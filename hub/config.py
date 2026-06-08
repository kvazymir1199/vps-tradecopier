import os
from dataclasses import dataclass, field

# Fixed DB path — always in MQL5 Common Files
DB_PATH = os.path.join(
    os.environ.get("APPDATA", ""),
    "MetaQuotes", "Terminal", "Common", "Files",
    "TradeCopier", "copier.db",
)

# Canonical alert type identifiers used across Hub, DB and UI.
# Adding a new alert type? Add it here AND in DatabaseManager.seed_config_defaults()
# under the `alert_enabled_<type>` keys, AND wire its trigger in HealthChecker/main.
ALERT_TYPES: tuple[str, ...] = (
    "heartbeat_miss",
    "ack_timeout",
    "consecutive_nacks",
    "queue_depth",
    "slave_disconnected",
    "hub_started",
    "trade_copied",
    "daily_summary",
    "alert_storm",
)


@dataclass
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str
    daily_summary_time: str = "08:00"
    alert_storm_threshold: int = 10
    alerts_retention_days: int = 90
    alert_enabled: dict[str, bool] = field(default_factory=dict)


@dataclass
class Config:
    db_path: str
    vps_id: str
    heartbeat_interval_sec: int
    heartbeat_timeout_sec: int
    ack_timeout_sec: int
    ack_max_retries: int
    resend_window_size: int
    alert_dedup_minutes: int
    telegram: TelegramConfig

    @classmethod
    def from_db(cls, data: dict[str, str]) -> "Config":
        alert_enabled: dict[str, bool] = {}
        for at in ALERT_TYPES:
            key = f"alert_enabled_{at}"
            alert_enabled[at] = data.get(key, "true").lower() == "true"
        return cls(
            db_path=DB_PATH,
            vps_id=data.get("vps_id", "vps_1"),
            heartbeat_interval_sec=int(data.get("heartbeat_interval_sec", "10")),
            heartbeat_timeout_sec=int(data.get("heartbeat_timeout_sec", "30")),
            ack_timeout_sec=int(data.get("ack_timeout_sec", "5")),
            ack_max_retries=int(data.get("ack_max_retries", "3")),
            resend_window_size=int(data.get("resend_window_size", "200")),
            alert_dedup_minutes=int(data.get("alert_dedup_minutes", "5")),
            telegram=TelegramConfig(
                enabled=data.get("telegram_enabled", "false").lower() == "true",
                bot_token=data.get("telegram_bot_token", ""),
                chat_id=data.get("telegram_chat_id", ""),
                daily_summary_time=data.get("telegram_daily_summary_time", "08:00"),
                alert_storm_threshold=int(data.get("telegram_alert_storm_threshold", "10")),
                alerts_retention_days=int(data.get("telegram_alerts_retention_days", "90")),
                alert_enabled=alert_enabled,
            ),
        )
