import base64
import hashlib
import io
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger("enterprise_hub.google_drive")


def execute_with_backoff(callable_fn: Callable[[], Any], max_retries: int = 3, initial_delay: float = 1.0) -> Any:
    """
    Executes a Google Drive API call with exponential backoff on HTTP 429 / 5xx rate limits.
    Delays: 1s, 2s, 4s...
    """
    delay = initial_delay
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return callable_fn()
        except Exception as exc:
            last_exc = exc
            status_code = getattr(getattr(exc, "resp", None), "status", None)
            # Google HttpError usually has resp.status == 429, 500, 503
            if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                logger.warning(
                    "Google Drive API returned status %s. Retrying in %.1fs (attempt %d/%d)...",
                    status_code, delay, attempt + 1, max_retries
                )
                time.sleep(delay)
                delay *= 2.0
            else:
                raise last_exc
    raise last_exc


class DriveFileInfo(BaseModel):
    """Metadata representation of a file in Google Drive or Mock Drive."""
    id: str = Field(..., description="Unique file ID or mock identifier")
    name: str = Field(..., description="Original file name")
    mime_type: str = Field(
        default="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        description="MIME type of the file",
    )
    size_bytes: int = Field(default=0, description="Size of file in bytes")
    md5_checksum: str = Field(..., description="MD5 hash of the file content for change detection")
    modified_time: datetime = Field(..., description="Last modification timestamp (UTC)")
    web_view_link: str = Field(..., description="URL to view/open file in browser")
    parent_folder: str = Field(..., description="Name or ID of parent folder")


class DriveUploadResult(BaseModel):
    """Result payload of a completed file upload."""
    id: str
    name: str
    web_view_link: str
    size_bytes: int
    md5_checksum: str


