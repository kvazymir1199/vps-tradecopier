def resolve_symbol(master_symbol: str, suffix: str, explicit_mappings: dict[str, str]) -> str:
    if master_symbol in explicit_mappings:
        return explicit_mappings[master_symbol]
    if not suffix:
        return master_symbol
    if suffix.startswith("."):
        return master_symbol + suffix
    return master_symbol + "." + suffix
