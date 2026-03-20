from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api.database import initialize_db
from web.api.routers import config, links, magic_mappings, symbol_mappings, terminals


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_db()
    yield


def create_app() -> FastAPI:
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
    app.include_router(config.router, prefix="/api")

    return app


app = create_app()