class GoogleDriveClient:
    """
    Unified Google Drive API v3 Client with zero-dependency Transparent Mock Mode.
    
    In Mock Mode (GOOGLE_DRIVE_MOCK=True or absent credentials):
    Emulates Google Drive API by reading and writing files from `storage/mock_drive/`,
    calculating real MD5 checksums, and providing deterministic file IDs.
    """

    # Folders required per Task BE-1.1
    STANDARD_FOLDERS = [
        "01_Сметы_и_Тендеры",
        "02_Счета_Снабжения",
        "03_Банк_и_Касса",
        "04_Путевые_листы",
        "05_Обработано",
        "99_Ошибки_парсинга",
    ]

    # Legacy folders for backwards compatibility with earlier templates
    LEGACY_FOLDERS = [
        "01_Реестры_Тендеров",
        "02_Финансы_и_1С",
        "03_Снабжение_и_Закупки",
        "04_ПТО_и_Объекты",
        "05_Юридический_Отдел",
    ]

    TARGET_FOLDERS = STANDARD_FOLDERS

    # Protected system folders that should never be deleted
    PROTECTED_FOLDERS = set(STANDARD_FOLDERS + LEGACY_FOLDERS)

    def __init__(
        self,
        mock_mode: Optional[bool] = None,
        mock_dir: Optional[Path] = None,
        credentials_path: Optional[Path] = None,
    ):
        if mock_dir:
            self.mock_dir = Path(mock_dir).resolve()
        else:
            # Check workspace root first, then cwd
            ws_root_mock = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "mock_drive"
            cwd_mock = Path(settings.GOOGLE_DRIVE_MOCK_DIR).resolve()
            if ws_root_mock.exists() and any(ws_root_mock.iterdir()):
                self.mock_dir = ws_root_mock
            elif cwd_mock.exists() and any(cwd_mock.iterdir()):
                self.mock_dir = cwd_mock
            elif ws_root_mock.parent.exists():
                self.mock_dir = ws_root_mock
            else:
                self.mock_dir = cwd_mock

        self.mock_dir.mkdir(parents=True, exist_ok=True)
        
        credentials_file = Path(credentials_path or settings.GOOGLE_DRIVE_CREDENTIALS_PATH)
        configured_mock = settings.GOOGLE_DRIVE_MOCK if mock_mode is None else mock_mode
        has_sa_json = bool(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        
        # Determine whether to use mock mode
        self.is_mock = configured_mock or (not has_sa_json and not credentials_file.is_file())
        self._service = None
        self._folder_ids_cache: Dict[str, str] = {}

        if self.is_mock:
            logger.info("GoogleDriveClient initialized in MOCK MODE (root: %s)", self.mock_dir)
            self._ensure_mock_folders()
        else:
            try:
                from google.oauth2 import service_account  # type: ignore
                from googleapiclient.discovery import build  # type: ignore

                creds = None
                if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
                    raw_val = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
                    try:
                        # Try base64 decoding first
                        decoded = base64.b64decode(raw_val).decode("utf-8")
                        info = json.loads(decoded)
                    except Exception:
                        info = json.loads(raw_val)
                    creds = service_account.Credentials.from_service_account_info(
                        info,
                        scopes=["https://www.googleapis.com/auth/drive"],
                    )
                elif credentials_file.is_file():
                    creds = service_account.Credentials.from_service_account_file(
                        str(credentials_file),
                        scopes=["https://www.googleapis.com/auth/drive"],
                    )

                if creds:
                    self._service = build("drive", "v3", credentials=creds)
                    logger.info("GoogleDriveClient connected to live Google Drive API v3")
                else:
                    self.is_mock = True
                    self._ensure_mock_folders()
            except Exception as e:
                logger.warning(
                    "Failed to initialize live Google Drive API (%s). Falling back to MOCK MODE.", e
                )
                self.is_mock = True
                self._ensure_mock_folders()

    def _ensure_mock_folders(self) -> None:
        """Creates target directory structure in mock storage if not already present."""
        for folder_name in self.STANDARD_FOLDERS + self.LEGACY_FOLDERS:
            (self.mock_dir / folder_name).mkdir(parents=True, exist_ok=True)

    def init_folders(self, root_folder_id: Optional[str] = None) -> Dict[str, str]:
        """
        Initializes standard folder structure on Google Drive or in Mock Mode (Task BE-1.1).
        Creates:
        - 01_Сметы_и_Тендеры
        - 02_Счета_Снабжения
        - 03_Банк_и_Касса
        - 04_Путевые_листы
        - 05_Обработано
        - 99_Ошибки_парсинга
        Returns mapping of {folder_name: folder_id}.
        """
        root_id = root_folder_id or settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
        folder_mapping: Dict[str, str] = {}

        if self.is_mock:
            self._ensure_mock_folders()
            for name in self.STANDARD_FOLDERS:
                folder_path = self.mock_dir / name
                folder_mapping[name] = str(folder_path)
                self._folder_ids_cache[name] = str(folder_path)
            return folder_mapping

        # Real Google Drive API v3
        from googleapiclient.errors import HttpError  # type: ignore

        parent_clause = f"'{root_id}' in parents and " if root_id else ""
        for name in self.STANDARD_FOLDERS:
            def find_or_create():
                query = (
                    f"{parent_clause}name = '{name}' and "
                    f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                )
                resp = self._service.files().list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)",
                ).execute()
                files = resp.get("files", [])
                if files:
                    return files[0]["id"]

                # Create folder
                folder_metadata = {
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                }
                if root_id:
                    folder_metadata["parents"] = [root_id]
                created = self._service.files().create(
                    body=folder_metadata,
                    fields="id",
                ).execute()
                return created.get("id")

            try:
                fid = execute_with_backoff(find_or_create)
                folder_mapping[name] = fid
                self._folder_ids_cache[name] = fid
                logger.info("Initialized Google Drive folder '%s' (id: %s)", name, fid)
            except Exception as e:
                logger.error("Error creating folder '%s' on Google Drive: %s", name, e)
                raise

        return folder_mapping

    def _get_mock_file_id(self, rel_path: Path) -> str:
        """Generates deterministic mock file ID from relative path."""
        norm = str(rel_path).replace("\\", "/").strip("/")
        return f"mock-file-{hashlib.md5(norm.encode('utf-8')).hexdigest()[:16]}"

    def _resolve_mock_file_path(self, file_id_or_path: str) -> Path:
        """Resolves file ID or relative path to an absolute Path in mock directory."""
        # 1. Check direct absolute/relative path
        direct_path = Path(file_id_or_path)
        if direct_path.is_file():
            return direct_path.resolve()

        under_mock = (self.mock_dir / file_id_or_path.lstrip("/\\")).resolve()
        if under_mock.is_file():
            return under_mock

        # 2. Search by mock ID across mock directory
        for f in self.mock_dir.rglob("*.xlsx"):
            rel = f.relative_to(self.mock_dir)
            if self._get_mock_file_id(rel) == file_id_or_path or f.name == file_id_or_path:
                return f.resolve()

        raise FileNotFoundError(f"File not found on Google Drive (mock): {file_id_or_path}")

    def list_files_in_folder(
        self,
        folder_name_or_id: str,
        modified_after: Optional[datetime] = None,
    ) -> List[DriveFileInfo]:
        """
        Lists documents (.xlsx, .xls, .txt, .pdf) inside the specified folder.
        If folder_name_or_id is 'root' or empty, searches across standard folders.
        Filters by modified_after if provided.
        """
        valid_extensions = (".xlsx", ".xls", ".txt", ".pdf")

        if self.is_mock:
            results: List[DriveFileInfo] = []
            
            clean_folder = folder_name_or_id.strip("/\\")
            if not clean_folder or clean_folder in ("root", "all"):
                search_dirs = [self.mock_dir / folder for folder in self.STANDARD_FOLDERS + self.LEGACY_FOLDERS]
            else:
                target_dir = (self.mock_dir / clean_folder).resolve()
                search_dirs = [target_dir] if target_dir.is_dir() else []

            for folder_path in search_dirs:
                if not folder_path.exists():
                    continue
                folder_name = folder_path.name
                for file_path in folder_path.iterdir():
                    if not file_path.is_file() or file_path.name.startswith("~$"):
                        continue  # Skip directories and temporary Excel lock files
                    if not any(file_path.name.lower().endswith(ext) for ext in valid_extensions):
                        continue

                    stat = file_path.stat()
                    mod_dt = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                    if modified_after and mod_dt <= modified_after:
                        continue

                    content = file_path.read_bytes()
                    md5_hash = hashlib.md5(content).hexdigest()
                    rel_path = file_path.relative_to(self.mock_dir)
                    mock_id = self._get_mock_file_id(rel_path)

                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if file_path.name.lower().endswith(".txt"):
                        mime = "text/plain"
                    elif file_path.name.lower().endswith(".pdf"):
                        mime = "application/pdf"

                    results.append(
                        DriveFileInfo(
                            id=mock_id,
                            name=file_path.name,
                            mime_type=mime,
                            size_bytes=stat.st_size,
                            md5_checksum=md5_hash,
                            modified_time=mod_dt,
                            web_view_link=self.get_web_view_link(mock_id),
                            parent_folder=folder_name,
                        )
                    )
            return sorted(results, key=lambda x: x.name)

        # Real Google Drive API v3
        from googleapiclient.errors import HttpError  # type: ignore

        try:
            q_parts = [
                f"'{folder_name_or_id}' in parents",
                "trashed = false",
                "mimeType != 'application/vnd.google-apps.folder'",
            ]
            if modified_after:
                iso_time = modified_after.strftime("%Y-%m-%dT%H:%M:%SZ")
                q_parts.append(f"modifiedTime > '{iso_time}'")

            q = " and ".join(q_parts)

            def do_list():
                return (
                    self._service.files()
                    .list(
                        q=q,
                        fields="files(id, name, mimeType, size, md5Checksum, modifiedTime, webViewLink, parents)",
                        pageSize=100,
                    )
                    .execute()
                )

            response = execute_with_backoff(do_list)
            files = response.get("files", [])
            drive_files = []
            for f in files:
                drive_files.append(
                    DriveFileInfo(
                        id=f.get("id"),
                        name=f.get("name"),
                        mime_type=f.get("mimeType"),
                        size_bytes=int(f.get("size", 0)),
                        md5_checksum=f.get("md5Checksum", ""),
                        modified_time=datetime.fromisoformat(f.get("modifiedTime").replace("Z", "+00:00")),
                        web_view_link=f.get("webViewLink", ""),
                        parent_folder=folder_name_or_id,
                    )
                )
            return drive_files
        except Exception as e:
            logger.error("Error listing files in Google Drive folder %s: %s", folder_name_or_id, e)
            raise

    def download_file_bytes(self, file_id_or_path: str) -> bytes:
        """Downloads raw binary content of a file."""
        if self.is_mock:
            target_path = self._resolve_mock_file_path(file_id_or_path)
            return target_path.read_bytes()

        # Real Google Drive API v3
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore

        def do_download():
            request = self._service.files().get_media(fileId=file_id_or_path)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return fh.getvalue()

        return execute_with_backoff(do_download)

    def upload_file(
        self, folder_name_or_id: str, filename: str, content: bytes, description: Optional[str] = None
    ) -> DriveUploadResult:
        """Uploads a file to Google Drive or the Mock Drive directory."""
        md5_hash = hashlib.md5(content).hexdigest()
        size_bytes = len(content)

        if self.is_mock:
            clean_folder = folder_name_or_id.strip("/\\")
            target_folder = self.mock_dir / clean_folder
            target_folder.mkdir(parents=True, exist_ok=True)
            target_file = target_folder / filename
            target_file.write_bytes(content)

            rel_path = target_file.relative_to(self.mock_dir)
            mock_id = self._get_mock_file_id(rel_path)
            web_link = self.get_web_view_link(mock_id)

            logger.info("Mock Drive: Uploaded '%s' to folder '%s' (size: %d bytes)", filename, clean_folder, size_bytes)
            return DriveUploadResult(
                id=mock_id,
                name=filename,
                web_view_link=web_link,
                size_bytes=size_bytes,
                md5_checksum=md5_hash,
            )

        # Real Google Drive API v3
        from googleapiclient.http import MediaIoBaseUpload  # type: ignore

        file_metadata: Dict[str, Any] = {
            "name": filename,
            "parents": [folder_name_or_id],
        }
        if description:
            file_metadata["description"] = description

        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if filename.lower().endswith(".txt"):
            mime = "text/plain"
        elif filename.lower().endswith(".pdf"):
            mime = "application/pdf"

        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype=mime,
            resumable=True,
        )

        def do_upload():
            return (
                self._service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, webViewLink, size, md5Checksum",
                )
                .execute()
            )

        file = execute_with_backoff(do_upload)
        return DriveUploadResult(
            id=file.get("id"),
            name=file.get("name"),
            web_view_link=file.get("webViewLink", ""),
            size_bytes=int(file.get("size", size_bytes)),
            md5_checksum=file.get("md5Checksum", md5_hash),
        )

    def move_file(
        self,
        file_id: str,
        target_folder_name_or_id: str,
        current_folder_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        Moves file on Google Drive or in Mock Mode from its current parent folder
        to target_folder_name_or_id (Task BE-1.3).
        If description is given, updates Drive metadata 'description' (e.g. for error logs).
        """
        if self.is_mock:
            try:
                source_path = self._resolve_mock_file_path(file_id)
                clean_target = target_folder_name_or_id.strip("/\\")
                target_dir = self.mock_dir / clean_target
                target_dir.mkdir(parents=True, exist_ok=True)
                dest_path = target_dir / source_path.name
                
                # If target file exists, overwrite or rename
                if dest_path.exists() and dest_path != source_path:
                    dest_path.unlink()
                source_path.rename(dest_path)

                if description:
                    # Write companion .meta.txt or log description
                    meta_file = target_dir / f"{source_path.name}.meta.txt"
                    meta_file.write_text(description, encoding="utf-8")

                logger.info("Mock Drive: Moved '%s' to folder '%s'", source_path.name, clean_target)
                return True
            except Exception as e:
                logger.error("Mock Drive: Error moving file %s: %s", file_id, e)
                return False

        # Real Google Drive API v3
        try:
            # First retrieve current parents if not provided
            def get_parents():
                f = self._service.files().get(fileId=file_id, fields="parents").execute()
                return ",".join(f.get("parents", []))

            previous_parents = current_folder_id or execute_with_backoff(get_parents)

            def do_move():
                body_meta = {}
                if description is not None:
                    body_meta["description"] = description
                return (
                    self._service.files()
                    .update(
                        fileId=file_id,
                        addParents=target_folder_name_or_id,
                        removeParents=previous_parents,
                        body=body_meta if body_meta else None,
                        fields="id, parents, description",
                    )
                    .execute()
                )

            execute_with_backoff(do_move)
            logger.info("Google Drive: Moved file %s to folder %s", file_id, target_folder_name_or_id)
            return True
        except Exception as e:
            logger.error("Google Drive: Failed to move file %s to folder %s: %s", file_id, target_folder_name_or_id, e)
            return False

    def get_web_view_link(self, file_id_or_path: str) -> str:
        """Returns browser web view URL for the file."""
        if self.is_mock:
            # Deterministic mock URL pointing to mock drive interface
            return f"https://drive.google.com/file/d/{file_id_or_path}/view?usp=sharing"
        return f"https://drive.google.com/file/d/{file_id_or_path}/view"


# Singleton instance
google_drive_client = GoogleDriveClient()


def get_google_drive_client() -> GoogleDriveClient:
    """Returns singleton instance of GoogleDriveClient."""
    return google_drive_client
