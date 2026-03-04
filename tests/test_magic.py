from hub.mapping.magic import parse_master_magic, compute_slave_magic

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
