def resolve_symbol(master_symbol: str, symbol_suffix: str = "", explicit_mappings: dict[str, str] | None = None) -> str:
    if explicit_mappings and master_symbol in explicit_mappings:
        return explicit_mappings[master_symbol]
    if symbol_suffix:
        return master_symbol + symbol_suffix
    return master_symbol
