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
        target_path = (self.base_dir / storage_key).resolve()
        if target_path == self.base_dir or not target_path.is_relative_to(self.base_dir):
            raise ValueError("Storage key is outside the storage directory")
        return target_path

    def get_local_file_path(self, storage_key: str) -> Path:
        return self._resolve_safe_path(storage_key)

    def get_tenant_file_path(self, storage_key: str, company_id: uuid.UUID) -> Path:
        tenant_prefix = Path("tenants") / str(company_id)
        if not Path(storage_key).is_relative_to(tenant_prefix):
            raise FileNotFoundError("Storage key does not belong to the company")
        target_path = self._resolve_safe_path(storage_key)
        if not target_path.is_relative_to(self.base_dir / tenant_prefix):
            raise FileNotFoundError("Storage key does not belong to the company")
        return target_path

    async def save_file(self, file_bytes: bytes, storage_key: str) -> str:
        target_path = self._resolve_safe_path(storage_key)
        await self._write_file(file_bytes, target_path)
        return storage_key

    async def save_tenant_file(self, file_bytes: bytes, storage_key: str, company_id: uuid.UUID) -> Path:
        target_path = self.get_tenant_file_path(storage_key, company_id)
        await self._write_file(file_bytes, target_path)
        return target_path

    async def _write_file(self, file_bytes: bytes, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = target_path.with_name(f".{uuid.uuid4().hex}.tmp")
        try:
            async with aiofiles.open(temporary_path, "xb") as f:
                await f.write(file_bytes)
            temporary_path.replace(target_path)
        finally:
            temporary_path.unlink(missing_ok=True)

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
