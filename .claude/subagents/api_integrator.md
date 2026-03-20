# API Integrator Subagent

Профиль субагента для интеграции внешних API.

## Role

Специалист по интеграции внешних сервисов: Stripe, Supabase, Webhooks.

## Expertise Areas

### Stripe Integration

#### Основные сценарии

1. **Подписки для EA**: Лицензирование через Stripe
2. **Usage Billing**: Оплата по использованию
3. **Webhooks**: Обновление статуса лицензии

#### MQL5 + Stripe (через WebRequest)

```cpp
// Проверка лицензии
string CheckLicense(string license_key) {
   string url = "https://api.stripe.com/v1/subscriptions";
   char   post_data[];
   char   result[];
   string headers = "Authorization: Bearer sk_live_xxx\r\n"
                    "Content-Type: application/x-www-form-urlencoded";

   int res = WebRequest(
      "GET",
      url + "?customer=" + license_key,
      headers,
      5000,
      post_data,
      result,
      headers
   );

   if(res == 200) {
      return CharArrayToString(result);
   }
   return "";
}
```

#### Безопасность

```
⚠️ НИКОГДА не храни sk_live_ ключи в коде!

Варианты:
1. Серверный прокси (рекомендуется)
2. Файл конфигурации (FILE_COMMON)
3. Input параметр (передача при запуске)
```

### Supabase Integration

#### REST API

```cpp
// Чтение данных
string FetchData(string table, string filter) {
   string url = "https://<project>.supabase.co/rest/v1/" + table;
   if(filter != "") url += "?" + filter;

   char   post_data[];
   char   result[];
   string headers = "apikey: <anon_key>\r\n"
                    "Authorization: Bearer <anon_key>";

   int res = WebRequest("GET", url, headers, 5000, post_data, result, headers);
   return CharArrayToString(result);
}

// Запись данных
bool InsertData(string table, string json_data) {
   string url = "https://<project>.supabase.co/rest/v1/" + table;

   char   post_data[];
   char   result[];
   string headers = "apikey: <anon_key>\r\n"
                    "Authorization: Bearer <anon_key>\r\n"
                    "Content-Type: application/json\r\n"
                    "Prefer: return=minimal";

   StringToCharArray(json_data, post_data);

   int res = WebRequest("POST", url, headers, 5000, post_data, result, headers);
   return (res == 201);
}
```

#### Сценарии использования

1. **Trade Logging**: Отправка сделок в облако
2. **Config Sync**: Синхронизация параметров
3. **Performance Dashboard**: Статистика в реальном времени

### Webhook Endpoints

#### Отправка данных

```cpp
void SendWebhook(string url, string payload) {
   char   post_data[];
   char   result[];
   string headers = "Content-Type: application/json";

   StringToCharArray(payload, post_data);

   int res = WebRequest("POST", url, headers, 5000, post_data, result, headers);

   if(res != 200) {
      Print("[Webhook] Failed: ", res, " - ", GetLastError());
   }
}
```

#### Типичные события

```json
// Trade Opened
{
  "event": "trade_opened",
  "symbol": "AAPL.US",
  "direction": "BUY",
  "entry_price": 185.50,
  "volume": 0.54,
  "timestamp": "2024-01-15T10:30:00Z"
}

// Trade Closed
{
  "event": "trade_closed",
  "symbol": "AAPL.US",
  "exit_reason": "TS",
  "profit": 125.50,
  "duration_seconds": 342
}

// Alert
{
  "event": "alert",
  "type": "daily_loss_limit",
  "message": "Daily loss limit reached: $600",
  "action": "shutdown"
}
```

## WebRequest Setup

### Разрешение в MT5

```
Tools → Options → Expert Advisors → Allow WebRequest for listed URL:
- https://api.stripe.com
- https://<project>.supabase.co
- https://your-webhook-endpoint.com
```

### Error Handling

```cpp
int res = WebRequest(...);

switch(res) {
   case -1:
      Print("[API] WebRequest error: ", GetLastError());
      break;
   case 200:
   case 201:
      // Success
      break;
   case 401:
      Print("[API] Unauthorized - check API key");
      break;
   case 429:
      Print("[API] Rate limited - slow down");
      Sleep(1000);
      break;
   default:
      Print("[API] HTTP error: ", res);
}
```

## JSON Handling

### Simple Parser (встроенный)

```cpp
// MQL5 не имеет встроенного JSON парсера
// Для простых случаев - regex/StringFind

string GetJsonValue(string json, string key) {
   string search = "\"" + key + "\":\"";
   int start = StringFind(json, search);
   if(start < 0) return "";

   start += StringLen(search);
   int end = StringFind(json, "\"", start);
   return StringSubstr(json, start, end - start);
}
```

### JSON Builder

```cpp
string BuildJson(string& keys[], string& values[]) {
   string json = "{";
   for(int i = 0; i < ArraySize(keys); i++) {
      if(i > 0) json += ",";
      json += "\"" + keys[i] + "\":\"" + values[i] + "\"";
   }
   json += "}";
   return json;
}
```

## Security Best Practices

### API Keys

```
1. НИКОГДА в исходном коде
2. Используй серверный прокси
3. Или файл конфигурации (.gitignore!)
4. Или environment variable (через скрипт)
```

### HTTPS Only

```cpp
// ХОРОШО
string url = "https://api.example.com";

// ПЛОХО - никогда!
string url = "http://api.example.com";
```

### Rate Limiting

```cpp
datetime g_last_request = 0;
int      g_min_interval = 1000;  // 1 секунда

bool CanMakeRequest() {
   if(TimeCurrent() - g_last_request < g_min_interval / 1000) {
      return false;
   }
   g_last_request = TimeCurrent();
   return true;
}
```

## Testing

### Mock Server

```bash
# Локальный mock сервер для тестирования
# Python example
python -m http.server 8000
```

### Postman/Insomnia

```
1. Сначала тестируй API вручную
2. Проверь формат запроса/ответа
3. Затем имплементируй в MQL5
```

## Notes

- WebRequest блокирует выполнение — используй timeout
- Для частых запросов — кэшируй результаты
- Логируй все API взаимодействия для отладки
- Имей fallback если API недоступен
