from hub.mapping.lot import compute_slave_volume, compute_partial_close_volume

def test_multiplier_mode():
    assert compute_slave_volume(0.1, "multiplier", 2.0) == 0.2

def test_fixed_mode():
    assert compute_slave_volume(0.1, "fixed", 0.05) == 0.05

def test_multiplier_mode_large():
    assert compute_slave_volume(1.0, "multiplier", 0.5) == 0.5

def test_partial_close_multiplier():
    vol = compute_partial_close_volume(
        master_close_volume=0.05, lot_mode="multiplier", lot_value=2.0,
        master_open_volume=0.1, slave_open_volume=0.2)
    assert vol == 0.1

def test_partial_close_fixed():
    vol = compute_partial_close_volume(
        master_close_volume=0.05, lot_mode="fixed", lot_value=0.1,
        master_open_volume=0.1, slave_open_volume=0.1)
    assert vol == 0.05
