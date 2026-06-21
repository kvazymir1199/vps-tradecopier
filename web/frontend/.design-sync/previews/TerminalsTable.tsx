import { TerminalsTable } from "frontend";

// Offline mock so the card shows realistic rows instead of the empty state.
const terminals = [
  { terminal_id: "MT5-Master-01", role: "master", account_number: 5012933, broker_server: "Pepperstone-Live", status: "Active", status_message: "OK", last_heartbeat: Date.now() - 3000 },
  { terminal_id: "MT5-Slave-A", role: "slave", account_number: 5099210, broker_server: "Pepperstone-Live", status: "Connected", status_message: "OK", last_heartbeat: Date.now() - 8000 },
  { terminal_id: "MT5-Slave-C", role: "slave", account_number: 5099477, broker_server: "Pepperstone-Demo", status: "Disconnected", status_message: "No heartbeat", last_heartbeat: Date.now() - 240000 },
];

if (typeof window !== "undefined" && !(window as Window & { __dsFetch?: boolean }).__dsFetch) {
  (window as Window & { __dsFetch?: boolean }).__dsFetch = true;
  const json = (d: unknown) => new Response(JSON.stringify(d), { status: 200, headers: { "Content-Type": "application/json" } });
  window.fetch = async (input: RequestInfo | URL) => {
    const u = String(input);
    if (u.includes("/terminals")) return json(terminals);
    return json([]);
  };
}

export function Overview() {
  return <TerminalsTable />;
}
