from hub.config import Config


def test_load_config(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"db_path": "test.db", "vps_id": "vps_1", "telegram": {"enabled": false, "bot_token": "", "chat_id": ""}}')
    cfg = Config.load(config_file)
    assert cfg.db_path == "test.db"
    assert cfg.vps_id == "vps_1"
    assert cfg.heartbeat_timeout_sec == 30  # default
    assert cfg.telegram.enabled is False


def test_load_config_with_all_fields(tmp_path):
    import json
    data = {
        "db_path": "copier.db",
        "vps_id": "vps_2",
        "heartbeat_interval_sec": 5,
        "heartbeat_timeout_sec": 15,
        "ack_timeout_sec": 3,
        "ack_max_retries": 5,
        "resend_window_size": 100,
        "alert_dedup_minutes": 10,
        "telegram": {"enabled": True, "bot_token": "TOKEN", "chat_id": "123"},
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))
    cfg = Config.load(config_file)
    assert cfg.heartbeat_interval_sec == 5
    assert cfg.ack_max_retries == 5
    assert cfg.telegram.bot_token == "TOKEN"
