import os
from dataclasses import dataclass

# Fixed DB path — always in MQL5 Common Files
DB_PATH = os.path.join(
    os.environ.get("APPDATA", ""),
    "MetaQuotes", "Terminal", "Common", "Files",
    "TradeCopier", "copier.db",
)


@dataclass
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str


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
            ),
        )
