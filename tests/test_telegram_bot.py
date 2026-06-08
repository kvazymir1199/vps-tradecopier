"""TelegramBot — command routing, auth, mute parsing.

We don't talk to the real Telegram API. Each test fabricates an update dict
the way getUpdates would return it and invokes `_handle_update` directly.
Outbound bot replies (`send_raw_markdown`) are captured in a list.
"""

import time
from dataclasses import dataclass, field

import pytest

from hub.config import ALERT_TYPES
from hub.db.manager import DatabaseManager
from hub.monitor.alerts import AlertSender
from hub.monitor.health import HealthChecker
from hub.monitor.telegram_bot import TelegramBot, _parse_duration


@dataclass
class FakeTelegram:
    enabled: bool = True
    bot_token: str = "tok"
    chat_id: str = "100"
    daily_summary_time: str = "08:00"
    alert_storm_threshold: int = 10
    alerts_retention_days: int = 90
    alert_enabled: dict[str, bool] = field(default_factory=dict)


@dataclass
class FakeConfig:
    vps_id: str = "vps_1"
    heartbeat_interval_sec: int = 10
    heartbeat_timeout_sec: int = 30
    ack_timeout_sec: int = 5
    ack_max_retries: int = 3
    resend_window_size: int = 200
    alert_dedup_minutes: int = 5
    telegram: FakeTelegram | None = None

    def __post_init__(self):
        if self.telegram is None:
            self.telegram = FakeTelegram()
        for at in ALERT_TYPES:
            self.telegram.alert_enabled.setdefault(at, True)


def _msg(chat_id: str, text: str, update_id: int = 1) -> dict:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": int(chat_id)}, "text": text},
    }


@pytest.fixture
async def bot_pieces():
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig()
    sender = AlertSender(db, cfg)
    replies: list[str] = []

    async def _capture(text: str) -> bool:
        replies.append(text)
        return True

    sender.send_raw_markdown = _capture  # type: ignore[assignment]
    hc = HealthChecker(db, cfg, resend_callback=lambda *_: None)
    bot = TelegramBot(db, cfg, sender, hc, hub_started_at_ms=int(time.time() * 1000))
    yield db, cfg, sender, bot, replies
    await db.close()


# ──────────────────── duration parser ─────────────────────


def test_parse_duration_supports_s_m_h_d():
    assert _parse_duration("30s") == 30_000
    assert _parse_duration("15m") == 15 * 60_000
    assert _parse_duration("2h") == 2 * 3_600_000
    assert _parse_duration("1d") == 86_400_000


def test_parse_duration_rejects_garbage():
    assert _parse_duration("hello") is None
    assert _parse_duration("") is None
    assert _parse_duration("10") is None


# ──────────────────── auth ─────────────────────


@pytest.mark.asyncio
async def test_unknown_chat_id_is_silently_ignored(bot_pieces):
    _db, _cfg, _sender, bot, replies = bot_pieces
    await bot._handle_update(_msg("999", "/status"))  # wrong chat
    assert replies == []


@pytest.mark.asyncio
async def test_authorized_chat_can_run_help(bot_pieces):
    _db, _cfg, _sender, bot, replies = bot_pieces
    await bot._handle_update(_msg("100", "/help"))
    assert len(replies) == 1
    assert "/status" in replies[0]
    assert "/last_alerts" in replies[0]
    assert "/mute" in replies[0]


# ──────────────────── /status ─────────────────────


@pytest.mark.asyncio
async def test_status_reports_uptime_and_pending(bot_pieces):
    db, _cfg, _sender, bot, replies = bot_pieces
    # Pending message + one alert in history so the snapshot has content.
    await db.execute(
        "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status) "
        "VALUES (1, 'm1', 'OPEN', '{}', ?, 'pending')",
        (int(time.time() * 1000),),
    )
    await db.insert_alert(
        "heartbeat_miss", "slave_1", "missing", "telegram",
        int(time.time() * 1000), 1,
    )
    await bot._handle_update(_msg("100", "/status"))
    assert len(replies) == 1
    assert "pending messages" in replies[0]
    # MarkdownV2 escapes `_` → `\_`, so the raw alert name lands escaped.
    assert "heartbeat\\_miss" in replies[0]


# ──────────────────── /mute ─────────────────────


@pytest.mark.asyncio
async def test_mute_with_duration_writes_until_ms(bot_pieces):
    db, _cfg, _sender, bot, replies = bot_pieces
    before = int(time.time() * 1000)
    await bot._handle_update(_msg("100", "/mute 2h"))
    until = await db.get_mute_until_ms()
    assert until >= before + (2 * 3_600_000) - 1_000
    assert until <= before + (2 * 3_600_000) + 5_000


@pytest.mark.asyncio
async def test_mute_off_clears(bot_pieces):
    db, _cfg, _sender, bot, _replies = bot_pieces
    await db.set_mute_until_ms(int(time.time() * 1000) + 60_000)
    await bot._handle_update(_msg("100", "/mute off"))
    assert await db.get_mute_until_ms() == 0


@pytest.mark.asyncio
async def test_mute_default_one_hour(bot_pieces):
    db, _cfg, _sender, bot, _replies = bot_pieces
    before = int(time.time() * 1000)
    await bot._handle_update(_msg("100", "/mute"))
    until = await db.get_mute_until_ms()
    # ~1h ± 5s of clock skew is fine — the bot computes the deadline itself.
    assert until >= before + 3_600_000 - 5_000


# ──────────────────── /last_alerts ─────────────────────


@pytest.mark.asyncio
async def test_last_alerts_returns_n_rows(bot_pieces):
    db, _cfg, _sender, bot, replies = bot_pieces
    base = int(time.time() * 1000)
    for i in range(5):
        await db.insert_alert(
            "ack_timeout", f"m{i}", f"msg {i}", "telegram", base + i, 1,
        )
    await bot._handle_update(_msg("100", "/last_alerts 3"))
    assert len(replies) == 1
    # Newest first → m4, m3, m2 must appear; m0/m1 must not.
    body = replies[0]
    assert "m4" in body and "m3" in body and "m2" in body
    assert "m0" not in body and "m1" not in body


@pytest.mark.asyncio
async def test_last_alerts_empty_history(bot_pieces):
    _db, _cfg, _sender, bot, replies = bot_pieces
    await bot._handle_update(_msg("100", "/last_alerts"))
    assert len(replies) == 1
    assert "no alerts" in replies[0].lower()
