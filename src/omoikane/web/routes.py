from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

TEMPLATE_DIR = Path(__file__).parent / "templates"


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    html_path = TEMPLATE_DIR / "dashboard.html"
    return HTMLResponse(content=html_path.read_text())
