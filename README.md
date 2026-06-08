# Trade Copier

A trade copying system between MetaTrader 5 terminals. The master terminal opens trades, and they are automatically copied to one or more slave terminals.

## Architecture

```
Master EA (MT5)  ──named pipe──>  Hub Service (Python)  ──named pipe──>  Slave EA (MT5)
                   JSON msgs       central                SlaveCommands
                                   router
                                        │
                                     SQLite DB
                                        │
                                   FastAPI ──> Next.js UI ──> Telegram alerts
```

**Components:**
- **Hub Service** — central message router (asyncio + Windows named pipes)
- **Master EA** — MQL5 Expert Advisor that monitors trades and sends events to Hub
- **Slave EA** — MQL5 Expert Advisor that receives commands from Hub and executes them via CTrade
- **Web UI** — FastAPI backend + Next.js frontend for managing terminals, links, mappings, alerts
- **Telegram bot** — one-way notifications (heartbeat / NACK / disconnect / daily summary) + read-only commands (`/status`, `/last_alerts`, `/mute`)

---

# Server Setup — From Zero to Production

This is the full setup path for a fresh Windows VPS. Follow phases top-to-bottom; later phases assume earlier ones are done.

## Phase 0 — Prerequisites

**Hardware (recommended for 2 Master + 3 Slave cross-broker run):**
- Windows Server 2019/2022 or Windows 10/11 Pro
- ≥ 8 GB RAM (1.5 GB per MT5 terminal + headroom)
- ≥ 50 GB free disk (~1 GB per MT5 install)
- Stable internet — broker connections are latency-sensitive
- Administrator rights — required for Windows named pipes

**Pause Windows Update during the test window** — a forced reboot mid-run invalidates the stability proof.

## Phase 1 — Install system tools

Install in this order:

1. **Git** — https://git-scm.com/download/win (default install).
2. **Python 3.11+** — https://www.python.org/downloads/. Check **"Add python.exe to PATH"** during install.
3. **uv** (package manager) — open PowerShell as Administrator:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
4. **Node.js 18+ LTS** — https://nodejs.org/ (LTS installer).

Verify everything (in a fresh terminal):
```bash
git --version
python --version
uv --version
node --version
npm --version
```

## Phase 2 — Clone and provision the project

```bash
cd C:\
git clone <repo-url> Tino-V
cd Tino-V
uv sync
cd web\frontend
npm install
cd ..\..
```

