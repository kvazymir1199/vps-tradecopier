export interface Terminal {
  terminal_id: string;
  role: "master" | "slave";
  account_number: number | null;
  broker_server: string | null;
  status: string;
  status_message: string;
  last_heartbeat: number;
}

export interface Link {
  id: number;
  master_id: string;
  slave_id: string;
  enabled: number;
  lot_mode: "multiplier" | "fixed";
  lot_value: number;
  symbol_suffix: string;
  created_at: number;
}

export interface SymbolMapping {
  id: number;
  link_id: number;
  master_symbol: string;
  slave_symbol: string;
}

export interface MagicMapping {
  id: number;
  link_id: number;
  master_setup_id: number;
  slave_setup_id: number;
}
