"""GET /health — публичный эндпоинт проверки работоспособности.

Используется Docker-healthcheck и внешними мониторингами.
Не требует авторизации. Проверяет доступность БД через SELECT 1.
Документирован в rules/api/endpoints.md, раздел 2.9.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import SessionLocal

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health", include_in_schema=True)
async def health() -> JSONResponse:
    """Возвращает HTTP 200 {"status": "ok"} если БД доступна, иначе HTTP 503."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        log.error("Health check: DB unavailable — %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "detail": "db_unavailable"})

    return JSONResponse(status_code=200, content={"status": "ok"})