Expected layout afterwards:
- `C:\Tino-V\hub\` — Python Hub
- `C:\Tino-V\web\api\` — FastAPI backend
- `C:\Tino-V\web\frontend\` — Next.js UI
- `C:\Tino-V\ea\` — MQL5 source for Master and Slave EAs
- `C:\Tino-V\scripts\` — backup_db.py, restore_db.py, etc.

## Phase 3 — Install MetaTrader 5 terminals (one per broker)

For each broker that will host a Master or Slave terminal:

1. Download the broker's official MT5 installer (each broker ships their own).
2. **Install to a separate directory** so terminals don't share data folders:
   ```
   C:\MT5_Pepperstone\
   C:\MT5_ICMarkets\
   C:\MT5_FTMO\
   ...
   ```
   Use the installer's "Settings" → custom install path.
3. Launch the terminal, log in with the demo / live account credentials.
4. Verify the account is **connected** (status bar bottom-right) and quotes update on at least one symbol.
5. Open **File → Open Data Folder** and note the path; the EA will be deployed there in Phase 5.

For the MS3 cross-broker run, the target is 5 different broker firms — 2 hosting Masters, 3 hosting Slaves.

## Phase 4 — Compile the EAs

MetaEditor is required only on one machine — compile once, deploy `.ex5` everywhere.

1. Launch any MT5 terminal → **F4** opens MetaEditor.
2. **File → Open Folder** → point it at `C:\Tino-V\ea\`.
3. Compile in this order (F7 in MetaEditor for each):
   - `Include/CopierPipe.mqh` — must compile cleanly (no `.ex5` produced; this is a library).
   - `Include/CopierProtocol.mqh`
   - `Include/CopierLogger.mqh`
   - `Master/TradeCopierMaster.mq5` — produces `TradeCopierMaster.ex5`.
   - `Slave/TradeCopierSlave.mq5` — produces `TradeCopierSlave.ex5`.
4. Copy the produced `.ex5` files to a release folder (e.g. `C:\Tino-V\release\ms3\`) so deployment to the other terminals is one drag-and-drop.

## Phase 5 — Deploy the EAs to each terminal

For every MT5 terminal installed in Phase 3:

1. **File → Open Data Folder** in the terminal.
2. Open `MQL5\Experts\` and copy in:
   - `TradeCopierMaster.ex5` — only on Master terminals.
   - `TradeCopierSlave.ex5` — only on Slave terminals.
3. Open `MQL5\Include\` and copy the entire `ea\Include\` folder there (so future re-compiles inside this terminal work).
4. In MT5: **right-click in the Navigator panel → Refresh**. The new EAs appear under "Expert Advisors".

## Phase 6 — Initialise the Hub for the first time

1. Start the three services (open three terminals or use `start.bat` if you set it up):
   ```bash
   # Terminal 1 — Hub Service
   cd C:\Tino-V
   uv run python -m hub.main

   # Terminal 2 — FastAPI backend
   cd C:\Tino-V
   uv run uvicorn web.api.main:app --host 0.0.0.0 --port 8000

   # Terminal 3 — frontend
   cd C:\Tino-V\web\frontend
   npm run dev
   ```
2. Open the Web UI: http://localhost:3000

The Hub auto-creates the SQLite DB at:
```
%APPDATA%\MetaQuotes\Terminal\Common\Files\TradeCopier\copier.db
```
This `Common\Files\` directory is **shared across all MT5 terminals on the machine** — every EA on every terminal reads/writes the same database, which is how the cross-terminal routing works.

## Phase 7 — Attach the EAs to charts

Repeat for each terminal:

1. Open any chart (the EA does not need a specific symbol — it manages trades by magic number).
2. Drag the EA from the Navigator onto the chart.
3. In the dialog, set the **Inputs** tab. Naming convention used throughout the project:
   - **Master terminal**:
     - `TerminalID` = `master_<broker_short>` — e.g. `master_pepperstone`
     - `PipeName` = `copier_master_<broker_short>` — must match `TerminalID` after the `copier_` prefix
   - **Slave terminal**:
     - `TerminalID` = `slave_<broker_short>` — e.g. `slave_icmarkets`
     - `CmdPipeName` = `copier_slave_<broker_short>_cmd`
     - `AckPipeName` = `copier_slave_<broker_short>_ack`
4. In the **Common** tab, check **"Allow algorithmic trading"** and **"Allow DLL imports"** (needed for the named-pipe DLL calls).
5. Click OK. The smiley face in the chart corner must be green.
6. Within ~5 seconds the terminal appears on the Web UI **Dashboard** with status `Active`.

If a terminal does not appear: check the EA's log (Toolbox → Experts) for connection errors. The pipe name must match exactly what the Hub creates (which derives from the `TerminalID`).

## Phase 8 — Wire up routing (Links + Mappings)

Open the Web UI and configure for each Master → Slave pair:

1. **Links** — click **+ Add Link**. Pick a Master, pick a Slave, set:
   - **Lot Mode** — `multiplier` (proportional) or `fixed` (absolute volume).
   - **Lot Value** — e.g. `1.0` for "copy verbatim" or `0.5` for half size.
   - **Suffix** — broker-specific symbol suffix (e.g. `.s` if EURUSD trades as `EURUSD.s` on this Slave).
2. **Symbol Mappings** — only required when the suffix rule isn't enough (e.g. Master uses `XAUUSD`, Slave uses `GOLD`). Add an explicit row per exotic pair.
3. **Magic Mappings** — **required**. Without a magic mapping the route is blocked (this is the MS2 whitelist guarantee). For each master setup_id you want copied:
   - `Master setup_id` — last two digits of the master's magic number.
   - `Slave setup_id` — the magic suffix to apply on the Slave side.
   - `Allowed direction` — `BUY`, `SELL`, or `BOTH`.

## Phase 9 — Configure Telegram notifications

1. Create the bot:
   - Open Telegram → search for `@BotFather` → `/newbot` → follow the prompts → copy the **token** (looks like `1234567890:AAFm...`).
2. Get your chat_id:
   - Search `@userinfobot` in Telegram → press Start → it replies with your numeric ID.
   - For a group chat: add the bot to the group, post any message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `result[*].message.chat.id` (negative number for groups).
3. In the Web UI: **Telegram** page.
   - Paste `bot_token` and `chat_id`.
   - Toggle **Enabled**.
   - (Optional) flip per-alert-type toggles. `trade_copied` is off by default because it's high-volume.
   - Click **Save**.
4. Click **Test alert** — within ~1 s the bot must DM you the test message. The row appears on the **Alerts** page with `delivered=1`.

If the test fails, the most common causes are:
- Wrong chat_id (positive vs negative sign).
- The bot has never been started by the recipient (DM the bot once before the first alert).
- Network/firewall blocks `api.telegram.org`.

## Phase 10 — Smoke test the full flow

1. On a Master terminal, open any small position (e.g. 0.01 lot EURUSD with a SL/TP).
2. Within ~1 s the same position must appear on every linked Slave terminal, with:
   - Volume transformed per **Lot Mode**.
   - Magic number transformed per **Magic Mapping**.
   - Symbol resolved via **Symbol Mappings** / suffix.
3. Close the Master position → all Slave copies close.
4. Open the **Alerts** page — there must be no `heartbeat_miss`, `ack_timeout`, or `slave_disconnected` entries during the test.

## Phase 11 — Enable daily backups

The DB lives in `Common\Files\TradeCopier\copier.db`. Set up an automated daily backup:

1. Pick a backup directory (ideally on a different physical disk or a network share):
   ```
   D:\TradeCopierBackups\
   ```
2. Manual one-off backup to verify:
   ```bash
   cd C:\Tino-V
   uv run python scripts\backup_db.py "%APPDATA%\MetaQuotes\Terminal\Common\Files\TradeCopier\copier.db" "D:\TradeCopierBackups\" 30
   ```
   The third argument is `retention_days`. Backups older than this are auto-purged.
3. Schedule it via **Task Scheduler**:
   - Trigger: daily at 03:00.
   - Action: `cmd.exe /c cd /d C:\Tino-V && uv run python scripts\backup_db.py "%APPDATA%\MetaQuotes\Terminal\Common\Files\TradeCopier\copier.db" "D:\TradeCopierBackups\" 30`
