from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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
