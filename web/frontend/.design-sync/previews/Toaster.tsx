import { Toaster, toast } from "frontend";
import * as React from "react";

export function Notifications() {
  React.useEffect(() => {
    toast.success("Trade copied to MT5-Slave-A");
    toast.error("MT5-Slave-C disconnected");
    toast.warning("ACK timeout on MT5-Slave-B");
    toast.info("Heartbeat received from master");
  }, []);
  return (
    <Toaster position="top-center" richColors expand visibleToasts={6} duration={1000000} />
  );
}
