from hub.mapping.symbol import resolve_symbol

def test_explicit_mapping():
    result = resolve_symbol("XAUUSD", explicit_mappings={"XAUUSD": "GOLD.s"})
    assert result == "GOLD.s"

def test_no_mapping_returns_original():
    result = resolve_symbol("EURUSD", explicit_mappings={})
    assert result == "EURUSD"

def test_explicit_mapping_not_matching_returns_original():
    result = resolve_symbol("EURUSD", explicit_mappings={"XAUUSD": "GOLD.f"})
    assert result == "EURUSD"


def test_resolve_symbol_with_suffix():
    """When no explicit mapping, suffix should be appended."""
    result = resolve_symbol("EURUSD", symbol_suffix=".s", explicit_mappings={})
    assert result == "EURUSD.s"


def test_resolve_symbol_explicit_overrides_suffix():
    """Explicit mapping takes priority over suffix."""
    result = resolve_symbol("XAUUSD", symbol_suffix=".s", explicit_mappings={"XAUUSD": "GOLD.s"})
    assert result == "GOLD.s"


def test_resolve_symbol_no_suffix_no_mapping():
    """No suffix and no mapping — return original symbol."""
    result = resolve_symbol("EURUSD", symbol_suffix="", explicit_mappings={})
    assert result == "EURUSD"
