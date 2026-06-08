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

export type AllowedDirection = "BUY" | "SELL" | "BOTH";

export interface MagicMapping {
  id: number;
  link_id: number;
  master_setup_id: number;
  slave_setup_id: number;
  allowed_direction: AllowedDirection;
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

export type AlertType =
  | "heartbeat_miss"
  | "ack_timeout"
  | "consecutive_nacks"
  | "queue_depth"
  | "slave_disconnected"
  | "hub_started"
  | "trade_copied"
  | "daily_summary"
  | "alert_storm";

export interface TelegramSettings {
  enabled: boolean;
  bot_token: string;
  chat_id: string;
  daily_summary_time: string;
  alert_storm_threshold: number;
  alerts_retention_days: number;
  alert_dedup_minutes: number;
  mute_until_ms: number;
  alert_enabled: Record<AlertType, boolean>;
}

export type TelegramSettingsUpdate = Partial<
  Omit<TelegramSettings, "mute_until_ms">
>;

export interface AlertRecord {
  id: number;
  alert_type: AlertType | string;
  terminal_id: string | null;
  message: string;
  channel: "telegram" | "email";
  sent_at: number;
  delivered: number;
  retry_count: number;
  deduplicated: number;
  muted: number;
}
