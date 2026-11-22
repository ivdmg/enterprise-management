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


SOURCE_KINDS = {"team": "engineers", "operations": "tenders", "finance": "finance", "stock": "procurement"}


# Native books containing only the synthetic examples created for this showcase.
DEMO_BOOKS = {
    "team": "1WHoJlmqvHwQcDZee2Zh8JMcrzqU2KfWzept61nSl_MM",
    "finance": "1g_viD8QSubypRDYo2_awbjmTuiHEDShOQ0bDPXvJTXc",
    "operations": "1VFEmY4ien_lCPmu69Gk90c6_wOTlxaFkpoqNj6ktDeU",
    "stock": "1vwB55WTuEhneA1MSqPWH6oY01sfL6iESl6anuMVvB64",
}
DEMO_TEMPLATES = {
    "team": (
        ("Реестр сотрудников", "1_ZAcCPZB9gK_KpEm449uE7IeMg18iJ9lxUvNs9PHIE0"),
        ("График команды", "1w0uwd1Bm0_AWWdnduARFOzLVxf5T3YKVqaC3ILAaUwU"),
    ),
    "finance": (("Платёжный календарь", "10jVz6uefVc_gJKv_vJ827mc3ITQ6EWQLizaJ0TC6Xms"),),
    "operations": (("Реестр заявок", "1HTMIIdE2O3YpqbiYpa0wg1TmlslB-XZOe-G6AB7XK6k"),),
    "stock": (
        ("Справочник номенклатуры", "1B7ZXmFsPDFdRpHGMSlasGnWFZcSfOlNJbI9gjCjOLGo"),
        ("Движение запасов", "1LbiqhSpYP8XUVcbwNUiu3rorTFLIVorTVv3x-GZxE2U"),
    ),
}
DEMO_TEMPLATE_IDS = {identifier for templates in DEMO_TEMPLATES.values() for _, identifier in templates}
DEMO_OPERATIONS_GIDS = {
    "Реестр контрактов": 0, "Ежедневный мониторинг": 1180388921,
    "Задачи": 1867629535, "Сигналы": 1062699588, "Смены": 214455523,
}


def sheet_url(identifier, gid=None):
    base = f"https://docs.google.com/spreadsheets/d/{identifier}/edit"
    return base if gid is None else f"{base}#gid={gid}"


DEMO_SOURCE_LINKS = {
    title: sheet_url(DEMO_BOOKS[key], DEMO_OPERATIONS_GIDS[title] if key == "operations" else 0)
    for key, titles in SHEETS.items() for title in titles
}


def node(name, key, children=None, active=False, metadata=None, source_kind=None, url=None):
    metadata = metadata or {}
    size = metadata.get("size")
    return {**({"url": url} if url else {}), "id": key, "name": name, "children": children, "active_source": active,
            "source_kind": source_kind, "size_bytes": int(size) if size is not None else None,
            "created_at": metadata.get("createdTime"), "modified_at": metadata.get("modifiedTime"), "owner": None}


def local_catalog(tables=None, updated_at=None):
    return [
        node(FOLDERS[key], key, [node(
            TITLES[key], f"{key}-sheet", active=True, source_kind=SOURCE_KINDS[key], url=sheet_url(DEMO_BOOKS[key]),
            metadata={"createdTime": updated_at, "size": len(json.dumps(
                {name: tables[name] for name in sheets}, ensure_ascii=False,
            ).encode())} if tables is not None else None,
        ), *(node(title, f"{key}-template-{index}", url=sheet_url(identifier))
             for index, (title, identifier) in enumerate(DEMO_TEMPLATES[key]))])
        for key, sheets in SHEETS.items()
    ]


class GoogleSource:
    def __init__(self):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials

        self.files = {key: os.environ[f"SHOWCASE_{key.upper()}_SHEET_ID"] for key in SHEETS}
        extra = os.getenv("SHOWCASE_CATALOG_FILE_IDS", "").split(",")
        self.allowed = set(self.files.values()) | DEMO_TEMPLATE_IDS | {value.strip() for value in extra if value.strip()}
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
        groups_by_file = {file_id: group for group, file_id in self.files.items()}
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
                    fields="nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime)", pageSize=100, pageToken=page,
                )
                for item in response.get("files", []):
                    identifier, mime = item["id"], item["mimeType"]
                    if not ID.fullmatch(identifier):
                        raise ValueError("invalid Drive ID")
                    key = f"{prefix}-{len(nodes)}"
                    if mime == FOLDER:
                        nodes.append(node(item["name"], key, walk(identifier, key, depth + 1)))
                    elif identifier in self.allowed and mime != "application/vnd.google-apps.shortcut":
                        group = groups_by_file.get(identifier)
                        active = group is not None
                        if active:
                            if mime != SHEET:
                                raise ValueError("expected a Google spreadsheet")
                            found.add(identifier)
                        url = sheet_url(identifier) if mime == SHEET and (active or identifier in DEMO_TEMPLATE_IDS) else None
                        nodes.append(node(item["name"], key, active=active, metadata=item,
                                          source_kind=SOURCE_KINDS.get(group), url=url))
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
        self.source_links = {}
        for key, sheets in SHEETS.items():
            book = f"https://sheets.googleapis.com/v4/spreadsheets/{self.files[key]}"
            meta = self.get(book, fields="sheets(properties(sheetId,title))")
            ids = {sheet["properties"]["title"]: sheet["properties"]["sheetId"] for sheet in meta["sheets"]}
            actual = ["Реест Ольга" if name == "Реестр контрактов" and name not in ids else name for name in sheets]
            for name, title in zip(sheets, actual, strict=True):
                gid = ids.get(title)
                if type(gid) is not int or gid < 0:
                    raise ValueError("missing sheet metadata")
                self.source_links[name] = f"https://docs.google.com/spreadsheets/d/{self.files[key]}/edit#gid={gid}"
            response = self.get(
                f"{book}/values:batchGet",
                ranges=[f"'{name}'!A1:Z1000" for name in actual], valueRenderOption="UNFORMATTED_VALUE",
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
            mapping = json.loads(os.getenv("SHOWCASE_COLUMN_MAPPING_JSON", "{}"))
            if not isinstance(mapping, dict) or any(not isinstance(value, dict) for value in mapping.values()):
                raise ValueError("invalid column mappings")
            links = getattr(reader, "source_links", {})
            links = links if isinstance(links, dict) else {}
            data = parse_tables(tables, today, mapping, links)
            data["source_links"] = links
            loaded = (data, catalog, timestamp())
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
        tables = seed_tables(today)
        data = parse_tables(tables, today)
        data["source_links"] = DEMO_SOURCE_LINKS
        for item in data["customer-tenders"]:
            item["link"] = DEMO_SOURCE_LINKS["Реестр контрактов"]
        for item in data["dashboard/projects"]:
            item["google_drive_link"] = DEMO_SOURCE_LINKS["Реестр контрактов"]
        catalog = local_catalog(tables, data["engineer-documents"]["synced_at"])
        return Current(data, catalog, "synthetic", None, issue)
