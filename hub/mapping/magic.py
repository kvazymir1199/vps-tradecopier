def parse_master_magic(magic: int) -> dict:
    s = str(magic)
    return {
        "prefix": int(s[0:2]),
        "pair_id": int(s[2:4]),
        "direction_block": int(s[4:6]),
        "setup_id": int(s[6:8]),
    }

def compute_slave_magic(master_magic: int, slave_setup_id: int) -> int:
    return master_magic - (master_magic % 100) + slave_setup_id
