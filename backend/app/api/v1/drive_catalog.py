import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import get_current_active_manager
from app.core.config import settings
from app.models.user import User
from app.schemas.common import ResponseEnvelope
from app.services.engineer_documents import GOOGLE_SHEET, is_engineer_source
from app.services.google_drive import GoogleDriveClient, execute_with_backoff

router = APIRouter(prefix="/drive-catalog", tags=["Google Drive"])
FOLDER = "application/vnd.google-apps.folder"


def read_catalog():
    # A separate transport keeps these reads independent from scheduled imports.
    client = GoogleDriveClient()

    def list_children(folder_id):
        page_token = None
        items = []
        while True:
            page = execute_with_backoff(lambda: client._service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken,files(id,name,mimeType,size,createdTime,owners(displayName))",
                pageSize=100, pageToken=page_token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute())
            items.extend(page.get("files", []))
            page_token = page.get("nextPageToken")
            if not page_token:
                break

        root = folder_id == settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
        engineer_sources = [item["id"] for item in items
                            if root and is_engineer_source(item["name"], item["mimeType"])]
        nodes = []
        for item in sorted(items, key=lambda entry: (entry["mimeType"] != FOLDER, entry["name"].casefold())):
            is_folder = item["mimeType"] == FOLDER
            file_id = item["id"]
            is_active_source = not is_folder and (
                file_id == settings.GOOGLE_DRIVE_SOURCE_FILE_ID or engineer_sources == [file_id]
            )
            url = f"https://drive.google.com/file/d/{file_id}/view"
            if is_folder:
                url = f"https://drive.google.com/drive/folders/{file_id}"
            elif item["mimeType"] == GOOGLE_SHEET:
                url = f"https://docs.google.com/spreadsheets/d/{file_id}/view"
            nodes.append({
                "id": file_id, "name": item["name"], "url": url,
                "active_source": is_active_source,
                "size_bytes": int(item["size"]) if item.get("size") is not None else None,
                "created_at": item.get("createdTime"),
                "owner": next((owner.get("displayName") for owner in item.get("owners", [])
                               if owner.get("displayName")), None),
                "children": list_children(file_id) if is_folder else None,
            })
        return nodes

    return list_children(settings.GOOGLE_DRIVE_ROOT_FOLDER_ID)


@router.get("")
async def get_catalog(response: Response, user: User = Depends(get_current_active_manager)):
    if (settings.GOOGLE_DRIVE_MOCK or user.company_id != settings.GOOGLE_DRIVE_COMPANY_ID
            or not settings.GOOGLE_DRIVE_ROOT_FOLDER_ID):
        raise HTTPException(404, "Google Диск не подключён к этой организации")
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return ResponseEnvelope.ok(await asyncio.to_thread(read_catalog))
    except Exception as exc:
        raise HTTPException(502, "Не удалось прочитать каталог Google Диска") from exc
