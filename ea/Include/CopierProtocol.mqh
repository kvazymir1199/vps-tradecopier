//+------------------------------------------------------------------+
//| CopierProtocol.mqh — JSON builder/parser for Trade Copier       |
//| Builds and parses newline-delimited JSON messages                |
//+------------------------------------------------------------------+
#ifndef COPIER_PROTOCOL_MQH
#define COPIER_PROTOCOL_MQH

//+------------------------------------------------------------------+
//| JSON helper functions — string concatenation, no external libs   |
//+------------------------------------------------------------------+

/// Escapes a string value for safe JSON embedding.
/// Handles backslash, double-quote, and control characters.
string JsonEscape(string val)
{
   string result = val;
   // Backslash must be replaced first
   StringReplace(result, "\\", "\\\\");
   StringReplace(result, "\"", "\\\"");
   StringReplace(result, "\n", "\\n");
   StringReplace(result, "\r", "\\r");
   StringReplace(result, "\t", "\\t");
   return result;
}

/// "key":"val"
string JsonStr(string key, string val)
{
   return "\"" + key + "\":\"" + JsonEscape(val) + "\"";
}

/// "key":val  (numeric, up to 8 decimal places, trailing zeros stripped)
string JsonNum(string key, double val)
{
   string s = DoubleToString(val, 8);
   // Strip trailing zeros after decimal point
   if(StringFind(s, ".") >= 0)
   {
      int len = StringLen(s);
      while(len > 1 && StringGetCharacter(s, len - 1) == '0')
         len--;
      if(StringGetCharacter(s, len - 1) == '.')
         len--;
      s = StringSubstr(s, 0, len);
   }
   return "\"" + key + "\":" + s;
}

/// "key":val  (integer)
string JsonInt(string key, long val)
{
   return "\"" + key + "\":" + IntegerToString(val);
}

//+------------------------------------------------------------------+
//| Timestamp helper                                                 |
//+------------------------------------------------------------------+
long GetTimestampMs()
{
   return (long)TimeGMT() * 1000;
}

//+------------------------------------------------------------------+
//| Build JSON array of MarketWatch symbols                          |
//+------------------------------------------------------------------+
string BuildSymbolsArray()
{
   string result = "";
   int total = SymbolsTotal(true);  // true = only MarketWatch
   for(int i = 0; i < total; i++)
   {
      string sym = SymbolName(i, true);
      if(i > 0) result += ",";
      result += "\"" + sym + "\"";
   }
   return result;
}

//+------------------------------------------------------------------+
//| Message builders                                                 |
//+------------------------------------------------------------------+

string BuildOpenMessage(int msgId, string masterId, long ticket,
                        string symbol, string direction, double volume,
                        double price, double sl, double tp,
                        long magic, string comment)
{
   string json = "{";
   json += JsonInt("msg_id", msgId)          + ",";
   json += JsonStr("master_id", masterId)    + ",";
   json += JsonStr("type", "OPEN")           + ",";
   json += JsonInt("ts_ms", GetTimestampMs())+ ",";
   json += "\"payload\":{";
   json += JsonInt("ticket", ticket)         + ",";
   json += JsonStr("symbol", symbol)         + ",";
   json += JsonStr("direction", direction)   + ",";
   json += JsonNum("volume", volume)         + ",";
   json += JsonNum("price", price)           + ",";
   json += JsonNum("sl", sl)                 + ",";
   json += JsonNum("tp", tp)                 + ",";
   json += JsonInt("magic", magic)           + ",";
   json += JsonStr("comment", comment);
   json += "}}";
   return json;
}

//+------------------------------------------------------------------+
string BuildModifyMessage(int msgId, string masterId, long ticket,
                          long magic, double sl, double tp)
{
   string json = "{";
   json += JsonInt("msg_id", msgId)          + ",";
   json += JsonStr("master_id", masterId)    + ",";
   json += JsonStr("type", "MODIFY")         + ",";
   json += JsonInt("ts_ms", GetTimestampMs())+ ",";
   json += "\"payload\":{";
   json += JsonInt("ticket", ticket)         + ",";
   json += JsonInt("magic", magic)           + ",";
   json += JsonNum("sl", sl)                 + ",";
   json += JsonNum("tp", tp);
   json += "}}";
   return json;
}

//+------------------------------------------------------------------+
string BuildCloseMessage(int msgId, string masterId, long ticket, long magic)
{
   string json = "{";
   json += JsonInt("msg_id", msgId)          + ",";
   json += JsonStr("master_id", masterId)    + ",";
   json += JsonStr("type", "CLOSE")          + ",";
   json += JsonInt("ts_ms", GetTimestampMs())+ ",";
   json += "\"payload\":{";
   json += JsonInt("ticket", ticket)         + ",";
   json += JsonInt("magic", magic);
   json += "}}";
   return json;
}