4. Test restore (do this **once** before relying on backups in production):
   - Stop the Hub.
   - Run:
     ```bash
     uv run python scripts\restore_db.py "D:\TradeCopierBackups\copier_<latest>.db" "%APPDATA%\MetaQuotes\Terminal\Common\Files\TradeCopier\copier.db"
     ```
   - The script refuses if the Hub is still running (write-lock detected). It also writes a `.pre_restore_<timestamp>.db` snapshot of the file you're about to overwrite.

## Phase 12 — Production hardening

Before flipping to a live test window:

- **Disable Windows Update auto-restart** during the agreed test window — settings → Pause updates.
- **Set Hub + FastAPI + frontend to autostart** via Task Scheduler "At startup" triggers, so a VPS reboot doesn't leave the system half-up.
- **Set MT5 terminals to autostart**: each terminal has an option *Tools → Options → Server → Keep personal settings and data at startup*; pair with a Windows shortcut in `shell:startup`.
- **Firewall**: if the VPS exposes the public internet, block inbound 8000 (FastAPI) and 3000 (frontend) — these are intended for `localhost` only.
- **Verify Telegram**: re-run **Test alert** after every reboot to confirm token + chat_id survived.

---

# Daily Operations

## Service control

```bash
start.bat   # launches Hub + FastAPI + frontend in separate windows
stop.bat    # closes all three
```

## Health-check checklist

Run these in order; any failure means stop and investigate before opening real positions:

1. **Hub up** — http://localhost:8000/api/telegram returns 200.
2. **Frontend up** — http://localhost:3000 loads the Dashboard.
3. **All terminals registered** — every expected `master_*` and `slave_*` row visible.
4. **Heartbeats fresh** — every terminal's `last_heartbeat` is < 30 s old (column on the Dashboard).
5. **No fresh alerts** — Alerts page shows no new `heartbeat_miss` / `ack_timeout` / `slave_disconnected` in the last 5 minutes.
6. **Telegram alive** — press **Test alert**; expect `delivered=1`.

## Operator-side Telegram commands

Once the bot is configured, send these in the chat configured under `chat_id`:

| Command | Effect |
|---|---|
| `/status` | Hub uptime, pending msg count, online terminals, last 5 alerts |
| `/last_alerts [N]` | Last N alerts (default 10), newest first |
| `/mute [duration]` | Mute all alerts (e.g. `/mute 1h`, `/mute 30m`, `/mute 2d`). `/mute off` clears. |
| `/help` | Lists commands |

Commands from any chat other than the configured `chat_id` are silently dropped.

---

# Troubleshooting

