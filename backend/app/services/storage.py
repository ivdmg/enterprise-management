import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
import aiofiles
from app.core.config import settings


def build_tenant_storage_key(
    company_id: str | uuid.UUID,
    sha256_hash: str,
    extension: str = ".xlsx",
) -> str:
    """
    Constructs the canonical storage key path:
    tenants/{company_id}/{YYYY}/{MM}/{sha256_hash}{extension}
    Guarantees strict directory hierarchy and path traversal prevention.
    """
    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")
    ext = extension if extension.startswith(".") else f".{extension}"
    return f"tenants/{company_id}/{year}/{month}/{sha256_hash}{ext}"


class IStorageService(ABC):
    """Abstract interface for tenant file storage operations."""

    @abstractmethod
    async def save_file(self, file_bytes: bytes, storage_key: str) -> str:
        """Saves file bytes to the storage. Returns canonical relative storage key."""
        pass

    @abstractmethod
    async def get_file_bytes(self, storage_key: str) -> bytes:
        """Retrieves file bytes from storage."""
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Deletes file from storage."""
        pass

    @abstractmethod
    async def file_exists(self, storage_key: str) -> bool:
        """Checks if file exists in storage."""
        pass

    @abstractmethod
    def get_local_file_path(self, storage_key: str) -> Path:
        """Returns safe local Path for file-based processing libraries (openpyxl/calamine)."""
        pass


class LocalStorageService(IStorageService):
    """
    Local filesystem storage implementation with strict directory traversal prevention.
    """

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir or settings.STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        # Strip leading slashes to prevent root-escape
        normalized_key = storage_key.lstrip("/\\")
        target_path = (self.base_dir / normalized_key).resolve()
        # Path traversal guard
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError(f"Directory traversal attack detected in storage key: {storage_key}")
        return target_path

    def get_local_file_path(self, storage_key: str) -> Path:
        return self._resolve_safe_path(storage_key)

    async def save_file(self, file_bytes: bytes, storage_key: str) -> str:
        target_path = self._resolve_safe_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target_path, "wb") as f:
            await f.write(file_bytes)
        return storage_key

    async def get_file_bytes(self, storage_key: str) -> bytes:
        target_path = self._resolve_safe_path(storage_key)
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {storage_key}")
        async with aiofiles.open(target_path, "rb") as f:
            return await f.read()

    async def delete_file(self, storage_key: str) -> bool:
        target_path = self._resolve_safe_path(storage_key)
        if target_path.exists():
            target_path.unlink()
            return True
        return False

    async def file_exists(self, storage_key: str) -> bool:
        target_path = self._resolve_safe_path(storage_key)
        return target_path.is_file()


storage_service = LocalStorageService()
