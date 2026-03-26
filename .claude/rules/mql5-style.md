# MQL5 Code Style Rules

Code style rules for the Michael Spiropoulos Strategy project.

## Naming Conventions

### Classes

```cpp
// Prefix C + PascalCase
class CTradeManager { ... };
class CSessionManager { ... };
class CStrategyBreakout { ... };
```

### Class Members (private)

```cpp
// Prefix m_ + snake_case
private:
   int      m_magic_number;
   string   m_symbol;
   double   m_daily_loss_limit;
   CTrade   m_trade;
   CSessionManager* m_session_manager;
```

### Structs

```cpp
// Prefix S + PascalCase
struct STradeEntry {
   ulong    ticket;
   double   entry_price;
   datetime entry_time;
};

struct SRiskState {
   double   start_of_day_equity;
   bool     is_shutdown;
   long     day_start_time;
};
```

### Enums

```cpp
// Prefix ENUM_ + UPPER_CASE, values in UPPER_CASE
enum ENUM_STRATEGY_SIGNAL {
   SIGNAL_NONE,
   SIGNAL_BUY,
   SIGNAL_SELL
};

enum ENUM_SESSION_STATE {
   SESSION_CLOSED,
   SESSION_DATA_ONLY,
   SESSION_TRADING,
   SESSION_STOP_NEW
};
```

### Input Parameters

```cpp
// Prefix Inp + PascalCase
input int    InpMagic = 112233;
input double InpDailyLossLimit = 600.0;
input bool   InpUseSpyFilter = true;
input string InpSpySymbol = "SPY";
```

### Global Objects

```cpp
// Prefix g_ + PascalCase
CSessionManager* g_SessionManager;
CTradeManager*   g_TradeManager;
CRiskManager*    g_RiskManager;
```

### Local Variables

```cpp
// snake_case
void ProcessTrade() {
   double current_price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   int    positions_count = PositionsTotal();
   string symbol_list[];
}
```

### Methods

```cpp
// PascalCase
void Init(...);
void OnTick();
bool CheckRisk();
ENUM_STRATEGY_SIGNAL GetSignal();
bool IsTradingAllowed(string symbol);
```

## File Structure

```cpp
//+------------------------------------------------------------------+
//|                                                    FileName.mqh  |
//|                                  Copyright 2024, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property strict

//+------------------------------------------------------------------+
//| Summary: Brief module description                                |
//|          Multi-line description if needed                        |
//+------------------------------------------------------------------+

// === INCLUDES ===
#include <Trade/Trade.mqh>
#include "SessionManager.mqh"

// === ENUMS ===
enum ENUM_EXAMPLE { ... };

// === STRUCTS ===
struct SExample { ... };

// === CLASS ===
class CExample {
private:
   // Private members

public:
   // Constructor/destructor
   CExample();
   ~CExample();

   // Public methods
   void Init(...);
   void OnTick();
};

// === IMPLEMENTATION ===
CExample::CExample() {
   // ...
}
```

## Pointer Safety

### Initialization

```cpp
// ALWAYS initialize pointers in the constructor
CTradeManager::CTradeManager() {
   m_session_manager = NULL;
   m_spy_manager = NULL;
   m_risk_manager = NULL;
}
```

### Check Before Use

```cpp
// ALWAYS check for NULL before calling methods
void CTradeManager::OnTick() {
   if(m_session_manager != NULL) {
      if(m_session_manager.IsTradingAllowed(m_symbol)) {
         // ...
      }
   }
}
```

### Memory Deallocation

```cpp
// ALWAYS free dynamically created objects
CTradeManager::~CTradeManager() {
   for(int i = 0; i < ArraySize(m_strategies); i++) {
      if(CheckPointer(m_strategies[i]) == POINTER_DYNAMIC) {
         delete m_strategies[i];
      }
   }
}
```

### CheckPointer

```cpp
// Use CheckPointer for safe validation
if(CheckPointer(m_strategies[i]) == POINTER_DYNAMIC) {
   delete m_strategies[i];
   m_strategies[i] = NULL;
}
```

## Comments and Documentation

### Doxygen for Public Methods

```cpp
/**
 * Checks permission to trade
 * @param symbol Trading instrument
 * @param signal Strategy signal (BUY/SELL)
 * @return true if all filters passed
 */
bool CheckTradeFilters(string symbol, ENUM_STRATEGY_SIGNAL signal);
```

### Inline Comments

```cpp
// Breakeven at 0.5%
if(profit_pct >= 0.5 && current_sl < open_price) {
   new_sl = open_price;  // Move SL to breakeven
   should_modify = true;
}
```

### Sections

```cpp
//+------------------------------------------------------------------+
//| POSITION MANAGEMENT                                               |
//+------------------------------------------------------------------+
void ManagePositions() {
   // ...
}

//+------------------------------------------------------------------+
//| TRADE EXECUTION                                                   |
//+------------------------------------------------------------------+
void ExecuteTrade(...) {
   // ...
}
```

## Best Practices

### Defensive Programming

```cpp
// Check boundary conditions
if(ArraySize(m_strategies) == 0) return;

// Validate input data
if(symbol == "" || symbol == NULL) {
   Print("[ERROR] Invalid symbol");
   return;
}

// Check operation results
if(!m_trade.Buy(volume, symbol, price, sl, 0, comment)) {
   Print("[ERROR] Buy failed: ", GetLastError());
}
```

### Explicit over Implicit

```cpp
// GOOD: explicit specification
double price = SymbolInfoDouble(symbol, SYMBOL_ASK);
if(order_type == ORDER_TYPE_BUY) {
   // ...
}

// BAD: implicit
if(type) {  // What is type?
   // ...
}
```

### Magic Numbers

```cpp
// BAD
if(profit_pct >= 0.5) { ... }

// GOOD
const double BREAKEVEN_THRESHOLD = 0.5;  // 0.5%
if(profit_pct >= BREAKEVEN_THRESHOLD) { ... }

// OR via input parameters
input double InpBreakevenThreshold = 0.5;
```

## Logging Standards

```cpp
// Format: [ModuleName] Message
Print("[SessionManager] Session started: ", session_name);
Print("[RiskManager] Daily loss limit reached: ", loss);
Print("[SpyManager] Long allowed: score=", score, "/3");

// Levels (implicit)
Print("[INFO] Normal operation");
Print("[WARNING] Something unusual");
Print("[ERROR] Something failed");
```
