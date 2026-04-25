from hub.mapping.magic import parse_master_magic, compute_slave_magic, direction_allowed

def test_parse_master_magic():
    parts = parse_master_magic(15010301)
    assert parts == {"prefix": 15, "pair_id": 1, "direction_block": 3, "setup_id": 1}

def test_parse_master_magic_large():
    parts = parse_master_magic(15990905)
    assert parts == {"prefix": 15, "pair_id": 99, "direction_block": 9, "setup_id": 5}

def test_compute_slave_magic():
    result = compute_slave_magic(15010301, slave_setup_id=5)
    assert result == 15010305

def test_compute_slave_magic_same_setup():
    result = compute_slave_magic(15010301, slave_setup_id=1)
    assert result == 15010301

def test_compute_slave_magic_setup_99():
    result = compute_slave_magic(15010301, slave_setup_id=99)
    assert result == 15010399

def test_direction_allowed_both_permits_any():
    assert direction_allowed("BOTH", "BUY") is True
    assert direction_allowed("BOTH", "SELL") is True

def test_direction_allowed_buy_only_permits_buy():
    assert direction_allowed("BUY", "BUY") is True

def test_direction_allowed_buy_only_blocks_sell():
    assert direction_allowed("BUY", "SELL") is False

def test_direction_allowed_sell_only_permits_sell():
    assert direction_allowed("SELL", "SELL") is True

def test_direction_allowed_sell_only_blocks_buy():
    assert direction_allowed("SELL", "BUY") is False

def test_direction_allowed_empty_direction_passes():
    # CLOSE / MODIFY / SLTP payloads carry no direction — guard is a no-op
    assert direction_allowed("BUY", "") is True
    assert direction_allowed("SELL", "") is True
    assert direction_allowed("BOTH", "") is True
