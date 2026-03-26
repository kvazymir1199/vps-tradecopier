# Trading Logic Rules

Trading logic rules for the Michael Spiropoulos Strategy project.

## Risk Management

### Daily Loss Limit

```
Limit: $600 per day
Action: SHUTDOWN (block trading until end of day)
```

```cpp
// RiskManager logic
if(loss >= m_daily_loss_limit) {
   m_state.is_shutdown = true;
   SaveState();  // Persistence

   if(m_force_close) {
      EnforceSessionEnd();  // Close all positions
   }
}
```

**CRITICAL**: Never bypass the shutdown mechanism!

### Position Sizing

```
Nominal size: $10,000 USD
Calculation: target_value / (contract_size * price)
Normalization: by SYMBOL_VOLUME_MIN and SYMBOL_VOLUME_STEP
```

### Stop Loss Levels

| Type | Level | Description |
|------|-------|-------------|
| Protective SL | 0.5% | Initial stop loss |
| Breakeven | +0.5% profit | SL moves to entry |
| Trailing Stop | +0.6% profit | Trailing 0.6% activation |

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
Limit: 10 minutes
Action: PositionClose()
```

## Session Control

### Trading Sessions

| Session | Time | Instruments |
|---------|------|-------------|
| London | 08:00-10:00 GMT | Gold, WTI |
| NY | 09:30-11:30 EST | US Stock CFDs |

### Session States

```cpp
enum SessionState {
   SESSION_CLOSED,     // Outside trading window
   SESSION_DATA_ONLY,  // Data collection (Data Start -> Trade Start)
   SESSION_TRADING,    // Trading window (Trade Start -> Stop New)
   SESSION_STOP_NEW    // New trades prohibited (Stop New -> Force Close)
};
```

### DST Adjustment

```
Automatic adjustment for:
- EU DST (last Sunday of March/October)
- US DST (second Sunday of March, first Sunday of November)
```

**CRITICAL**: Always use SessionManager for time handling!

### Force Close

```
Trigger: Reaching Force Close time
Action: Close all session positions
Logging: EXIT reason = "SESSION_END"
```

## Filters

### SPY Filter (2 of 3 Rule)

```
To allow LONG/SHORT, a minimum of 2 out of 3 points is required:

1. EMA Momentum (M5)
   - LONG: EMA3 > EMA8
   - SHORT: EMA3 < EMA8

2. RVOL (Relative Volume)
   - Condition: current volume / avg(10 days) > 1.2

3. Daily Change
   - LONG: price > +0.4% from Open
   - SHORT: price < -0.4% from Open
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
Threshold: 0.2% from level

Levels:
- PDH (Previous Day High)
- PMH (Pre-Market High)
- VWAP (Volume Weighted Average Price)
- Round Numbers (X.00)
```

### External Filters

**Earnings Day**:
```
Source: Earnings.txt (one symbol per line)
Action: Block trading for the entire day
```

**Halted Symbol**:
```
Detection: 2 most recent M1 bars with volume = 0
Action: Block until next session
```

### Technical Filters

| Filter | Threshold | Application |
|--------|-----------|-------------|
| Spread | max 0.2% | All instruments |
| Premarket Volume | min 100k | US stocks |
| Liquidity (Long) | 30k | US stocks |
| Liquidity (Short) | 40k | US stocks |
| Tick Volume | 50 | Gold/WTI |
| Gap | ±15% from prev close | All instruments |

## Position Limits

### Per Symbol

```
Rule: 1 trade per symbol per day
Check: open positions + history for the day
```

### Group Limits

| Group | Limit |
|-------|-------|
| NY Stocks | 3 simultaneous |
| Gold | 1 |
| WTI | 1 |

## Trade Execution

### Order Flow

```
1. Strategy.GetSignal() -> SIGNAL_BUY/SELL/NONE
2. PositionLimitManager.CheckSafeToTrade()
3. FilterManager.CheckTradeFilters()
4. TradeManager.ExecuteTrade()
5. TradeLogger.LogEntry()
```

### Entry Metadata Caching

```cpp
// Save on entry
struct STradeEntryCache {
   ulong    ticket;
   double   entry_price;
   double   entry_spread;
   double   liquidity_score;
   string   spy_condition;
   datetime entry_time;
};

// Use when logging exit
void LogExit(ulong ticket) {
   STradeEntryCache cache = GetCachedEntry(ticket);
   // log with entry metadata
}
```

### Exit Reasons

| Code | Description |
|------|-------------|
| SL | Stop Loss hit |
| TS | Trailing Stop hit |
| TIMER | Max Duration exceeded |
| SESSION_END | Force Close |
| SHUTDOWN | Daily Loss Limit |
| MANUAL | Closed manually |

## Logging

### CSV Format

```
File: TradeLogs/Trade_YYYYMMDD.csv

Columns:
Time, Symbol, Direction, Entry Price, Exit Price, Exit Reason,
SPY Condition, Liquidity, Spread %, Event Type
```

### Event Types

```
ENTRY      - Position opened
EXIT       - Position closed
DISCONNECT - Connection lost
RECONNECT  - Connection restored
SHUTDOWN   - Daily Loss Limit
```

## Connection Watchdog

```
Critical Threshold: 180 seconds
Actions:
1. Log DISCONNECT
2. Force Close all positions
3. SHUTDOWN until reconnect
```

## Safety Rules

1. **NEVER** trade without an active RiskManager
2. **NEVER** ignore session boundaries
3. **ALWAYS** check connection status
4. **ALWAYS** log critical operations
5. **ALWAYS** save state for recovery
