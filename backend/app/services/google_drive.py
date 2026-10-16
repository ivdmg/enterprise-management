import hashlib
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger("enterprise_hub.google_drive")


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
    
    In Mock Mode (GOOGLE_DRIVE_MOCK=True or absent credentials.json):
    Emulates Google Drive API by reading and writing files from `storage/mock_drive/`,
    calculating real MD5 checksums, and providing deterministic file IDs.
    """

    TARGET_FOLDERS = [
        "01_Реестры_Тендеров",
        "02_Финансы_и_1С",
        "03_Снабжение_и_Закупки",
        "04_ПТО_и_Объекты",
        "05_Юридический_Отдел",
    ]

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
        
        # Determine whether to use mock mode
        self.is_mock = configured_mock or not credentials_file.is_file()
        self._service = None

        if self.is_mock:
            logger.info("GoogleDriveClient initialized in MOCK MODE (root: %s)", self.mock_dir)
            self._ensure_mock_folders()
        else:
            try:
                from google.oauth2 import service_account  # type: ignore
                from googleapiclient.discovery import build  # type: ignore

                creds = service_account.Credentials.from_service_account_file(
                    str(credentials_file),
                    scopes=["https://www.googleapis.com/auth/drive"],
                )
                self._service = build("drive", "v3", credentials=creds)
                logger.info("GoogleDriveClient connected to live Google Drive API v3 via %s", credentials_file)
            except Exception as e:
                logger.warning(
                    "Failed to initialize live Google Drive API (%s). Falling back to MOCK MODE.", e
                )
                self.is_mock = True
                self._ensure_mock_folders()

    def _ensure_mock_folders(self) -> None:
        """Creates target directory structure in mock storage if not already present."""
        for folder_name in self.TARGET_FOLDERS:
            (self.mock_dir / folder_name).mkdir(parents=True, exist_ok=True)

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

    def list_files_in_folder(self, folder_name_or_id: str) -> List[DriveFileInfo]:
        """
        Lists Excel files (.xlsx) inside the specified folder.
        If folder_name_or_id is 'root' or empty, searches across all 5 standard folders.
        """
        if self.is_mock:
            results: List[DriveFileInfo] = []
            
            clean_folder = folder_name_or_id.strip("/\\")
            if not clean_folder or clean_folder in ("root", "all"):
                search_dirs = [self.mock_dir / folder for folder in self.TARGET_FOLDERS]
            else:
                target_dir = (self.mock_dir / clean_folder).resolve()
                search_dirs = [target_dir] if target_dir.is_dir() else []

            for folder_path in search_dirs:
                if not folder_path.exists():
                    continue
                folder_name = folder_path.name
                for file_path in folder_path.glob("*.xlsx"):
                    if file_path.name.startswith("~$"):
                        continue  # Skip temporary Excel lock files
                    
                    stat = file_path.stat()
                    content = file_path.read_bytes()
                    md5_hash = hashlib.md5(content).hexdigest()
                    rel_path = file_path.relative_to(self.mock_dir)
                    mock_id = self._get_mock_file_id(rel_path)
                    mod_dt = datetime.fromtimestamp(stat.st_mtime, timezone.utc)

                    results.append(
                        DriveFileInfo(
                            id=mock_id,
                            name=file_path.name,
                            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
            q = f"'{folder_name_or_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'"
            response = (
                self._service.files()
                .list(
                    q=q,
                    fields="files(id, name, mimeType, size, md5Checksum, modifiedTime, webViewLink, parents)",
                    pageSize=100,
                )
                .execute()
            )
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

        request = self._service.files().get_media(fileId=file_id_or_path)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()

    def upload_file(
        self, folder_name_or_id: str, filename: str, content: bytes
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

        file_metadata = {
            "name": filename,
            "parents": [folder_name_or_id],
        }
        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=True,
        )
        file = (
            self._service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id, name, webViewLink, size, md5Checksum",
            )
            .execute()
        )
        return DriveUploadResult(
            id=file.get("id"),
            name=file.get("name"),
            web_view_link=file.get("webViewLink", ""),
            size_bytes=int(file.get("size", size_bytes)),
            md5_checksum=file.get("md5Checksum", md5_hash),
        )

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
