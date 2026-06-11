from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from omoikane.api.routes import router
from omoikane.db.models import init_db
from omoikane.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Omoikane",
        description="AI Workspace Memory Layer",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router, prefix="/v1")
    app.include_router(web_router)
    return app