//+------------------------------------------------------------------+
string BuildClosePartialMessage(int msgId, string masterId, long ticket,
                                long magic, double volume)
{
   string json = "{";
   json += JsonInt("msg_id", msgId)          + ",";
   json += JsonStr("master_id", masterId)    + ",";
   json += JsonStr("type", "CLOSE_PARTIAL")  + ",";
   json += JsonInt("ts_ms", GetTimestampMs())+ ",";
   json += "\"payload\":{";
   json += JsonInt("ticket", ticket)         + ",";
   json += JsonInt("magic", magic)           + ",";
   json += JsonNum("volume", volume);
   json += "}}";
   return json;
}

//+------------------------------------------------------------------+
string BuildHeartbeatMessage(string terminalId, string vpsId,
                             long account, string broker,
                             int statusCode, string statusMsg,
                             string lastError)
{
   string json = "{";
   json += JsonStr("type", "HEARTBEAT")        + ",";
   json += JsonInt("ts_ms", GetTimestampMs())   + ",";
   json += JsonStr("terminal_id", terminalId)   + ",";
   json += JsonStr("vps_id", vpsId)             + ",";
   json += JsonInt("account", account)           + ",";
   json += JsonStr("broker", broker)             + ",";
   json += "\"payload\":{";
   json += JsonInt("status_code", statusCode)    + ",";
   json += JsonStr("status_msg", statusMsg)      + ",";
   json += JsonStr("last_error", lastError)      + ",";
   json += "\"symbols\":[" + BuildSymbolsArray() + "]";
   json += "}}";
   return json;
}

//+------------------------------------------------------------------+
string BuildRegisterMessage(string terminalId, string role,
                            long account, string broker)
{
   string json = "{";
   json += JsonStr("type", "REGISTER")         + ",";
   json += JsonInt("ts_ms", GetTimestampMs())   + ",";
   json += JsonStr("terminal_id", terminalId)   + ",";
   json += JsonStr("role", role)                 + ",";
   json += JsonInt("account", account)           + ",";
   json += JsonStr("broker", broker)             + ",";
   json += "\"symbols\":[" + BuildSymbolsArray() + "]";
   json += "}";
   return json;
}

//+------------------------------------------------------------------+
//| Parser — SlaveCommand data received from Hub                     |
//+------------------------------------------------------------------+
struct SlaveCommandData
{
   int      msgId;
   string   masterId;
   string   slaveId;
   string   type;
   long     masterTicket;
   string   symbol;
   string   direction;
   string   orderType;    // "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"
   double   volume;
   double   price;
   double   sl;
   double   tp;
   long     magic;
   string   comment;

   void Reset()
   {
      msgId        = 0;
      masterId     = "";
      slaveId      = "";
      type         = "";
      masterTicket = 0;
      symbol       = "";
      direction    = "";
      orderType    = "";
      volume       = 0.0;
      price        = 0.0;
      sl           = 0.0;
      tp           = 0.0;
      magic        = 0;
      comment      = "";
   }
};

//+------------------------------------------------------------------+
//| Internal parser helpers                                          |
//+------------------------------------------------------------------+

/// Extract a string value for a given key from JSON.
/// Searches for "key":"value" pattern.
string _JsonExtractStr(const string &json, string key)
{
   string needle = "\"" + key + "\":\"";
   int pos = StringFind(json, needle);
   if(pos < 0)
      return "";

   int valStart = pos + StringLen(needle);
   // Find closing quote, handling escaped quotes
   int i = valStart;
   int jsonLen = StringLen(json);
   string result = "";

   while(i < jsonLen)
   {
      ushort ch = StringGetCharacter(json, i);
      if(ch == '\\' && i + 1 < jsonLen)
      {
         ushort next = StringGetCharacter(json, i + 1);
         if(next == '"')       { result += "\""; i += 2; continue; }
         if(next == '\\')      { result += "\\"; i += 2; continue; }
         if(next == 'n')       { result += "\n"; i += 2; continue; }
         if(next == 'r')       { result += "\r"; i += 2; continue; }
         if(next == 't')       { result += "\t"; i += 2; continue; }
         result += ShortToString(ch);
         i++;
         continue;
      }
      if(ch == '"')
         break;
      result += ShortToString(ch);
      i++;
   }

   return result;
}

/// Extract a numeric value (integer or float) for a given key from JSON.
/// Searches for "key":123 or "key":1.5 pattern.
string _JsonExtractNum(const string &json, string key)
{
   string needle = "\"" + key + "\":";
   int pos = StringFind(json, needle);
   if(pos < 0)
      return "";

   int valStart = pos + StringLen(needle);
   int jsonLen = StringLen(json);

   // Skip whitespace
   while(valStart < jsonLen)
   {
      ushort ch = StringGetCharacter(json, valStart);
      if(ch != ' ' && ch != '\t')
         break;
      valStart++;
   }

   // Skip if it's a string value (starts with quote)
   if(valStart < jsonLen && StringGetCharacter(json, valStart) == '"')
      return "";

   // Read until delimiter
   int i = valStart;
   while(i < jsonLen)
   {
      ushort ch = StringGetCharacter(json, i);
      if(ch == ',' || ch == '}' || ch == ']' || ch == ' ' || ch == '\n' || ch == '\r')
         break;
      i++;
   }

   if(i == valStart)
      return "";

   return StringSubstr(json, valStart, i - valStart);
}

