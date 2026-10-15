from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Detailed error object conforming to REST API standards."""
    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Any] = Field(default=None, description="Optional payload / field-level details")


class MetaModel(BaseModel):
    """Metadata container for API responses."""
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the response generation",
    )
    page: Optional[int] = Field(default=None, description="Current page number")
    limit: Optional[int] = Field(default=None, description="Items per page limit")
    total_items: Optional[int] = Field(default=None, description="Total count of items")
    total_pages: Optional[int] = Field(default=None, description="Total pages available")


class ResponseEnvelope(BaseModel, Generic[T]):
    """
    Standard Response Envelope wrapping every API JSON payload.
    """
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="Boolean execution status flag")
    data: Optional[T] = Field(default=None, description="Payload data or null on failure")
    error: Optional[ErrorDetail] = Field(default=None, description="Error detail or null on success")
    meta: MetaModel = Field(default_factory=MetaModel, description="Response metadata")

    @classmethod
    def ok(cls, data: T, meta: Optional[MetaModel] = None) -> "ResponseEnvelope[T]":
        return cls(
            success=True,
            data=data,
            error=None,
            meta=meta or MetaModel(),
        )

    @classmethod
    def fail(cls, code: str, message: str, details: Optional[Any] = None) -> "ResponseEnvelope[None]":
        return cls(
            success=False,
            data=None,
            error=ErrorDetail(code=code, message=message, details=details),
            meta=MetaModel(),
        )


class PaginationParams(BaseModel):
    """Query parameters for pagination and sorting."""
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page limit")
    sort_by: Optional[str] = Field(default=None, description="Field name to sort by")
    order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order: asc or desc")
    search: Optional[str] = Field(default=None, description="Fulltext / substring search query")
