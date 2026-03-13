from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import web.api.database as database
from web.api.database import initialize_db, set_db_path
from web.api.routers import links, magic_mappings, symbol_mappings, terminals

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "config.json"


def _resolve_db_path() -> str:
    """Get DB path from env var or config.json."""
    path = os.environ.get("COPIER_DB_PATH", "")
    if path:
        return path
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("db_path", "")
    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_db()
    yield


def create_app() -> FastAPI:
    if not database.DB_PATH:
        db_path = _resolve_db_path()
        if db_path:
            set_db_path(db_path)

    app = FastAPI(title="Trade Copier Panel", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(terminals.router, prefix="/api")
    app.include_router(links.router, prefix="/api")
    app.include_router(symbol_mappings.router, prefix="/api")
    app.include_router(magic_mappings.router, prefix="/api")

    return app


app = create_app()
