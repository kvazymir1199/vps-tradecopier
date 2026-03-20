# Trading Logic Rules

Правила торговой логики для проекта Michael Spiropoulos Strategy.

## Risk Management

### Daily Loss Limit

```
Лимит: $600 за день
Действие: SHUTDOWN (блокировка торговли до конца дня)
```

```cpp
// Логика RiskManager
if(loss >= m_daily_loss_limit) {
   m_state.is_shutdown = true;
   SaveState();  // Персистентность

   if(m_force_close) {
      EnforceSessionEnd();  // Закрыть все позиции
   }
}
```

**КРИТИЧНО**: Никогда не обходи shutdown механизм!

### Position Sizing

```
Номинальный размер: $10,000 USD
Расчёт: target_value / (contract_size * price)
Нормализация: по SYMBOL_VOLUME_MIN и SYMBOL_VOLUME_STEP
```

### Stop Loss Levels

| Тип | Уровень | Описание |
|-----|---------|----------|
| Protective SL | 0.5% | Начальный стоп-лосс |
| Breakeven | +0.5% profit | SL перемещается в entry |
| Trailing Stop | +0.6% profit | Активация trailing 0.6% |

```cpp
// Breakeven
if(profit_pct >= 0.5 && sl < open_price) {
   new_sl = open_price;
}

// Trailing
if(profit_pct >= 0.6) {
   double trail_sl = cur_price - (cur_price * 0.006);
   if(trail_sl > sl) new_sl = trail_sl;
}
```

### Max Duration

```
Лимит: 10 минут
Действие: PositionClose()
```

## Session Control

### Trading Sessions

| Сессия | Время | Инструменты |
|--------|-------|-------------|
| London | 08:00-10:00 GMT | Gold, WTI |
| NY | 09:30-11:30 EST | US Stock CFDs |

### Session States

```cpp
enum SessionState {
   SESSION_CLOSED,     // Вне торгового окна
   SESSION_DATA_ONLY,  // Сбор данных (Data Start → Trade Start)
   SESSION_TRADING,    // Торговое окно (Trade Start → Stop New)
   SESSION_STOP_NEW    // Новые сделки запрещены (Stop New → Force Close)
};
```

### DST Adjustment

```
Автоматическая корректировка для:
- EU DST (последнее воскресенье марта/октября)
- US DST (второе воскресенье марта, первое воскресенье ноября)
```

**КРИТИЧНО**: Всегда используй SessionManager для работы со временем!

### Force Close

```
Триггер: Достижение Force Close времени
Действие: Закрытие всех позиций сессии
Логирование: EXIT reason = "SESSION_END"
```

## Filters

### SPY Filter (2 of 3 Rule)

```
Для разрешения LONG/SHORT нужно минимум 2 балла из 3:

1. EMA Momentum (M5)
   - LONG: EMA3 > EMA8
   - SHORT: EMA3 < EMA8

2. RVOL (Relative Volume)
   - Условие: текущий объём / avg(10 days) > 1.2

3. Daily Change
   - LONG: цена > +0.4% от Open
   - SHORT: цена < -0.4% от Open
```

```cpp
bool IsLongAllowed() {
   int score = 0;
   if(ema3 > ema8) score++;
   if(rvol > 1.2) score++;
   if(daily_change > 0.4) score++;
   return (score >= 2);
}
```

### Price Proximity Filters

```
Порог: 0.2% от уровня

Уровни:
- PDH (Previous Day High)
- PMH (Pre-Market High)
- VWAP (Volume Weighted Average Price)
- Round Numbers (X.00)
```

### External Filters

**Earnings Day**:
```
Источник: Earnings.txt (один символ на строку)
Действие: Блокировка торговли на весь день
```

**Halted Symbol**:
```
Детекция: 2 последних M1 бара с volume = 0
Действие: Блокировка до следующей сессии
```

### Technical Filters

| Фильтр | Порог | Применение |
|--------|-------|------------|
| Spread | max 0.2% | Все инструменты |
| Premarket Volume | min 100k | US stocks |
| Liquidity (Long) | 30k | US stocks |
| Liquidity (Short) | 40k | US stocks |
| Tick Volume | 50 | Gold/WTI |
| Gap | ±15% от prev close | Все инструменты |

## Position Limits

### Per Symbol

```
Правило: 1 сделка на символ в день
Проверка: открытые позиции + история за день
```

### Group Limits

| Группа | Лимит |
|--------|-------|
| NY Stocks | 3 одновременно |
| Gold | 1 |
| WTI | 1 |

## Trade Execution

### Order Flow

```
1. Strategy.GetSignal() → SIGNAL_BUY/SELL/NONE
2. PositionLimitManager.CheckSafeToTrade()
3. FilterManager.CheckTradeFilters()
4. TradeManager.ExecuteTrade()
5. TradeLogger.LogEntry()
```

### Entry Metadata Caching

```cpp
// Сохраняем при входе
struct STradeEntryCache {
   ulong    ticket;
   double   entry_price;
   double   entry_spread;
   double   liquidity_score;
   string   spy_condition;
   datetime entry_time;
};

// Используем при логировании выхода
void LogExit(ulong ticket) {
   STradeEntryCache cache = GetCachedEntry(ticket);
   // log with entry metadata
}
```

### Exit Reasons

| Код | Описание |
|-----|----------|
| SL | Stop Loss hit |
| TS | Trailing Stop hit |
| TIMER | Max Duration exceeded |
| SESSION_END | Force Close |
| SHUTDOWN | Daily Loss Limit |
| MANUAL | Закрыто вручную |

## Logging

### CSV Format

```
Файл: TradeLogs/Trade_YYYYMMDD.csv

Колонки:
Time, Symbol, Direction, Entry Price, Exit Price, Exit Reason,
SPY Condition, Liquidity, Spread %, Event Type
```

### Event Types

```
ENTRY      - Открытие позиции
EXIT       - Закрытие позиции
DISCONNECT - Потеря соединения
RECONNECT  - Восстановление
SHUTDOWN   - Daily Loss Limit
```

## Connection Watchdog

```
Critical Threshold: 180 секунд
Действия:
1. Логирование DISCONNECT
2. Force Close всех позиций
3. SHUTDOWN до реконнекта
```

## Safety Rules

1. **НИКОГДА** не торгуй без активного RiskManager
2. **НИКОГДА** не игнорируй session boundaries
3. **ВСЕГДА** проверяй connection status
4. **ВСЕГДА** логируй критичные операции
5. **ВСЕГДА** сохраняй state для recovery
