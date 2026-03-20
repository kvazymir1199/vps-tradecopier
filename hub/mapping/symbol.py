def resolve_symbol(master_symbol: str, explicit_mappings: dict[str, str]) -> str:
    if master_symbol in explicit_mappings:
        return explicit_mappings[master_symbol]
    return master_symbol
