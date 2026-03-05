from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api.database import set_db_path
from web.api.routers import links, magic_mappings, symbol_mappings, terminals


def create_app() -> FastAPI:
    app = FastAPI(title="Trade Copier Panel")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_path = os.environ.get("COPIER_DB_PATH", "")
    if db_path:
        set_db_path(db_path)

    app.include_router(terminals.router, prefix="/api")
    app.include_router(links.router, prefix="/api")
    app.include_router(symbol_mappings.router, prefix="/api")
    app.include_router(magic_mappings.router, prefix="/api")

    return app


app = create_app()
