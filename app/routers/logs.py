"""Эндпоинт скачивания файла логов (TASK-LOG-005)."""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from app.config import BASE_DIR

router = APIRouter(prefix="/api/logs", tags=["logs"])

LOGS_FILE = BASE_DIR / "data" / "logs" / "app.log"


@router.get("/download")
async def download_logs(request: Request):
    if not request.session.get("user_id"):
        return JSONResponse(status_code=403, content={"ok": False, "error": "Требуется авторизация"})
    if not LOGS_FILE.exists():
        return JSONResponse(status_code=404, content={"ok": False, "error": "Файл логов не найден"})
    return FileResponse(
        path=str(LOGS_FILE),
        filename="app.log",
        media_type="text/plain",
    )
