# API Integrator Subagent

Subagent profile for external API integration.

## Role

Specialist in integrating external services: Stripe, Supabase, Webhooks.

## Expertise Areas

### Stripe Integration

#### Main Scenarios

1. **EA Subscriptions**: Licensing via Stripe
2. **Usage Billing**: Pay-per-use billing
3. **Webhooks**: License status updates

#### MQL5 + Stripe (via WebRequest)

```cpp
// License verification
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

#### Security

```
NEVER store sk_live_ keys in code!

Options:
1. Server-side proxy (recommended)
2. Configuration file (FILE_COMMON)
3. Input parameter (passed at startup)
```

### Supabase Integration

#### REST API

```cpp
// Read data
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

// Write data
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

#### Use Cases

1. **Trade Logging**: Sending trades to the cloud
2. **Config Sync**: Parameter synchronization
3. **Performance Dashboard**: Real-time statistics

### Webhook Endpoints

#### Sending Data

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

#### Typical Events

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

### Allowing in MT5

```
Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL:
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

### Simple Parser (built-in)

```cpp
// MQL5 does not have a built-in JSON parser
// For simple cases - regex/StringFind

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
1. NEVER in source code
2. Use a server-side proxy
3. Or a configuration file (.gitignore!)
4. Or environment variable (via script)
```

### HTTPS Only

```cpp
// GOOD
string url = "https://api.example.com";

// BAD - never!
string url = "http://api.example.com";
```

### Rate Limiting

```cpp
datetime g_last_request = 0;
int      g_min_interval = 1000;  // 1 second

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
# Local mock server for testing
# Python example
python -m http.server 8000
```

### Postman/Insomnia

```
1. First test the API manually
2. Verify request/response format
3. Then implement in MQL5
```

## Notes

- WebRequest blocks execution -- use timeout
- For frequent requests -- cache results
- Log all API interactions for debugging
- Have a fallback if the API is unavailable
