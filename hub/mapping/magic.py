def parse_master_magic(magic: int) -> dict:
    if magic == 0:
        return {"prefix": 0, "pair_id": 0, "direction_block": 0, "setup_id": 0}
    s = str(magic)
    return {
        "prefix": int(s[0:2]) if len(s) >= 2 else int(s),
        "pair_id": int(s[2:4]) if len(s) >= 4 else 0,
        "direction_block": int(s[4:6]) if len(s) >= 6 else 0,
        "setup_id": int(s[6:8]) if len(s) >= 8 else 0,
    }

def compute_slave_magic(master_magic: int, slave_setup_id: int) -> int:
    return master_magic - (master_magic % 100) + slave_setup_id
