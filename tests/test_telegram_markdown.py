"""MarkdownV2 validity of every outbound Telegram message.

Regression suite for the stability-run bug where `/status` replies failed
with HTTP 400 ("character '(' is reserved and must be escaped"): the
terminals line interpolated literal parentheses without escaping them.

The validator below mimics the two Bot API parsing rules that matter for
our messages (https://core.telegram.org/bots/api#markdownv2-style):

  1. Outside code entities every reserved character that is not an entity
     marker (* _ ~ `) must be backslash-escaped. A bare `(`, `.`, `-` etc.
     makes the whole sendMessage call fail with 400.
  2. Inside `code` entities only '`' and '\\' may be escaped. Any other
     backslash is rendered literally, so escaping there is a visible
     formatting defect (e.g. `2026\\-07\\-10` shown to the operator).
"""

import time
from dataclasses import dataclass, field

import pytest

from hub.config import ALERT_TYPES
from hub.db.manager import DatabaseManager
from hub.monitor.alerts import AlertSender, format_markdown_v2
from hub.monitor.health import HealthChecker
from hub.monitor.telegram_bot import TelegramBot

# Reserved MarkdownV2 chars that are never entity markers: unescaped
# occurrences outside code spans always produce a 400 from Telegram.
_ALWAYS_RESERVED = set("()[]{}#+-=|.!>")


def find_markdown_v2_violations(text: str) -> list[str]:
    """Return human-readable violations; empty list == message is safe."""
    violations: list[str] = []
    in_code = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "`":
            in_code = not in_code
            i += 1
            continue
        if in_code:
            if ch == "\\":
                violations.append(
                    f"pos {i}: backslash inside code span renders literally: "
                    f"...{text[max(0, i - 15):i + 15]!r}..."
                )
            i += 1
            continue
        if ch == "\\":
            i += 2  # escape sequence — consumes the next char
            continue
        if ch in _ALWAYS_RESERVED:
            violations.append(
                f"pos {i}: unescaped {ch!r}: "
                f"...{text[max(0, i - 15):i + 15]!r}..."
            )
            i += 1
            continue
        i += 1
    if in_code:
        violations.append("unbalanced '`' — code span never closed")
    return violations


def assert_valid_markdown_v2(text: str) -> None:
    violations = find_markdown_v2_violations(text)
    assert not violations, "MarkdownV2 violations:\n" + "\n".join(violations)


# ─────────────────────── validator self-test ───────────────────────


def test_validator_catches_unescaped_paren():
    assert find_markdown_v2_violations("slave_1(s)")
    assert not find_markdown_v2_violations("slave\\_1\\(s\\)")


def test_validator_catches_backslash_inside_code():
    assert find_markdown_v2_violations("`2026\\-07\\-10`")
    assert not find_markdown_v2_violations("`2026-07-10`")


def test_validator_accepts_plain_entities():
    assert not find_markdown_v2_violations("*bold* _italic_ `code (raw)`")


# ─────────────────────── bot reply fixtures ───────────────────────


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


def _msg(text: str) -> dict:
    return {"update_id": 1, "message": {"chat": {"id": 100}, "text": text}}


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
    yield db, bot, replies
    await db.close()


async def _populate_realistic_state(db: DatabaseManager) -> None:
    """Two masters + five slaves online, alerts in history — the exact shape
    of the VPS stability run where the live 400s were observed."""
    for tid, role in [
        ("master_1715542650", "master"),
        ("master_67185418", "master"),
        ("slave_168935786", "slave"),
        ("slave_52953732", "slave"),
        ("slave_591823116", "slave"),
        ("slave_67185418", "slave"),
        ("slave_7833734", "slave"),
    ]:
        await db.register_terminal(tid, role, 1, "Broker (Demo) Ltd.")
    now = int(time.time() * 1000)
    for i, at in enumerate(["consecutive_nacks", "slave_disconnected", "heartbeat_miss"]):
        await db.insert_alert(at, "slave_52953732", f"msg {i}", "telegram", now + i, 1)


# ─────────────────────── the regression tests ───────────────────────


@pytest.mark.asyncio
async def test_status_reply_is_valid_markdown_v2(bot_pieces):
    """Live bug: '/status' with online terminals returned terminals_line
    like 'master_1715542650(m), ...' — unescaped parens → HTTP 400."""
    db, bot, replies = bot_pieces
    await _populate_realistic_state(db)
    await bot._handle_update(_msg("/status"))
    assert len(replies) == 1
    assert_valid_markdown_v2(replies[0])


@pytest.mark.asyncio
async def test_status_reply_with_more_than_10_terminals(bot_pieces):
    db, bot, replies = bot_pieces
    for i in range(12):
        await db.register_terminal(f"slave_{i}", "slave", i, "B")
    await bot._handle_update(_msg("/status"))
    assert_valid_markdown_v2(replies[0])
    assert "more" in replies[0]


@pytest.mark.asyncio
async def test_last_alerts_reply_is_valid_markdown_v2(bot_pieces):
    db, bot, replies = bot_pieces
    await _populate_realistic_state(db)
    await bot._handle_update(_msg("/last_alerts 3"))
    assert len(replies) == 1
    assert_valid_markdown_v2(replies[0])


@pytest.mark.asyncio
async def test_mute_replies_are_valid_markdown_v2(bot_pieces):
    _db, bot, replies = bot_pieces
    await bot._handle_update(_msg("/mute 30m"))
    await bot._handle_update(_msg("/mute garbage"))
    await bot._handle_update(_msg("/mute off"))
    assert len(replies) == 3
    for body in replies:
        assert_valid_markdown_v2(body)


@pytest.mark.asyncio
async def test_help_reply_is_valid_markdown_v2(bot_pieces):
    _db, bot, replies = bot_pieces
    await bot._handle_update(_msg("/help"))
    assert_valid_markdown_v2(replies[0])


# ─────────────────────── alert bodies ───────────────────────


def test_alert_body_is_valid_markdown_v2():
    """format_markdown_v2 must stay valid for hostile inputs (broker names
    with dots/parens, NACK reasons with symbols) and must not over-escape
    inside the `fired at:` code span."""
    body = format_markdown_v2(
        alert_type="consecutive_nacks",
        terminal_id="slave_52911415",
        broker="Raw Trading Ltd. (IC Markets)",
        message="NACK burst: 6 consecutive NACKs in last 60 s. "
                "Last reason: ORDER_FAILED (XAUUSD.s)",
        fired_at_ms=int(time.time() * 1000),
    )
    assert_valid_markdown_v2(body)


def test_alert_body_without_terminal_and_broker():
    body = format_markdown_v2(
        alert_type="hub_started",
        terminal_id=None,
        broker=None,
        message="Hub started — vps=vps_1, pipes=14, masters=2, slaves=6",
        fired_at_ms=int(time.time() * 1000),
    )
    assert_valid_markdown_v2(body)
