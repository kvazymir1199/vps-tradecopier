"""Certifi-backed SSL context for every outbound Telegram HTTPS call.

Regression for a field failure: on a fresh Windows VPS the GoDaddy root that
api.telegram.org chains to is often not yet cached in the OS certificate
store (Windows fetches roots lazily via SChannel/Windows Update), so
Python/OpenSSL fails with `self-signed certificate in certificate chain`.
Delivery must therefore rely on a CA bundle we ship (certifi), not on
whatever roots the OS store happens to have cached.

Call-site tests intercept `httpx.AsyncClient` (all three senders build one
with `verify=telegram_ssl_context()`) and assert an SSLContext reaches the
`verify` argument.
"""

from __future__ import annotations

import ssl
import time
from pathlib import Path

import certifi
import httpx
import pytest
from httpx import ASGITransport

import web.api.database as database
from hub.config import ALERT_TYPES
from hub.db.manager import DatabaseManager
from hub.monitor.alerts import AlertSender
from hub.monitor.health import HealthChecker
from hub.monitor.telegram_bot import TelegramBot
from web.api.main import create_app

from tests.test_telegram_bot import FakeConfig, FakeTelegram


def _certifi_cert_count() -> int:
    pem = Path(certifi.where()).read_text(encoding="ascii", errors="ignore")
    return pem.count("BEGIN CERTIFICATE")


@pytest.fixture
def captured_httpx(monkeypatch):
    """Intercept the httpx.AsyncClient our Telegram senders build.

    Production code constructs `httpx.AsyncClient(verify=telegram_ssl_context())`
    and then calls .post()/.get(). We capture the `verify` kwarg and hand back
    canned 200 responses so no network is touched. The API test drives the app
    through its own client built with `transport=ASGITransport(...)`; those are
    delegated to the real httpx client so the ASGI request still works.
    """
    captured: dict = {}
    real_client = httpx.AsyncClient

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["verify"] = kwargs.get("verify")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            captured["post_url"] = url
            captured["post_kwargs"] = kwargs
            # Attach a request so resp.raise_for_status() works like the real one.
            return httpx.Response(
                200,
                json={"ok": True, "result": []},
                request=httpx.Request("POST", url),
            )

        async def get(self, url, **kwargs):
            captured["get_url"] = url
            captured["get_kwargs"] = kwargs
            return httpx.Response(
                200,
                json={"ok": True, "result": []},
                request=httpx.Request("GET", url),
            )

    def _factory(*args, **kwargs):
        # The test's own ASGI client passes transport=; delegate those to the
        # real client. Production senders pass verify=; intercept those.
        if "transport" in kwargs:
            return real_client(*args, **kwargs)
        return _FakeAsyncClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    return captured


# ───────────────────── context factory ─────────────────────


def test_context_enforces_verification():
    from hub.monitor.alerts import telegram_ssl_context

    ctx = telegram_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_context_carries_at_least_the_certifi_bundle():
    from hub.monitor.alerts import telegram_ssl_context

    # The context must hold the entire shipped bundle so delivery does not
    # depend on which roots the OS store has cached on a given VPS.
    ctx = telegram_ssl_context()
    assert len(ctx.get_ca_certs()) >= _certifi_cert_count()


def test_context_trusts_godaddy_root():
    from hub.monitor.alerts import telegram_ssl_context

    # api.telegram.org chains to GoDaddy Root Certificate Authority - G2.
    ctx = telegram_ssl_context()
    assert any(
        "Go Daddy Root Certificate Authority - G2" in str(ca)
        for ca in ctx.get_ca_certs()
    )


# ───────────────────── call sites ─────────────────────


@pytest.mark.asyncio
async def test_alert_sender_posts_with_ssl_context(captured_httpx):
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig(telegram=FakeTelegram(bot_token="t", chat_id="c"))
    sender = AlertSender(db, cfg)

    await sender._post_message("test body")

    assert isinstance(captured_httpx["verify"], ssl.SSLContext)
    await db.close()


@pytest.mark.asyncio
async def test_bot_get_updates_uses_ssl_context(captured_httpx):
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig()
    sender = AlertSender(db, cfg)
    hc = HealthChecker(db, cfg, resend_callback=lambda *_: None)
    bot = TelegramBot(
        db, cfg, sender, hc, hub_started_at_ms=int(time.time() * 1000)
    )

    updates = await bot._get_updates()

    assert updates == []
    assert isinstance(captured_httpx["verify"], ssl.SSLContext)
    await db.close()


@pytest.mark.asyncio
async def test_api_test_endpoint_uses_ssl_context(tmp_path, captured_httpx):
    db_path = str(tmp_path / "test.db")
    mgr = DatabaseManager(db_path)
    await mgr.initialize()
    await mgr.seed_config_defaults()
    await mgr.close()

    database.DB_PATH = db_path
    app = create_app()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        r = await client.put(
            "/api/telegram", json={"bot_token": "t", "chat_id": "c"}
        )
        assert r.status_code == 200

        r = await client.post("/api/telegram/test")
        assert r.status_code == 200
        assert r.json()["delivered"] is True

    assert isinstance(captured_httpx["verify"], ssl.SSLContext)
