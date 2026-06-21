import { AddLinkDialog } from "frontend";

const terminals = [
  { terminal_id: "MT5-Master-01", role: "master", status: "Active", broker_server: "Pepperstone-Live" },
  { terminal_id: "MT5-Master-02", role: "master", status: "Active", broker_server: "Pepperstone-Live" },
  { terminal_id: "MT5-Slave-A", role: "slave", status: "Connected", broker_server: "Pepperstone-Live" },
  { terminal_id: "MT5-Slave-B", role: "slave", status: "Connected", broker_server: "Pepperstone-Demo" },
];

export function Open() {
  return (
    <AddLinkDialog
      open
      terminals={terminals}
      onOpenChange={() => {}}
      onSubmit={async () => {}}
    />
  );
}
