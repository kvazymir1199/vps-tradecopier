import { MappingsPanel } from "frontend";

// Offline mock so the panel shows realistic symbol + magic mappings.
const symbolMappings = [
  { id: 1, link_id: 1, master_symbol: "EURUSD", slave_symbol: "EURUSD.raw" },
  { id: 2, link_id: 1, master_symbol: "XAUUSD", slave_symbol: "XAUUSD.raw" },
];
const magicMappings = [
  { id: 1, link_id: 1, master_setup_id: 101, slave_setup_id: 205, allowed_direction: "BOTH" },
  { id: 2, link_id: 1, master_setup_id: 102, slave_setup_id: 206, allowed_direction: "BUY" },
];
const suggestions = {
  master_id: "MT5-Master-01",
  slave_id: "MT5-Slave-A",
  suggestions: [
    { master_symbol: "EURUSD", slave_symbol: "EURUSD.raw", status: "mapped" },
    { master_symbol: "XAUUSD", slave_symbol: "XAUUSD.raw", status: "auto" },
    { master_symbol: "GBPUSD", slave_symbol: null, status: "unmapped" },
  ],
  slave_symbols: ["EURUSD.raw", "XAUUSD.raw", "GBPUSD.raw", "USDJPY.raw"],
};

if (typeof window !== "undefined" && !(window as Window & { __dsFetch?: boolean }).__dsFetch) {
  (window as Window & { __dsFetch?: boolean }).__dsFetch = true;
  const json = (d: unknown) => new Response(JSON.stringify(d), { status: 200, headers: { "Content-Type": "application/json" } });
  window.fetch = async (input: RequestInfo | URL) => {
    const u = String(input);
    if (u.includes("/symbol-mappings/suggestions")) return json(suggestions);
    if (u.includes("/magic-mappings")) return json(magicMappings);
    if (u.includes("/symbol-mappings")) return json(symbolMappings);
    return json([]);
  };
}

export function Open() {
  return <MappingsPanel linkId={1} open onOpenChange={() => {}} />;
}
