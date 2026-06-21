import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
  Badge,
} from "frontend";

export function LinksOverview() {
  const rows = [
    { master: "MT5-Master-01", slave: "MT5-Slave-A", mode: "multiplier", value: "1.0", on: true },
    { master: "MT5-Master-01", slave: "MT5-Slave-B", mode: "fixed", value: "0.10", on: true },
    { master: "MT5-Master-02", slave: "MT5-Slave-C", mode: "multiplier", value: "2.5", on: false },
  ];
  return (
    <Table>
      <TableCaption>Active copy links between terminals</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Master</TableHead>
          <TableHead>Slave</TableHead>
          <TableHead>Lot Mode</TableHead>
          <TableHead>Lot Value</TableHead>
          <TableHead>Enabled</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.slave}>
            <TableCell style={{ fontWeight: 500 }}>{r.master}</TableCell>
            <TableCell>{r.slave}</TableCell>
            <TableCell>{r.mode}</TableCell>
            <TableCell>{r.value}</TableCell>
            <TableCell>
              <Badge variant={r.on ? "default" : "outline"}>{r.on ? "On" : "Off"}</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function TerminalsOverview() {
  const rows = [
    { id: "MT5-Master-01", role: "master", account: "5012933", broker: "Pepperstone-Live", status: "Active" },
    { id: "MT5-Slave-A", role: "slave", account: "5099210", broker: "Pepperstone-Live", status: "Connected" },
    { id: "MT5-Slave-C", role: "slave", account: "5099477", broker: "Pepperstone-Demo", status: "Disconnected" },
  ];
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Terminal ID</TableHead>
          <TableHead>Role</TableHead>
          <TableHead>Account</TableHead>
          <TableHead>Broker</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.id}>
            <TableCell style={{ fontWeight: 500 }}>{r.id}</TableCell>
            <TableCell>{r.role}</TableCell>
            <TableCell>{r.account}</TableCell>
            <TableCell>{r.broker}</TableCell>
            <TableCell>{r.status}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
