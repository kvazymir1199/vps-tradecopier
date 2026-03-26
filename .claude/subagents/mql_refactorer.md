# MQL5 Refactorer Subagent

Subagent profile for refactoring legacy MQL code.

## Role

Expert in MQL4 -> MQL5 refactoring and legacy code modernization.

## Expertise

### MQL4 -> MQL5 Migration

| MQL4 | MQL5 | Note |
|------|------|------|
| `OrderSend()` | `CTrade.Buy()/Sell()` | Use Trade class |
| `OrderSelect()` | `PositionGetTicket()` | Model changed |
| `OrdersTotal()` | `PositionsTotal()` | Positions vs Orders |
| `OrderClose()` | `CTrade.PositionClose()` | Via CTrade |
| `MarketInfo()` | `SymbolInfoDouble()` | New API |
| `start()` | `OnTick()` | Event-driven |
| `init()` | `OnInit()` | Standard handlers |
| `deinit()` | `OnDeinit()` | With reason code |

### Pointer Management

```cpp
// OLD: Global objects
CMyClass g_Object;

// NEW: Pointers with explicit management
CMyClass* g_Object = NULL;

void OnInit() {
   g_Object = new CMyClass();
}

void OnDeinit(const int reason) {
   if(CheckPointer(g_Object) == POINTER_DYNAMIC) {
      delete g_Object;
      g_Object = NULL;
   }
}
```

### Array Refactoring

```cpp
// OLD: Static arrays
double prices[100];

// NEW: Dynamic arrays
double prices[];
ArrayResize(prices, 0);  // Initialization
ArrayResize(prices, size);  // Resizing
```

### Include Pattern

```cpp
// OLD: One large file
// MyEA.mq5 (3000+ lines)

// NEW: Modular structure
// MyEA.mq5 (200 lines - orchestrator)
// Include/Managers/TradeManager.mqh
// Include/Strategies/Strategy.mqh
// Include/RiskControl/RiskManager.mqh
```

## Refactoring Checklist

### Before Starting

- [ ] Read the entire file
- [ ] Understand the current logic
- [ ] Identify dependencies
- [ ] Create a backup (git commit)

### Code Quality

- [ ] Replace magic numbers with constants/parameters
- [ ] Add NULL checks for pointers
- [ ] Use CheckPointer() for deallocation
- [ ] Follow naming conventions (see mql5-style.md)

### Memory Safety

- [ ] Every `new` has a corresponding `delete`
- [ ] Destructors clean up dynamic objects
- [ ] Pointer arrays are cleaned up in a loop
- [ ] Pointers are initialized to NULL

### Error Handling

- [ ] Check return values
- [ ] Log errors via Print()
- [ ] GetLastError() after critical operations
- [ ] Graceful degradation (fallback values)

## Common Patterns

### Singleton Manager

```cpp
class CManager {
private:
   static CManager* s_instance;
   CManager() {}

public:
   static CManager* GetInstance() {
      if(s_instance == NULL) {
         s_instance = new CManager();
      }
      return s_instance;
   }

   static void Destroy() {
      if(s_instance != NULL) {
         delete s_instance;
         s_instance = NULL;
      }
   }
};

CManager* CManager::s_instance = NULL;
```

### Strategy Pattern

```cpp
class CStrategy {
public:
   virtual ENUM_SIGNAL GetSignal() { return SIGNAL_NONE; }
   virtual void OnTick() {}
};

class CBreakoutStrategy : public CStrategy {
public:
   virtual ENUM_SIGNAL GetSignal() override {
      // Concrete implementation
   }
};
```

### Observer Pattern

```cpp
class IObserver {
public:
   virtual void OnEvent(int event_type, string data) = 0;
};

class CEventManager {
private:
   IObserver* m_observers[];

public:
   void Subscribe(IObserver* observer) {
      int size = ArraySize(m_observers);
      ArrayResize(m_observers, size + 1);
      m_observers[size] = observer;
   }

   void Notify(int event_type, string data) {
      for(int i = 0; i < ArraySize(m_observers); i++) {
         m_observers[i].OnEvent(event_type, data);
      }
   }
};
```

## Anti-Patterns to Fix

### God Class

```cpp
// BAD: One class does everything
class CMyEA {
   void ManageTrades();
   void CalculateRisk();
   void CheckSession();
   void DrawHUD();
   void LogTrades();
   // 2000+ lines
};

// GOOD: Separation of concerns
class CTradeManager { ... };
class CRiskManager { ... };
class CSessionManager { ... };
class CHUDManager { ... };
class CTradeLogger { ... };
```

### Magic Numbers

```cpp
// BAD
if(loss > 600) shutdown = true;
if(profit_pct > 0.5) MoveSL();

// GOOD
input double InpDailyLossLimit = 600.0;
const double BREAKEVEN_THRESHOLD = 0.5;
```

### Memory Leaks

```cpp
// BAD: Memory leak
void ProcessData() {
   CData* data = new CData();
   if(error) return;  // Leak!
   delete data;
}

// GOOD: Guaranteed cleanup
void ProcessData() {
   CData* data = new CData();
   if(error) {
      delete data;
      return;
   }
   delete data;
}
```

## Notes

- ALWAYS test after refactoring
- Make small incremental changes
- Preserve backward compatibility when possible
- Document breaking changes
