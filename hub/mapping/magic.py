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


def direction_allowed(direction_block: int, direction: str) -> bool:
    """Check if the magic number's direction_block permits the given trade direction.

    direction_block == 0 means the setup is unrestricted (trades both ways).
    The encoding convention for non-zero blocks must be confirmed with the client
    before this guard is enabled in the router.

    Placeholder implementation: all non-zero blocks are also treated as unrestricted
    until the convention is documented.
    """
    if not direction:
        return True
    if direction_block == 0:
        return True
    # TODO: replace with actual convention once confirmed, e.g.:
    # if direction_block % 2 == 0:
    #     return direction == "BUY"
    # return direction == "SELL"
    return True
