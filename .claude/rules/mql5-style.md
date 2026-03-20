# MQL5 Code Style Rules

Правила оформления кода для проекта Michael Spiropoulos Strategy.

## Naming Conventions

### Классы

```cpp
// Префикс C + PascalCase
class CTradeManager { ... };
class CSessionManager { ... };
class CStrategyBreakout { ... };
```

### Члены класса (приватные)

```cpp
// Префикс m_ + snake_case
private:
   int      m_magic_number;
   string   m_symbol;
   double   m_daily_loss_limit;
   CTrade   m_trade;
   CSessionManager* m_session_manager;
```

### Структуры

```cpp
// Префикс S + PascalCase
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

### Енумы

```cpp
// Префикс ENUM_ + UPPER_CASE, значения в UPPER_CASE
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

### Входные параметры

```cpp
// Префикс Inp + PascalCase
input int    InpMagic = 112233;
input double InpDailyLossLimit = 600.0;
input bool   InpUseSpyFilter = true;
input string InpSpySymbol = "SPY";
```

### Глобальные объекты

```cpp
// Префикс g_ + PascalCase
CSessionManager* g_SessionManager;
CTradeManager*   g_TradeManager;
CRiskManager*    g_RiskManager;
```

### Локальные переменные

```cpp
// snake_case
void ProcessTrade() {
   double current_price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   int    positions_count = PositionsTotal();
   string symbol_list[];
}
```

### Методы

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
//| Summary: Краткое описание модуля                                 |
//|          Многострочное описание при необходимости                |
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
   // Приватные члены

public:
   // Конструктор/деструктор
   CExample();
   ~CExample();

   // Публичные методы
   void Init(...);
   void OnTick();
};

// === IMPLEMENTATION ===
CExample::CExample() {
   // ...
}
```

## Pointer Safety

### Инициализация

```cpp
// ВСЕГДА инициализируй указатели в конструкторе
CTradeManager::CTradeManager() {
   m_session_manager = NULL;
   m_spy_manager = NULL;
   m_risk_manager = NULL;
}
```

### Проверка перед использованием

```cpp
// ВСЕГДА проверяй NULL перед вызовом методов
void CTradeManager::OnTick() {
   if(m_session_manager != NULL) {
      if(m_session_manager.IsTradingAllowed(m_symbol)) {
         // ...
      }
   }
}
```

### Освобождение памяти

```cpp
// ВСЕГДА освобождай динамически созданные объекты
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
// Используй CheckPointer для безопасной проверки
if(CheckPointer(m_strategies[i]) == POINTER_DYNAMIC) {
   delete m_strategies[i];
   m_strategies[i] = NULL;
}
```

## Comments and Documentation

### Doxygen для публичных методов

```cpp
/**
 * Проверяет разрешение на торговлю
 * @param symbol Торговый инструмент
 * @param signal Сигнал стратегии (BUY/SELL)
 * @return true если все фильтры пройдены
 */
bool CheckTradeFilters(string symbol, ENUM_STRATEGY_SIGNAL signal);
```

### Inline комментарии

```cpp
// Breakeven на 0.5%
if(profit_pct >= 0.5 && current_sl < open_price) {
   new_sl = open_price;  // Перемещаем SL в безубыток
   should_modify = true;
}
```

### Секции

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
// Проверяй граничные условия
if(ArraySize(m_strategies) == 0) return;

// Валидируй входные данные
if(symbol == "" || symbol == NULL) {
   Print("[ERROR] Invalid symbol");
   return;
}

// Проверяй результаты операций
if(!m_trade.Buy(volume, symbol, price, sl, 0, comment)) {
   Print("[ERROR] Buy failed: ", GetLastError());
}
```

### Explicit over Implicit

```cpp
// ХОРОШО: явное указание
double price = SymbolInfoDouble(symbol, SYMBOL_ASK);
if(order_type == ORDER_TYPE_BUY) {
   // ...
}

// ПЛОХО: неявное
if(type) {  // Что такое type?
   // ...
}
```

### Magic Numbers

```cpp
// ПЛОХО
if(profit_pct >= 0.5) { ... }

// ХОРОШО
const double BREAKEVEN_THRESHOLD = 0.5;  // 0.5%
if(profit_pct >= BREAKEVEN_THRESHOLD) { ... }

// ИЛИ через input параметры
input double InpBreakevenThreshold = 0.5;
```

## Logging Standards

```cpp
// Формат: [ModuleName] Message
Print("[SessionManager] Session started: ", session_name);
Print("[RiskManager] Daily loss limit reached: ", loss);
Print("[SpyManager] Long allowed: score=", score, "/3");

// Уровни (неявные)
Print("[INFO] Normal operation");
Print("[WARNING] Something unusual");
Print("[ERROR] Something failed");
```
