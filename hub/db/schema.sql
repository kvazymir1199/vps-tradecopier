PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- 1. terminals
CREATE TABLE IF NOT EXISTS terminals (
    terminal_id     TEXT    PRIMARY KEY,
    role            TEXT    NOT NULL CHECK (role IN ('master', 'slave')),
    account_number  INTEGER,
    broker_server   TEXT,
    status          TEXT    NOT NULL DEFAULT 'Starting'
                           CHECK (status IN (
                               'Starting', 'Connected', 'Syncing',
                               'Active', 'Paused', 'Disconnected', 'Error'
                           )),
    status_message  TEXT    DEFAULT '',
    created_at      INTEGER NOT NULL,
    last_heartbeat  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_terminals_role ON terminals(role);
CREATE INDEX IF NOT EXISTS idx_terminals_status ON terminals(status);

-- 2. master_slave_links
CREATE TABLE IF NOT EXISTS master_slave_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id       TEXT    NOT NULL REFERENCES terminals(terminal_id),
    slave_id        TEXT    NOT NULL REFERENCES terminals(terminal_id),
    enabled         INTEGER NOT NULL DEFAULT 1,
    lot_mode        TEXT    NOT NULL DEFAULT 'multiplier'
                           CHECK (lot_mode IN ('multiplier', 'fixed')),
    lot_value       REAL    NOT NULL DEFAULT 1.0,
    symbol_suffix   TEXT    DEFAULT '',
    created_at      INTEGER NOT NULL,

    UNIQUE(master_id, slave_id)
);

CREATE INDEX IF NOT EXISTS idx_links_master ON master_slave_links(master_id);
CREATE INDEX IF NOT EXISTS idx_links_slave ON master_slave_links(slave_id);
CREATE INDEX IF NOT EXISTS idx_links_enabled ON master_slave_links(enabled);

-- 3. symbol_mappings
CREATE TABLE IF NOT EXISTS symbol_mappings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id         INTEGER NOT NULL REFERENCES master_slave_links(id) ON DELETE CASCADE,
    master_symbol   TEXT    NOT NULL,
    slave_symbol    TEXT    NOT NULL,

    UNIQUE(link_id, master_symbol)
);

CREATE INDEX IF NOT EXISTS idx_sym_link ON symbol_mappings(link_id);
CREATE INDEX IF NOT EXISTS idx_sym_master ON symbol_mappings(master_symbol);

-- 4. magic_mappings
CREATE TABLE IF NOT EXISTS magic_mappings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id           INTEGER NOT NULL REFERENCES master_slave_links(id) ON DELETE CASCADE,
    master_setup_id   INTEGER NOT NULL,
    slave_setup_id    INTEGER NOT NULL,

    UNIQUE(link_id, master_setup_id)
);

CREATE INDEX IF NOT EXISTS idx_magic_link ON magic_mappings(link_id);

-- 5. trade_mappings
CREATE TABLE IF NOT EXISTS trade_mappings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id       TEXT    NOT NULL,
    slave_id        TEXT    NOT NULL,
    master_ticket   INTEGER NOT NULL,
    slave_ticket    INTEGER,
    master_magic    INTEGER NOT NULL,
    slave_magic     INTEGER NOT NULL,
    symbol          TEXT    NOT NULL,
    master_volume   REAL    NOT NULL,
    slave_volume    REAL    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'open', 'partial_closed', 'closed', 'failed')),
    created_at      INTEGER NOT NULL,
    closed_at       INTEGER,

    UNIQUE(master_id, slave_id, master_ticket)
);

CREATE INDEX IF NOT EXISTS idx_trade_master ON trade_mappings(master_id, master_ticket);
CREATE INDEX IF NOT EXISTS idx_trade_slave ON trade_mappings(slave_id, slave_ticket);
CREATE INDEX IF NOT EXISTS idx_trade_status ON trade_mappings(status);
CREATE INDEX IF NOT EXISTS idx_trade_magic ON trade_mappings(master_magic);

-- 6. messages
CREATE TABLE IF NOT EXISTS messages (
    msg_id          INTEGER NOT NULL,
    master_id       TEXT    NOT NULL,
    type            TEXT    NOT NULL CHECK (type IN (
                        'OPEN', 'MODIFY', 'CLOSE', 'CLOSE_PARTIAL',
                        'HEARTBEAT', 'REGISTER'
                    )),
    payload         TEXT    NOT NULL,
    ts_ms           INTEGER NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'sent', 'acked', 'nacked', 'expired')),

    PRIMARY KEY (master_id, msg_id)
);

CREATE INDEX IF NOT EXISTS idx_msg_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_msg_ts ON messages(ts_ms);
CREATE INDEX IF NOT EXISTS idx_msg_type ON messages(type);

-- 7. message_acks
CREATE TABLE IF NOT EXISTS message_acks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id          INTEGER NOT NULL,
    master_id       TEXT    NOT NULL,
    slave_id        TEXT    NOT NULL,
    ack_type        TEXT    NOT NULL CHECK (ack_type IN ('ACK', 'NACK')),
    nack_reason     TEXT,
    slave_ticket    INTEGER,
    ts_ms           INTEGER NOT NULL,

    FOREIGN KEY (master_id, msg_id) REFERENCES messages(master_id, msg_id)
);

CREATE INDEX IF NOT EXISTS idx_ack_msg ON message_acks(master_id, msg_id);
CREATE INDEX IF NOT EXISTS idx_ack_slave ON message_acks(slave_id);
CREATE INDEX IF NOT EXISTS idx_ack_type ON message_acks(ack_type);

-- 8. heartbeats
CREATE TABLE IF NOT EXISTS heartbeats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    terminal_id     TEXT    NOT NULL REFERENCES terminals(terminal_id),
    vps_id          TEXT    NOT NULL,
    ts_ms           INTEGER NOT NULL,
    status_code     INTEGER NOT NULL,
    status_message  TEXT    DEFAULT '',
    last_error      TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_hb_terminal ON heartbeats(terminal_id);
CREATE INDEX IF NOT EXISTS idx_hb_ts ON heartbeats(ts_ms);

-- 9. alerts_history
CREATE TABLE IF NOT EXISTS alerts_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type      TEXT    NOT NULL,
    terminal_id     TEXT,
    message         TEXT    NOT NULL,
    channel         TEXT    NOT NULL CHECK (channel IN ('telegram', 'email')),
    sent_at         INTEGER NOT NULL,
    delivered       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts_history(alert_type);
CREATE INDEX IF NOT EXISTS idx_alert_terminal ON alerts_history(terminal_id);
CREATE INDEX IF NOT EXISTS idx_alert_sent ON alerts_history(sent_at);
