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
