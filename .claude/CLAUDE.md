# CLAUDE.md

Answer Always in Russian.

## Project Overview

**Trade Copier** — система копирования сделок между MT5 терминалами.

Состоит из 4 компонентов:
- **Hub Service** (Python) — центральный маршрутизатор сообщений через Windows named pipes
- **Master EA** (MQL5) — отслеживает сделки на мастер-терминале и отправляет в Hub
- **Slave EA** (MQL5) — получает команды от Hub и исполняет сделки через CTrade
- **Web UI** — FastAPI backend + Next.js frontend для управления терминалами и связями

**Broker**: Pepperstone
**Платформа**: Windows (named pipes для IPC)
**Python**: 3.11+ с пакетным менеджером `uv`

## Architecture

```
Master EA ──named pipe──> Hub Service ──named pipe──> Slave EA
  (MT5)     JSON msgs     (Python)     SlaveCommands   (MT5)
            <── ACK/NACK              <── ACK/NACK

                          Hub Service
                              │
                           SQLite (WAL)
                              │
                          FastAPI ──> Next.js UI
```

## Project Structure

```
hub/                          # Python Hub Service
├── db/
│   ├── schema.sql            # DDL (9 таблиц, WAL mode)
│   └── manager.py            # DatabaseManager (единственный writer)
├── protocol/
│   ├── models.py             # MessageType, MasterMessage, SlaveCommand, AckMessage
│   └── serializer.py         # JSON encode/decode с newline-разделителем
├── mapping/
│   ├── magic.py              # Magic number parse + slave mapping
│   ├── symbol.py             # Symbol resolution (explicit > suffix)
│   └── lot.py                # Lot size: multiplier, fixed, partial close
├── transport/
│   └── pipe_server.py        # Async Windows named pipe server
├── router/
│   └── router.py             # Message router + ResendWindow (N=200)
├── monitor/
│   ├── health.py             # 4 проверки: heartbeat, ACK timeout, NACKs, queue
│   └── alerts.py             # Telegram alerts + дедупликация (5 мин)
├── config.py                 # Config loader (JSON)
└── main.py                   # HubService entry point (asyncio)

ea/                           # MQL5 Expert Advisors
├── Include/
│   ├── CopierPipe.mqh        # Named pipe client (kernel32.dll imports)
│   ├── CopierProtocol.mqh    # JSON builder/parser
│   └── CopierLogger.mqh      # File logger
├── Master/
│   └── TradeCopierMaster.mq5 # Master EA
└── Slave/
    └── TradeCopierSlave.mq5  # Slave EA

web/
├── api/                      # FastAPI backend
│   ├── main.py               # App с CORS
│   ├── database.py           # aiosqlite connection (WAL)
│   ├── schemas.py            # Pydantic models
│   └── routers/              # terminals, links, symbol_mappings, magic_mappings
└── frontend/                 # Next.js + shadcn/ui
    └── src/
        ├── app/              # App Router (page.tsx, layout.tsx)
        ├── components/       # Tables, dialogs, mappings panel
        ├── hooks/            # use-terminals (5s poll), use-links, use-mappings
        ├── lib/              # api.ts, utils.ts
        └── types/            # Terminal, Link, SymbolMapping, MagicMapping

tests/                        # 70 pytest tests (15 файлов)
scripts/backup_db.py          # DB backup с WAL checkpoint + retention
config/config.example.json    # Пример конфигурации
```

## Build & Run Commands

### Hub Service
```bash
uv run python -m hub.main
```

### FastAPI Backend
```bash
uv run uvicorn web.api.main:app --reload --port 8000
```

### Frontend
```bash
cd web/frontend && npm run dev          # Dev (port 3000)
cd web/frontend && npm run build        # Production build
```

### Tests
```bash
uv run pytest                           # Все тесты
uv run pytest tests/test_router.py      # Конкретный файл
uv run pytest -k "test_name"            # По имени
```

### MQL5
Скопировать `ea/` в каталог MQL5 терминала, компилировать через MetaEditor.

## Key Concepts

### Magic Number Mapping
```
slave_magic = master_magic - (master_magic % 100) + slave_setup_id
```

### Symbol Resolution
Приоритет: explicit mapping > suffix rule (`master_symbol + suffix`).

### Lot Size Modes
- **multiplier**: `master_volume * lot_value`
- **fixed**: `lot_value` (константа)
- **partial close**: пропорциональный пересчёт

### Message Protocol
Newline-delimited JSON через Windows named pipes.
Типы: OPEN, MODIFY, CLOSE, CLOSE_PARTIAL, HEARTBEAT, REGISTER.

### Database
SQLite WAL mode. 9 таблиц. DatabaseManager — единственный writer.

## Development Rules

### MUST DO
1. **Read before modifying** — Всегда читай файл перед изменением
2. **uv** — Используй `uv` для зависимостей, не pip
3. **Tests** — Покрывай новую логику тестами (pytest-asyncio)
4. **Async** — Hub Service на asyncio, не блокируй event loop
5. **WAL mode** — SQLite всегда в WAL mode

### FORBIDDEN
1. **DO NOT** блокируй asyncio event loop синхронными вызовами
2. **DO NOT** пиши в БД мимо DatabaseManager
3. **DO NOT** хардкодь пути к named pipes — используй config.json
4. **DO NOT** удаляй health checks и alerts

## Naming Conventions

### Python
- Классы: `PascalCase` (DatabaseManager, PipeServer)
- Функции: `snake_case` (compute_slave_volume, resolve_symbol)
- Константы: `UPPER_CASE`

### MQL5
- Классы: `CClassName`, члены: `m_member`, inputs: `InpName`
- Enums: `ENUM_TYPE_VALUE`, structs: `SStructName`
- Локальные: `snake_case`

### TypeScript
- Интерфейсы/компоненты: `PascalCase`
- Хуки: `useCamelCase`

## Documentation

- `docs/plans/` — Архитектура, БД, фронтенд, план реализации
- `.claude/rules/trading-logic.md` — Правила торговой логики
- `.claude/rules/mql5-style.md` — MQL5 code style guide
