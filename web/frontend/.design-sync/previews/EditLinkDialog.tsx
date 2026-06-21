import { EditLinkDialog } from "frontend";

const link = {
  id: 1,
  master_id: "MT5-Master-01",
  slave_id: "MT5-Slave-A",
  lot_mode: "multiplier",
  lot_value: 1.5,
  enabled: 1,
  created_at: 0,
};

export function Open() {
  return (
    <EditLinkDialog open link={link} onOpenChange={() => {}} onSubmit={async () => {}} />
  );
}