//+------------------------------------------------------------------+
//| ParseSlaveCommand — parse a JSON string into SlaveCommandData    |
//+------------------------------------------------------------------+
bool ParseSlaveCommand(const string &json, SlaveCommandData &data)
{
   data.Reset();

   if(StringLen(json) == 0)
      return false;

   // Verify it looks like JSON
   if(StringFind(json, "{") < 0)
      return false;

   // Top-level fields
   string sMsgId = _JsonExtractNum(json, "msg_id");
   if(sMsgId == "")
   {
      Print("[CopierProtocol] ParseSlaveCommand: missing msg_id");
      return false;
   }
   data.msgId = (int)StringToInteger(sMsgId);

   data.masterId = _JsonExtractStr(json, "master_id");
   data.slaveId  = _JsonExtractStr(json, "slave_id");
   data.type     = _JsonExtractStr(json, "type");

   if(data.type == "")
   {
      Print("[CopierProtocol] ParseSlaveCommand: missing type");
      return false;
   }

   // Payload fields — these live inside "payload":{...} but our flat
   // search works since key names are unique across the message.
   string sTicket = _JsonExtractNum(json, "ticket");
   if(sTicket != "")
      data.masterTicket = StringToInteger(sTicket);

   data.symbol    = _JsonExtractStr(json, "symbol");
   data.direction = _JsonExtractStr(json, "direction");
   data.orderType = _JsonExtractStr(json, "order_type");

   string sVolume = _JsonExtractNum(json, "volume");
   if(sVolume != "")
      data.volume = StringToDouble(sVolume);

   string sPrice = _JsonExtractNum(json, "price");
   if(sPrice != "")
      data.price = StringToDouble(sPrice);

   string sSl = _JsonExtractNum(json, "sl");
   if(sSl != "")
      data.sl = StringToDouble(sSl);

   string sTp = _JsonExtractNum(json, "tp");
   if(sTp != "")
      data.tp = StringToDouble(sTp);

   string sMagic = _JsonExtractNum(json, "magic");
   if(sMagic != "")
      data.magic = StringToInteger(sMagic);

   data.comment = _JsonExtractStr(json, "comment");

   return true;
}

//+------------------------------------------------------------------+
//| Pending order message builders                                   |
//+------------------------------------------------------------------+

string BuildPendingPlaceMessage(int msgId, string masterId, long ticket,
                                string symbol, string orderType, double volume,
                                double price, double sl, double tp,
                                long magic, string comment)
{
   string json = "{";
   json += JsonInt("msg_id", msgId)          + ",";
   json += JsonStr("master_id", masterId)    + ",";
   json += JsonStr("type", "PENDING_PLACE")  + ",";
   json += JsonInt("ts_ms", GetTimestampMs())+ ",";
   json += "\"payload\":{";
   json += JsonInt("ticket", ticket)         + ",";
   json += JsonStr("symbol", symbol)         + ",";
   json += JsonStr("order_type", orderType)  + ",";
   json += JsonNum("volume", volume)         + ",";
   json += JsonNum("price", price)           + ",";
   json += JsonNum("sl", sl)                 + ",";
   json += JsonNum("tp", tp)                 + ",";
   json += JsonInt("magic", magic)           + ",";
   json += JsonStr("comment", comment);
   json += "}}";
   return json;
}

//+------------------------------------------------------------------+
string BuildPendingModifyMessage(int msgId, string masterId, long ticket,
                                 long magic, double price, double sl, double tp)
{
   string json = "{";
   json += JsonInt("msg_id", msgId)            + ",";
   json += JsonStr("master_id", masterId)      + ",";
   json += JsonStr("type", "PENDING_MODIFY")   + ",";
   json += JsonInt("ts_ms", GetTimestampMs())  + ",";
   json += "\"payload\":{";
   json += JsonInt("ticket", ticket)           + ",";
   json += JsonInt("magic", magic)             + ",";
   json += JsonNum("price", price)             + ",";
   json += JsonNum("sl", sl)                   + ",";
   json += JsonNum("tp", tp);
   json += "}}";
   return json;
}

//+------------------------------------------------------------------+
string BuildPendingDeleteMessage(int msgId, string masterId, long ticket,
                                 long magic)
{
   string json = "{";
   json += JsonInt("msg_id", msgId)            + ",";
   json += JsonStr("master_id", masterId)      + ",";
   json += JsonStr("type", "PENDING_DELETE")   + ",";
   json += JsonInt("ts_ms", GetTimestampMs())  + ",";
   json += "\"payload\":{";
   json += JsonInt("ticket", ticket)           + ",";
   json += JsonInt("magic", magic);
   json += "}}";
   return json;
}

#endif // COPIER_PROTOCOL_MQH
