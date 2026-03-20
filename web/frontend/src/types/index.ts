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

export interface SymbolSuggestion {
  master_symbol: string;
  slave_symbol: string | null;
  status: "mapped" | "auto" | "unmapped";
}

export interface SymbolSuggestionsResponse {
  master_id: string;
  slave_id: string;
  suggestions: SymbolSuggestion[];
  slave_symbols: string[];
}

export interface Config {
  vps_id: string;
  heartbeat_interval_sec: number;
  heartbeat_timeout_sec: number;
  ack_timeout_sec: number;
  ack_max_retries: number;
  resend_window_size: number;
  alert_dedup_minutes: number;
  telegram_enabled: boolean;
  telegram_bot_token: string;
  telegram_chat_id: string;
}
