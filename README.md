# Trade Copier

Система копирования сделок между терминалами MetaTrader 5. Мастер-терминал открывает сделки, они автоматически копируются на один или несколько слейв-терминалов.

## Архитектура

```
Master EA (MT5)  ──named pipe──>  Hub Service (Python)  ──named pipe──>  Slave EA (MT5)
                   JSON msgs       центральный           SlaveCommands
                                   маршрутизатор
                                        │
                                     SQLite DB
                                        │
                                   FastAPI ──> Next.js UI
```

**Компоненты:**
- **Hub Service** — центральный маршрутизатор сообщений (asyncio + Windows named pipes)
- **Master EA** — MQL5 советник, отслеживает сделки и отправляет события в Hub
- **Slave EA** — MQL5 советник, получает команды от Hub и исполняет через CTrade
- **Web UI** — FastAPI backend + Next.js frontend для управления терминалами, связями и настройками

## Требования

- **ОС:** Windows 10/11 (named pipes — Windows-only механизм IPC)
- **Python:** 3.11+ с пакетным менеджером [uv](https://docs.astral.sh/uv/)
- **Node.js:** 18+ (для Next.js frontend)
- **MetaTrader 5:** с доступом к MetaEditor для компиляции EA

## Установка

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd Tino-V
```

### 2. Установить Python-зависимости

```bash
uv sync
```

### 3. Установить frontend-зависимости

```bash
cd web/frontend
npm install
cd ../..
```

### 4. Скомпилировать EA

1. Скопировать содержимое папки `ea/` в каталог MQL5 вашего терминала MT5
2. Открыть MetaEditor (F4 в терминале)
3. Скомпилировать `TradeCopierMaster.mq5` и `TradeCopierSlave.mq5` (F7)

## Запуск

### Быстрый старт

```bash
start.bat
```

Запускает все 3 сервиса (Hub, FastAPI, Frontend) в отдельных окнах.

### Ручной запуск

```bash
# 1. Hub Service
uv run python -m hub.main

# 2. FastAPI Backend (в другом терминале)
uv run uvicorn web.api.main:app --host 0.0.0.0 --port 8000

# 3. Frontend (в другом терминале)
cd web/frontend && npm run dev
```

### Остановка

```bash
stop.bat
```

## Настройка

### Настройка терминалов

1. Открыть Web UI: http://localhost:3000
2. В MT5 добавить Master EA на график мастер-терминала:
   - `TerminalID` = `master_1`
   - `PipeName` = `copier_master_1`
3. Добавить Slave EA на графики слейв-терминалов:
   - `TerminalID` = `slave_1` (или `slave_2`, и т.д.)
   - `CmdPipeName` = `copier_slave_1_cmd`
   - `AckPipeName` = `copier_slave_1_ack`

EA автоматически зарегистрируется в базе данных и появится в Web UI.

### Создание связей (Links)

В Web UI нажать **+ Add Link** и выбрать:
- **Master** — источник сделок
- **Slave** — получатель сделок
- **Lot Mode** — `multiplier` (множитель) или `fixed` (фиксированный объём)
- **Lot Value** — значение (например, `1.0` = тот же объём)
- **Suffix** — суффикс символа для брокера слейва (например, `m` → `EURUSDm`, `.sml` → `EURUSD.sml`)

### Конфигурация сервиса

Настройки доступны в Web UI: http://localhost:3000/settings

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| VPS ID | vps_1 | Идентификатор VPS |
| Heartbeat Interval | 10 сек | Частота heartbeat от EA |
| Heartbeat Timeout | 30 сек | Таймаут до статуса Disconnected |
| ACK Timeout | 5 сек | Таймаут ожидания ACK от слейва |
| ACK Max Retries | 3 | Количество повторных отправок |
| Resend Window | 200 | Размер окна дедупликации |
| Alert Dedup | 5 мин | Интервал дедупликации алертов |
| Telegram | выкл | Отправка алертов в Telegram |

## Поддерживаемые операции

| Операция | Описание |
|----------|----------|
| OPEN | Открытие новой позиции |
| MODIFY | Изменение SL/TP существующей позиции |
| CLOSE | Полное закрытие позиции |
| CLOSE_PARTIAL | Частичное закрытие (по объёму) |

## Magic Number Mapping

Формула: `slave_magic = master_magic - (master_magic % 100) + slave_setup_id`

Настраивается через Web UI для каждой связи.

## База данных

SQLite в режиме WAL. Файл: `%APPDATA%\MetaQuotes\Terminal\Common\Files\TradeCopier\copier.db`

Создаётся автоматически при первом запуске Hub.

## Тесты

```bash
uv run pytest                    # Все тесты
uv run pytest tests/test_router.py  # Конкретный файл
uv run pytest -k "test_name"    # По имени
```

## Структура проекта

```
hub/                    # Python Hub Service
├── config.py           # Конфигурация (из SQLite)
├── main.py             # Entry point (asyncio)
├── db/                 # Схема БД + DatabaseManager
├── protocol/           # Модели сообщений + сериализация
├── mapping/            # Magic, symbol, lot mapping
├── router/             # Маршрутизация + ResendWindow
├── transport/          # Named pipe server
└── monitor/            # Health checks + Telegram alerts

ea/                     # MQL5 Expert Advisors
├── Include/            # Общие модули (pipe, protocol, logger, database)
├── Master/             # Master EA
└── Slave/              # Slave EA

web/
├── api/                # FastAPI backend
└── frontend/           # Next.js + shadcn/ui

tests/                  # pytest тесты
```
