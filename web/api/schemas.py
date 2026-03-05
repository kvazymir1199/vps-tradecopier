from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


# ── Terminals ──────────────────────────────────────────────────────

class TerminalOut(BaseModel):
    terminal_id: str
    role: str
    account_number: Optional[int] = None
    broker_server: Optional[str] = None
    status: str
    status_message: Optional[str] = None
    last_heartbeat: int


# ── Links ──────────────────────────────────────────────────────────

class LinkCreate(BaseModel):
    master_id: str
    slave_id: str
    lot_mode: str = "multiplier"
    lot_value: float = 1.0
    symbol_suffix: str = ""


class LinkUpdate(BaseModel):
    enabled: Optional[int] = None
    lot_mode: Optional[str] = None
    lot_value: Optional[float] = None
    symbol_suffix: Optional[str] = None


class LinkOut(BaseModel):
    id: int
    master_id: str
    slave_id: str
    enabled: int
    lot_mode: str
    lot_value: float
    symbol_suffix: Optional[str] = None
    created_at: int


# ── Symbol mappings ────────────────────────────────────────────────

class SymbolMappingCreate(BaseModel):
    master_symbol: str
    slave_symbol: str


class SymbolMappingOut(BaseModel):
    id: int
    link_id: int
    master_symbol: str
    slave_symbol: str


# ── Magic mappings ─────────────────────────────────────────────────

class MagicMappingCreate(BaseModel):
    master_setup_id: int
    slave_setup_id: int


class MagicMappingOut(BaseModel):
    id: int
    link_id: int
    master_setup_id: int
    slave_setup_id: int
