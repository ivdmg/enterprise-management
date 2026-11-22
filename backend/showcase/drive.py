"""Server-only Drive reader. Requests are built exclusively from deployment config."""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread
from time import monotonic

from .tables import FOLDERS, SHEETS, TITLES, parse_tables, seed_tables, timestamp

FOLDER = "application/vnd.google-apps.folder"
SHEET = "application/vnd.google-apps.spreadsheet"
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly",
          "https://www.googleapis.com/auth/spreadsheets.readonly"]
ROOT = "1lvoObAIIBUS2uc8uw-WmOeXzaJ_TdqYF"
ID = re.compile(r"[A-Za-z0-9_-]{10,150}")
LOG = logging.getLogger(__name__)


def node(name, key, children=None, active=False):
    return {"id": key, "name": name, "children": children, "active_source": active,
            "size_bytes": None, "created_at": None, "owner": None}


def local_catalog():
    return [node(FOLDERS[key], key, [node(TITLES[key], f"{key}-sheet", active=True)]) for key in SHEETS]


class GoogleSource:
    def __init__(self):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials

        self.files = {key: os.environ[f"SHOWCASE_{key.upper()}_SHEET_ID"] for key in SHEETS}
        extra = os.getenv("SHOWCASE_CATALOG_FILE_IDS", "").split(",")
        self.allowed = set(self.files.values()) | {value.strip() for value in extra if value.strip()}
        if not all(ID.fullmatch(value) for value in self.allowed) or len(set(self.files.values())) != len(SHEETS):
            raise ValueError("invalid Drive allowlist")
        payload = os.getenv("SHOWCASE_GOOGLE_CREDENTIALS_JSON")
        if not payload:
            payload = Path(os.environ["SHOWCASE_GOOGLE_CREDENTIALS_FILE"]).read_text(encoding="utf-8")
        info = json.loads(payload)
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
        self.session = AuthorizedSession(credentials, max_refresh_attempts=0)

    def get(self, url, **params):
        with self.session.get(url, params=params, timeout=(3, 6), max_allowed_time=12,
                              allow_redirects=False) as response:
            if response.status_code == 400 and "/values:batchGet" in url:
                raise ValueError("invalid sheet range")
            if response.status_code != 200:
                raise OSError("Google API request failed")
            return response.json()

    def close(self):
        self.session.close()

    def load(self):
        found = set()
        remaining = 40

        def walk(parent, prefix="demo", depth=0):
            nonlocal remaining
            nodes = []
            page = None
            while True:
                remaining -= 1
                if remaining < 0 or depth > 5:
                    raise ValueError("Drive catalog exceeds bounds")
                response = self.get(
                    "https://www.googleapis.com/drive/v3/files",
                    q=f"'{parent}' in parents and trashed = false",
                    fields="nextPageToken,files(id,name,mimeType)", pageSize=100, pageToken=page,
                )
                for item in response.get("files", []):
                    identifier, mime = item["id"], item["mimeType"]
                    if not ID.fullmatch(identifier):
                        raise ValueError("invalid Drive ID")
                    key = f"{prefix}-{len(nodes)}"
                    if mime == FOLDER:
                        nodes.append(node(item["name"], key, walk(identifier, key, depth + 1)))
                    elif identifier in self.allowed and mime != "application/vnd.google-apps.shortcut":
                        active = identifier in self.files.values()
                        if active:
                            if mime != SHEET:
                                raise ValueError("expected a Google spreadsheet")
                            found.add(identifier)
                        nodes.append(node(item["name"], key, active=active))
                page = response.get("nextPageToken")
                if not page:
                    return nodes

        root = self.get(f"https://www.googleapis.com/drive/v3/files/{ROOT}", fields="mimeType,trashed")
        if root.get("mimeType") != FOLDER or root.get("trashed"):
            raise ValueError("invalid demo root")
        catalog = walk(ROOT)
        if found != set(self.files.values()):
            raise ValueError("configured spreadsheets are outside the demo root or missing")
        tables = {}
        for key, sheets in SHEETS.items():
            response = self.get(
                f"https://sheets.googleapis.com/v4/spreadsheets/{self.files[key]}/values:batchGet",
                ranges=[f"'{name}'!A1:Z1000" for name in sheets], valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="SERIAL_NUMBER",
            )
            for name, result in zip(sheets, response["valueRanges"], strict=True):
                tables[name] = result.get("values", [])
        return tables, catalog


@dataclass(frozen=True)
class Current:
    data: dict
    catalog: list
    source: str
    refreshed_at: str | None
    issue: str | None


class Snapshots:
    def __init__(self):
        self.lock = Lock()
        self.next_refresh = 0
        self.last = None
        self.issue = None

    def refresh(self, today):
        try:
            reader = GoogleSource()
            try:
                tables, catalog = reader.load()
            finally:
                reader.close()
            loaded = (parse_tables(tables, today), catalog, timestamp())
        except Exception as exc:
            issue = "schema" if isinstance(exc, ValueError) else "unavailable"
            LOG.warning("Showcase refresh failed (%s)", issue)
            with self.lock:
                self.issue = issue
                self.next_refresh = monotonic() + 60
        else:
            with self.lock:
                self.last = loaded
                self.issue = None
                self.next_refresh = monotonic() + 60

    def current(self, today):
        configured = os.getenv("SHOWCASE_GOOGLE_CREDENTIALS_JSON") or os.getenv("SHOWCASE_GOOGLE_CREDENTIALS_FILE")
        with self.lock:
            if configured and monotonic() >= self.next_refresh:
                self.next_refresh = float("inf")
                Thread(target=self.refresh, args=(today,), daemon=True).start()
            issue = self.issue
            if self.last:
                data, catalog, at = self.last
                return Current(data, catalog, "snapshot" if issue else "drive", at, issue)
        return Current(parse_tables(seed_tables(today), today), local_catalog(), "synthetic", None, issue)
