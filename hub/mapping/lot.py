def compute_slave_volume(master_volume: float, lot_mode: str, lot_value: float) -> float:
    if lot_mode == "multiplier":
        return master_volume * lot_value
    return lot_value  # fixed

def compute_partial_close_volume(
    master_close_volume: float, lot_mode: str, lot_value: float,
    master_open_volume: float, slave_open_volume: float
) -> float:
    if lot_mode == "multiplier":
        return master_close_volume * lot_value
    ratio = master_close_volume / master_open_volume
    return ratio * slave_open_volume
