from hub.config import Config, DB_PATH


def test_from_db_defaults():
    """Config.from_db with default values (empty dict)."""
    cfg = Config.from_db({})
    assert cfg.db_path == DB_PATH
    assert cfg.vps_id == "vps_1"
    assert cfg.heartbeat_interval_sec == 10
    assert cfg.heartbeat_timeout_sec == 30  # default
    assert cfg.ack_timeout_sec == 5
    assert cfg.ack_max_retries == 3
    assert cfg.resend_window_size == 200
    assert cfg.alert_dedup_minutes == 5
    assert cfg.telegram.enabled is False
    assert cfg.telegram.bot_token == ""
    assert cfg.telegram.chat_id == ""


def test_from_db_with_all_fields():
    """Config.from_db with all fields from DB."""
    data = {
        "vps_id": "vps_2",
        "heartbeat_interval_sec": "5",
        "heartbeat_timeout_sec": "15",
        "ack_timeout_sec": "3",
        "ack_max_retries": "5",
        "resend_window_size": "100",
        "alert_dedup_minutes": "10",
        "telegram_enabled": "true",
        "telegram_bot_token": "TOKEN",
        "telegram_chat_id": "123",
    }
    cfg = Config.from_db(data)
    assert cfg.db_path == DB_PATH
    assert cfg.vps_id == "vps_2"
    assert cfg.heartbeat_interval_sec == 5
    assert cfg.heartbeat_timeout_sec == 15
    assert cfg.ack_timeout_sec == 3
    assert cfg.ack_max_retries == 5
    assert cfg.resend_window_size == 100
    assert cfg.alert_dedup_minutes == 10
    assert cfg.telegram.enabled is True
    assert cfg.telegram.bot_token == "TOKEN"
    assert cfg.telegram.chat_id == "123"
