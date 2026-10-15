import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import DomainCategory, FileStatus


class FileUploadResponseData(BaseModel):
    """Response payload for file upload."""
    file_id: uuid.UUID
    original_name: str
    file_size_bytes: int
    sha256_hash: str
    status: FileStatus
    sheets: List[str]
    is_cached_template: bool


class ColumnMappingItem(BaseModel):
    """Single column mapping proposal."""
    source_column: str
    sample_values: List[str]
    target_field: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_required: bool = False


class CanonicalFieldDefinition(BaseModel):
    """Specification of a canonical domain field."""
    field: str
    label: str
    required: bool


class MappingPreviewResponseData(BaseModel):
    """Payload for column mapping preview endpoint."""
    file_id: uuid.UUID
    sheet_name: str
    suggested_domain: DomainCategory
    confidence_score: float
    source_type: str  # 'template_cache' | 'ai_inference' | 'heuristic'
    total_rows_detected: int
    columns_mapping: List[ColumnMappingItem]
    available_canonical_fields: List[CanonicalFieldDefinition]


class MappingConfirmRequest(BaseModel):
    """Payload for confirming mapping and triggering ingestion into canonical table."""
    sheet_name: str
    domain_category: DomainCategory
    template_name: Optional[str] = None
    mappings: Dict[str, str]  # {"Исходная колонка": "target_field" or "ignore"}


class MappingConfirmResponseData(BaseModel):
    """Response payload after successful mapping confirmation and row import."""
    file_id: uuid.UUID
    status: FileStatus
    imported_rows_count: int
    alerts_triggered_count: int = 0
    template_saved: bool = True


class FileListItem(BaseModel):
    """Item in uploaded files catalog."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_name: str
    file_size_bytes: int
    status: FileStatus
    uploaded_by: Optional[str] = None
    created_at: datetime
