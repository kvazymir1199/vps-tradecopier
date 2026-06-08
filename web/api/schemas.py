from __future__ import annotations

from pydantic import BaseModel
from typing import Literal, Optional


# ── Terminals ──────────────────────────────────────────────────────

class TerminalCreate(BaseModel):
    terminal_id: str
    role: str  # "master" or "slave"


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


class LinkUpdate(BaseModel):
    enabled: Optional[int] = None
    lot_mode: Optional[str] = None
    lot_value: Optional[float] = None


class LinkOut(BaseModel):
    id: int
    master_id: str
    slave_id: str
    enabled: int
    lot_mode: str
    lot_value: float
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
    allowed_direction: Literal["BUY", "SELL", "BOTH"] = "BOTH"


class MagicMappingOut(BaseModel):
    id: int
    link_id: int
    master_setup_id: int
    slave_setup_id: int
    allowed_direction: Literal["BUY", "SELL", "BOTH"]


# ── Config ────────────────────────────────────────────────────────

class ConfigOut(BaseModel):
    vps_id: str
    heartbeat_interval_sec: int
    heartbeat_timeout_sec: int
    ack_timeout_sec: int
    ack_max_retries: int
    resend_window_size: int
    alert_dedup_minutes: int
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def from_db(cls, data: dict[str, str]) -> "ConfigOut":
        return cls(
            vps_id=data.get("vps_id", "vps_1"),
            heartbeat_interval_sec=int(data.get("heartbeat_interval_sec", "10")),
            heartbeat_timeout_sec=int(data.get("heartbeat_timeout_sec", "30")),
            ack_timeout_sec=int(data.get("ack_timeout_sec", "5")),
            ack_max_retries=int(data.get("ack_max_retries", "3")),
            resend_window_size=int(data.get("resend_window_size", "200")),
            alert_dedup_minutes=int(data.get("alert_dedup_minutes", "5")),
            telegram_enabled=data.get("telegram_enabled", "false").lower() == "true",
            telegram_bot_token=data.get("telegram_bot_token", ""),
            telegram_chat_id=data.get("telegram_chat_id", ""),
        )


class ConfigUpdate(BaseModel):
    vps_id: Optional[str] = None
    heartbeat_interval_sec: Optional[int] = None
    heartbeat_timeout_sec: Optional[int] = None
    ack_timeout_sec: Optional[int] = None
    ack_max_retries: Optional[int] = None
    resend_window_size: Optional[int] = None
    alert_dedup_minutes: Optional[int] = None
    telegram_enabled: Optional[bool] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


# ── Telegram settings (extended) ───────────────────────────────────

class TelegramSettingsOut(BaseModel):
    enabled: bool
    bot_token: str
    chat_id: str
    daily_summary_time: str
    alert_storm_threshold: int
    alerts_retention_days: int
    alert_dedup_minutes: int
    mute_until_ms: int
    alert_enabled: dict[str, bool]


class TelegramSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    daily_summary_time: Optional[str] = None
    alert_storm_threshold: Optional[int] = None
    alerts_retention_days: Optional[int] = None
    alert_dedup_minutes: Optional[int] = None
    alert_enabled: Optional[dict[str, bool]] = None


class TelegramTestResult(BaseModel):
    delivered: bool
    detail: str


class MuteRequest(BaseModel):
    duration_seconds: int


class MuteStatus(BaseModel):
    muted_until_ms: int


# ── Alerts history ─────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    alert_type: str
    terminal_id: Optional[str] = None
    message: str
    channel: str
    sent_at: int
    delivered: int
    retry_count: int
    deduplicated: int
    muted: int
