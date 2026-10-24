from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, computed_field
from app.core.config import settings


class SyncFileDetail(BaseModel):
    file: str
    folder: str
    action: str  # "imported" | "skipped" | "error"
    reason: Optional[str] = None
    records_extracted: Optional[int] = None
    template_type: Optional[str] = None
    error: Optional[str] = None


class SyncStatusData(BaseModel):
    status: str = Field(..., description="Sync state: 'idle', 'syncing', 'error'")
    last_sync_time: Optional[str] = Field(None, description="ISO timestamp of last successful sync")
    processed_files_count: int = Field(0, description="Total files processed/imported")
    skipped_files_count: int = Field(0, description="Total unchanged files skipped (0 overhead)")
    last_error: Optional[str] = Field(None, description="Error message if sync failed")
    details: List[Dict[str, Any]] = Field(default_factory=list, description="Recent file sync events")

    @computed_field
    @property
    def last_synced_at(self) -> Optional[str]:
        return self.last_sync_time

    @computed_field
    @property
    def synced_files_count(self) -> int:
        return self.processed_files_count

    @computed_field
    @property
    def message(self) -> str:
        return self.last_error or f"Обновлено файлов: {self.processed_files_count}, без изменений: {self.skipped_files_count}"

    @computed_field
    @property
    def root_folder_link(self) -> Optional[str]:
        return f"https://drive.google.com/drive/folders/{settings.GOOGLE_DRIVE_ROOT_FOLDER_ID}" if settings.GOOGLE_DRIVE_ROOT_FOLDER_ID else None

    @computed_field
    @property
    def drive_mode(self) -> str:
        return "mock" if settings.GOOGLE_DRIVE_MOCK else "live"


class InitFoldersRequest(BaseModel):
    root_folder_id: Optional[str] = Field(None, description="Optional Google Drive root or parent folder ID")


class InitFoldersResponse(BaseModel):
    status: str = Field("ok", description="Status of folder initialization")
    folders: Dict[str, str] = Field(..., description="Map of folder names to Drive folder IDs")