| Symptom | First thing to check |
|---|---|
| Terminal stays `Disconnected` in the UI | EA log (Toolbox → Experts). Pipe name in EA inputs must match the Hub side (`copier_<terminal_id>` for masters; `copier_<terminal_id>_cmd` + `_ack` for slaves). |
| Master sends OPEN, Slave receives nothing | Open **Alerts** page → look for `consecutive_nacks`. Most common cause: missing **Magic Mapping** for that setup_id (strict whitelist). |
| ACK timeout alerts firing on a quiet system | Either ACK Timeout (Settings → Timing) is too tight, or the Slave terminal is laggy — check its broker connection. |
| `database is locked` errors in `hub.log` | Another process is holding a write lock. Most often: a manual `sqlite3` session in another window. Close it. |
| Telegram test alert returns `delivered=false` | Settings → Telegram → re-check `bot_token` (no trailing spaces) and `chat_id`. DM the bot once if you've never opened the chat. |
| Hub log grows large | Rotate manually: stop Hub, move `Common\Files\TradeCopier\hub.log` to an archive, restart. |
| You need to restore from backup | Stop the Hub first (script refuses to overwrite a locked DB), then run `scripts\restore_db.py <backup> <live_db>`. |

---

# Configuration Reference

Stored in the SQLite `config` key-value table; edited through the Settings page in the Web UI.

| Parameter | Default | Description |
|---|---|---|
| `vps_id` | `vps_1` | Identifier persisted in heartbeats so multi-VPS deployments can be told apart in the DB. |
| `heartbeat_interval_sec` | 10 | How often each EA sends a heartbeat. |
| `heartbeat_timeout_sec` | 30 | Window before a terminal is marked `Disconnected`. |
| `ack_timeout_sec` | 5 | How long the Hub waits for a Slave ACK before retrying. |
| `ack_max_retries` | 3 | Retry budget per message. After this, status → `expired`. |
| `resend_window_size` | 200 | Per-master ResendWindow size (MS2 dedup). |
| `alert_dedup_minutes` | 5 | Suppression window for identical alerts. |
| `telegram_*` | off / empty | See Phase 9 above. |
| `telegram_alert_storm_threshold` | 10 | If more than this many alerts are deduplicated inside one dedup window, fire `alert_storm`. |
| `telegram_alerts_retention_days` | 90 | `alerts_history` table is auto-purged beyond this. |
| `alert_enabled_<type>` | mostly `true` | Per-alert-type toggle. `trade_copied` ships **off** (high volume). |

---

# Supported trade operations

| Operation | Description |
|---|---|
| OPEN | Open a new market position. |
| MODIFY | Update SL / TP of an existing position. |
| CLOSE | Fully close. |
| CLOSE_PARTIAL | Close a portion of an existing position by volume. |
| PENDING_PLACE / PENDING_MODIFY / PENDING_DELETE | Pending-order lifecycle (limit / stop). |

## Magic number transformation

```
slave_magic = master_magic - (master_magic % 100) + slave_setup_id
```

Wired via **Magic Mappings** per Link. A missing mapping blocks the route (this is intentional — it's the MS2 strict-whitelist guarantee).

---

# Tests

```bash
uv run pytest                      # full regression suite (fast)
uv run pytest -m "not slow"        # same, explicitly skip slow
uv run pytest -m slow              # 1h sustained-load test (override duration via env var)
MS3_SUSTAINED_DURATION_SEC=3600 uv run pytest -m slow   # the real 1h acceptance run
uv run pytest tests/test_ms3_stress.py  # MS3 stress + recovery only
uv run pytest tests/test_backup_restore.py  # DB backup / restore only
```

# Project Structure

```
hub/                    # Python Hub Service
├── config.py           # Configuration loaded from SQLite (with Telegram/alert fields)
├── main.py             # Entry point (asyncio)
├── db/                 # DB schema + DatabaseManager (sole writer)
├── protocol/           # Message models + serialization
├── mapping/            # Magic, symbol, lot mapping
├── router/             # Routing + ResendWindow
├── transport/          # Named pipe server (with on_disconnect callback)
└── monitor/            # Health checks + AlertSender + TelegramBot

ea/                     # MQL5 Expert Advisors
├── Include/            # Shared modules (pipe, protocol, logger, database)
├── Master/             # Master EA
└── Slave/              # Slave EA

web/
├── api/                # FastAPI backend (terminals, links, mappings, telegram, alerts)
└── frontend/           # Next.js + shadcn/ui (Dashboard, Alerts, Settings, Telegram)

scripts/
├── backup_db.py        # SQLite backup with WAL checkpoint + retention
└── restore_db.py       # Restore-from-backup with integrity check + lock guard

tests/                  # pytest tests — MS2 proof + MS3 stress + recovery + backup/restore
```
