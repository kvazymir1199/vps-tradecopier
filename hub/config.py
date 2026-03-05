import json
from dataclasses import dataclass
from pathlib import Path


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
    def load(cls, path: str | Path) -> "Config":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            db_path=data["db_path"],
            vps_id=data["vps_id"],
            heartbeat_interval_sec=data.get("heartbeat_interval_sec", 10),
            heartbeat_timeout_sec=data.get("heartbeat_timeout_sec", 30),
            ack_timeout_sec=data.get("ack_timeout_sec", 5),
            ack_max_retries=data.get("ack_max_retries", 3),
            resend_window_size=data.get("resend_window_size", 200),
            alert_dedup_minutes=data.get("alert_dedup_minutes", 5),
            telegram=TelegramConfig(
                enabled=data.get("telegram", {}).get("enabled", False),
                bot_token=data.get("telegram", {}).get("bot_token", ""),
                chat_id=data.get("telegram", {}).get("chat_id", ""),
            ),
        )
