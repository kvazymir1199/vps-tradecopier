import { AddMappingDialog } from "frontend";

export function SymbolMapping() {
  return <AddMappingDialog type="symbol" open onOpenChange={() => {}} onSubmit={async () => {}} />;
}

export function MagicMapping() {
  return <AddMappingDialog type="magic" open onOpenChange={() => {}} onSubmit={async () => {}} />;
}
