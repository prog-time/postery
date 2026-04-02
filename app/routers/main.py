from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR
from app.routers.ai_provider import router as ai_provider_router
from app.routers.source import router as source_router
from app.routers.ai_generate import router as ai_generate_router
from app.routers.posts import router as posts_router

router = APIRouter()
router.include_router(ai_provider_router)
router.include_router(source_router)
router.include_router(ai_generate_router)
router.include_router(posts_router)

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")
