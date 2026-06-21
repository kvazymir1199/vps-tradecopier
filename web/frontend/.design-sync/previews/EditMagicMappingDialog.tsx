import { EditMagicMappingDialog } from "frontend";

const mapping = {
  id: 1,
  link_id: 1,
  master_setup_id: 101,
  slave_setup_id: 205,
  allowed_direction: "BOTH",
};

export function Open() {
  return (
    <EditMagicMappingDialog
      open
      mapping={mapping}
      onOpenChange={() => {}}
      onSubmit={async () => {}}
    />
  );
}
