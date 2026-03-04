from hub.mapping.symbol import resolve_symbol

def test_suffix_mapping():
    result = resolve_symbol("EURUSD", suffix=".s", explicit_mappings={})
    assert result == "EURUSD.s"

def test_explicit_mapping_overrides_suffix():
    result = resolve_symbol("XAUUSD", suffix=".s", explicit_mappings={"XAUUSD": "GOLD.s"})
    assert result == "GOLD.s"

def test_empty_suffix():
    result = resolve_symbol("EURUSD", suffix="", explicit_mappings={})
    assert result == "EURUSD"

def test_suffix_with_underscore():
    result = resolve_symbol("GBPUSD", suffix="_demo", explicit_mappings={})
    assert result == "GBPUSD_demo"

def test_explicit_mapping_not_matching_falls_to_suffix():
    result = resolve_symbol("EURUSD", suffix=".f", explicit_mappings={"XAUUSD": "GOLD.f"})
    assert result == "EURUSD.f"
