//+------------------------------------------------------------------+
//| TradeCopierSlave.mq5                                             |
//| Slave EA: receives commands from Python Hub, executes trades,    |
//| sends ACK/NACK back via ack pipe.                                |
//+------------------------------------------------------------------+
#property copyright "Tino-V"
#property version   "1.00"
#property strict

#include "..\Include\CopierLogger.mqh"
#include "..\Include\CopierPipe.mqh"
#include "..\Include\CopierProtocol.mqh"
#include "..\Include\CopierDatabase.mqh"
#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input int    HeartbeatSec  = 10;
input int    MaxSlippage   = 10;

//+------------------------------------------------------------------+
//| Idempotency tracker: last processed msg_id per master_id         |
//+------------------------------------------------------------------+
#define MAX_MASTERS 32

struct MasterIdempotency
{
   string master_id;
   int    last_msg_id;
};

//+------------------------------------------------------------------+
//| Global variables                                                 |
//+------------------------------------------------------------------+
CCopierLogger      g_logger;
CCopierPipe        g_cmdPipe;
CCopierPipe        g_ackPipe;
CTrade             g_trade;

MasterIdempotency  g_idempotency[];
int                g_idempotencyCount;
bool               g_idempotencyDirty;

datetime           g_lastHeartbeat;

// Auto-generated from account number
string g_terminalId;
string g_cmdPipeName;
string g_ackPipeName;
string g_dbFile = "TradeCopier\\copier.db";
string g_vpsId  = "vps_1";

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Auto-generate terminal ID and pipe names from account number
   long account = AccountInfoInteger(ACCOUNT_LOGIN);
   g_terminalId  = "slave_" + IntegerToString(account);
   g_cmdPipeName = "copier_slave_" + IntegerToString(account) + "_cmd";
   g_ackPipeName = "copier_slave_" + IntegerToString(account) + "_ack";

   g_logger.Init("Slave_" + g_terminalId);
   g_logger.Info("=== TradeCopierSlave initializing ===");
   g_logger.Info(StringFormat("TerminalID=%s  CmdPipe=%s  AckPipe=%s  HB=%ds  Slip=%d",
                              g_terminalId, g_cmdPipeName, g_ackPipeName,
                              HeartbeatSec, MaxSlippage));

   //--- Configure CTrade
   g_trade.SetExpertMagicNumber(0);
   g_trade.SetDeviationInPoints(MaxSlippage);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   //--- Initialize idempotency tracker
   g_idempotencyCount = 0;
   g_idempotencyDirty = false;
   ArrayResize(g_idempotency, MAX_MASTERS);

   //--- Restore idempotency state from previous session
   LoadIdempotencyState();

   //--- Register in shared SQLite DB so Hub discovers us
   if(!RegisterTerminalInDB(g_terminalId, "slave", g_dbFile))
      g_logger.Error("DB registration failed — Hub won't auto-create pipe");

   //--- Connect pipes (silent — Hub may not have created them yet)
   bool cmdOk = g_cmdPipe.Connect(g_cmdPipeName, true);
   bool ackOk = g_ackPipe.Connect(g_ackPipeName, true);

   if(!cmdOk || !ackOk)
      g_logger.Info("Waiting for Hub to create pipes...");

   //--- Send REGISTER via ack pipe
   if(ackOk)
   {
      string regMsg = BuildRegisterMessage(g_terminalId, "SLAVE",
                                           AccountInfoInteger(ACCOUNT_LOGIN),
                                           AccountInfoString(ACCOUNT_COMPANY));
      if(g_ackPipe.Send(regMsg))
         g_logger.Info("REGISTER sent via ack pipe");
      else
         g_logger.Error("Failed to send REGISTER");
   }

   //--- Start 100ms timer
   g_lastHeartbeat = TimeLocal();
   EventSetMillisecondTimer(100);

   g_logger.Info("Init complete");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   SaveIdempotencyState();
   EventKillTimer();
   g_cmdPipe.Disconnect();
   g_ackPipe.Disconnect();
   g_logger.Info(StringFormat("Shutdown (reason=%d)", reason));
}

//+------------------------------------------------------------------+
//| OnTimer — poll cmd pipe, execute, send ACK/NACK, heartbeat       |
//+------------------------------------------------------------------+
void OnTimer()
{
   //--- Ensure pipes are connected (silent retries, log only on success)
   if(!g_cmdPipe.IsConnected())
   {
      if(!g_cmdPipe.Connect(g_cmdPipeName, true))
         return;
      g_logger.Info("Cmd pipe connected");
   }

   if(!g_ackPipe.IsConnected())
   {
      if(!g_ackPipe.Connect(g_ackPipeName, true))
         return;

      //--- Re-register after reconnect
      string regMsg = BuildRegisterMessage(g_terminalId, "SLAVE",
                                           AccountInfoInteger(ACCOUNT_LOGIN),
                                           AccountInfoString(ACCOUNT_COMPANY));
      g_ackPipe.Send(regMsg);
      g_logger.Info("Re-registered via ack pipe after reconnect");
   }

   //--- Poll cmd pipe for commands
   string raw = g_cmdPipe.Receive();
   while(StringLen(raw) > 0)
   {
      g_logger.Debug(StringFormat("Cmd received: %s", raw));
      ProcessCommand(raw);
      raw = g_cmdPipe.Receive();
   }
   if(g_idempotencyDirty)
   {
      SaveIdempotencyState();
      g_idempotencyDirty = false;
   }

   //--- Heartbeat
   if(TimeLocal() - g_lastHeartbeat >= HeartbeatSec)
   {
      int broker_connected = (int)TerminalInfoInteger(TERMINAL_CONNECTED);
      int status_code = broker_connected ? 0 : 1;
      string status_msg = broker_connected ? "OK" : "No broker connection";

      string hbMsg = BuildHeartbeatMessage(g_terminalId, g_vpsId,
                                           AccountInfoInteger(ACCOUNT_LOGIN),
                                           AccountInfoString(ACCOUNT_COMPANY),
                                           status_code, status_msg, "");
      if(g_ackPipe.Send(hbMsg))
         g_logger.Debug("Heartbeat sent");
      else
         g_logger.Error("Heartbeat send failed");

      g_lastHeartbeat = TimeLocal();
   }
}

//+------------------------------------------------------------------+
//| Process a single command from the Hub                            |
//+------------------------------------------------------------------+
void ProcessCommand(string raw)
{
   SlaveCommandData cmd;
   if(!ParseSlaveCommand(raw, cmd))
   {
      g_logger.Error(StringFormat("Failed to parse command: %s", raw));
      return;
   }

   g_logger.Info(StringFormat("Processing: type=%s msg_id=%d master=%s magic=%d",
                              cmd.type, cmd.msgId, cmd.masterId, cmd.magic));

   //--- Idempotency check
   if(IsDuplicateMessage(cmd.masterId, cmd.msgId))
   {
      g_logger.Info(StringFormat("Duplicate msg_id=%d from %s — skipping", cmd.msgId, cmd.masterId));
      SendAck(cmd.msgId, 0);
      return;
   }

   //--- Execute based on type
   if(cmd.type == "OPEN")
      ExecuteOpen(cmd);
   else if(cmd.type == "MODIFY")
      ExecuteModify(cmd);
   else if(cmd.type == "CLOSE")
      ExecuteClose(cmd);
   else if(cmd.type == "CLOSE_PARTIAL")
      ExecuteClosePartial(cmd);
   else if(cmd.type == "PENDING_PLACE")
      ExecutePendingPlace(cmd);
   else if(cmd.type == "PENDING_MODIFY")
      ExecutePendingModify(cmd);
   else if(cmd.type == "PENDING_DELETE")
      ExecutePendingDelete(cmd);
   else
   {
      g_logger.Error(StringFormat("Unknown command type: %s", cmd.type));
      SendNack(cmd.msgId, "UNKNOWN_TYPE");
      return;
   }

   //--- Mark as processed
   RecordProcessedMessage(cmd.masterId, cmd.msgId);
   g_idempotencyDirty = true;
}

//+------------------------------------------------------------------+
//| Execute OPEN command                                             |
//+------------------------------------------------------------------+
void ExecuteOpen(SlaveCommandData &cmd)
{
   //--- If there's a pending order with this magic, delete it first (activation scenario)
   ulong pendingTicket = FindOrderByMagic(cmd.magic);
   if(pendingTicket != 0)
   {
      g_trade.OrderDelete(pendingTicket);
      g_logger.Info(StringFormat("Deleted pending order %d (magic=%d) before market OPEN",
                                 pendingTicket, cmd.magic));
   }

   //--- Validate symbol
   if(!SymbolInfoInteger(cmd.symbol, SYMBOL_EXIST))
   {
      g_logger.Error(StringFormat("Symbol not found: %s", cmd.symbol));
      SendNack(cmd.msgId, "SYMBOL_NOT_FOUND");
      return;
   }

   //--- Ensure symbol is in MarketWatch
   SymbolSelect(cmd.symbol, true);

   //--- Check if trading is enabled
   if(!SymbolInfoInteger(cmd.symbol, SYMBOL_TRADE_MODE))
   {
      g_logger.Error(StringFormat("Trading disabled for %s", cmd.symbol));
      SendNack(cmd.msgId, "TRADE_DISABLED");
      return;
   }

   //--- Normalize volume
   double volumeStep = SymbolInfoDouble(cmd.symbol, SYMBOL_VOLUME_STEP);
   double volumeMin  = SymbolInfoDouble(cmd.symbol, SYMBOL_VOLUME_MIN);
   double volumeMax  = SymbolInfoDouble(cmd.symbol, SYMBOL_VOLUME_MAX);

   double normalizedVol = NormalizeVolume(cmd.volume, volumeStep);

   if(normalizedVol < volumeMin)
   {
      g_logger.Error(StringFormat("Volume %.4f < min %.4f for %s",
                                  normalizedVol, volumeMin, cmd.symbol));
      SendNack(cmd.msgId, "INVALID_VOLUME");
      return;
   }

   if(normalizedVol > volumeMax)
   {
      g_logger.Info(StringFormat("Volume %.4f capped to max %.4f for %s",
                                 normalizedVol, volumeMax, cmd.symbol));
      normalizedVol = volumeMax;
   }

   //--- Set magic for the trade
   g_trade.SetExpertMagicNumber(cmd.magic);

   //--- Determine order type
   ENUM_ORDER_TYPE orderType = (cmd.direction == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double price = (cmd.direction == "BUY")
                  ? SymbolInfoDouble(cmd.symbol, SYMBOL_ASK)
                  : SymbolInfoDouble(cmd.symbol, SYMBOL_BID);

   //--- Execute
   string comment = cmd.comment;
   if(StringLen(comment) == 0)
      comment = StringFormat("Copy:%s:%d", cmd.masterId, cmd.masterTicket);

   bool result = g_trade.PositionOpen(cmd.symbol, orderType, normalizedVol,
                                      price, cmd.sl, cmd.tp, comment);

   if(result)
   {
      ulong dealTicket = g_trade.ResultDeal();
      // The position ticket may differ from the deal ticket;
      // use ResultOrder for the position ticket if available
      ulong posTicket = g_trade.ResultOrder();
      if(posTicket == 0)
         posTicket = dealTicket;

      g_logger.Info(StringFormat("OPEN success: sym=%s dir=%s vol=%.2f ticket=%d",
                                 cmd.symbol, cmd.direction, normalizedVol, posTicket));
      SendAck(cmd.msgId, (long)posTicket);
   }
   else
   {
      uint retcode = g_trade.ResultRetcode();
      g_logger.Error(StringFormat("OPEN failed: sym=%s retcode=%d comment=%s",
                                  cmd.symbol, retcode, g_trade.ResultComment()));
      SendNack(cmd.msgId, "ORDER_FAILED");
   }
}

//+------------------------------------------------------------------+
//| Execute MODIFY command                                           |
//+------------------------------------------------------------------+
void ExecuteModify(SlaveCommandData &cmd)
{
   ulong ticket = FindPositionByMagic(cmd.magic);
   if(ticket == 0)
   {
      g_logger.Error(StringFormat("MODIFY: no position with magic=%d", cmd.magic));
      SendNack(cmd.msgId, "ORDER_FAILED");
      return;
   }

   bool result = g_trade.PositionModify(ticket, cmd.sl, cmd.tp);

   if(result)
   {
      g_logger.Info(StringFormat("MODIFY success: ticket=%d sl=%.5f tp=%.5f",
                                 ticket, cmd.sl, cmd.tp));
      SendAck(cmd.msgId, (long)ticket);
   }
   else
   {
      uint retcode = g_trade.ResultRetcode();
      g_logger.Error(StringFormat("MODIFY failed: ticket=%d retcode=%d comment=%s",
                                  ticket, retcode, g_trade.ResultComment()));
      SendNack(cmd.msgId, "ORDER_FAILED");
   }
}

//+------------------------------------------------------------------+
//| Execute CLOSE command                                            |
//+------------------------------------------------------------------+
void ExecuteClose(SlaveCommandData &cmd)
{
   ulong ticket = FindPositionByMagic(cmd.magic);
   if(ticket == 0)
   {
      g_logger.Error(StringFormat("CLOSE: no position with magic=%d", cmd.magic));
      SendNack(cmd.msgId, "ORDER_FAILED");
      return;
   }

   bool result = g_trade.PositionClose(ticket);

   if(result)
   {
      g_logger.Info(StringFormat("CLOSE success: ticket=%d", ticket));
      SendAck(cmd.msgId, (long)ticket);
   }
   else
   {
      uint retcode = g_trade.ResultRetcode();
      g_logger.Error(StringFormat("CLOSE failed: ticket=%d retcode=%d comment=%s",
                                  ticket, retcode, g_trade.ResultComment()));
      SendNack(cmd.msgId, "ORDER_FAILED");
   }
}

//+------------------------------------------------------------------+
//| Execute CLOSE_PARTIAL command                                    |
//+------------------------------------------------------------------+
void ExecuteClosePartial(SlaveCommandData &cmd)
{
   ulong ticket = FindPositionByMagic(cmd.magic);
   if(ticket == 0)
   {
      g_logger.Error(StringFormat("CLOSE_PARTIAL: no position with magic=%d", cmd.magic));
      SendNack(cmd.msgId, "ORDER_FAILED");
      return;
   }

   //--- Select the position to get symbol for volume normalization
   if(!PositionSelectByTicket(ticket))
   {
      g_logger.Error(StringFormat("CLOSE_PARTIAL: cannot select ticket=%d", ticket));
      SendNack(cmd.msgId, "ORDER_FAILED");
      return;
   }

   string sym = PositionGetString(POSITION_SYMBOL);

   //--- Normalize volume
   double volumeStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double volumeMin  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);

   double normalizedVol = NormalizeVolume(cmd.volume, volumeStep);

   if(normalizedVol < volumeMin)
   {
      g_logger.Error(StringFormat("CLOSE_PARTIAL: volume %.4f < min %.4f for %s",
                                  normalizedVol, volumeMin, sym));
      SendNack(cmd.msgId, "INVALID_VOLUME");
      return;
   }

   bool result = g_trade.PositionClosePartial(ticket, normalizedVol);

   if(result)
   {
      g_logger.Info(StringFormat("CLOSE_PARTIAL success: ticket=%d vol=%.2f",
                                 ticket, normalizedVol));
      SendAck(cmd.msgId, (long)ticket);
   }
   else
   {
      uint retcode = g_trade.ResultRetcode();
      g_logger.Error(StringFormat("CLOSE_PARTIAL failed: ticket=%d retcode=%d comment=%s",
                                  ticket, retcode, g_trade.ResultComment()));
      SendNack(cmd.msgId, "ORDER_FAILED");
   }
}

//+------------------------------------------------------------------+
//| Find position by magic number                                    |
//+------------------------------------------------------------------+
ulong FindPositionByMagic(long magic)
{
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if((long)PositionGetInteger(POSITION_MAGIC) == magic)
         return ticket;
   }
   return 0;
}

//+------------------------------------------------------------------+
//| Normalize volume to step size                                    |
//+------------------------------------------------------------------+
double NormalizeVolume(double volume, double step)
{
   if(step <= 0)
      return volume;

   return MathFloor(volume / step) * step;
}

//+------------------------------------------------------------------+
//| Send ACK via ack pipe                                            |
//+------------------------------------------------------------------+
void SendAck(int msgId, long slaveTicket)
{
   string json = "{" +
      JsonInt("msg_id", msgId) + "," +
      JsonStr("slave_id", g_terminalId) + "," +
      JsonStr("ack_type", "ACK") + "," +
      JsonInt("slave_ticket", slaveTicket) + "," +
      JsonInt("ts_ms", GetTimestampMs()) +
      "}";

   if(!g_ackPipe.Send(json))
      g_logger.Error(StringFormat("Failed to send ACK for msg_id=%d", msgId));
}

//+------------------------------------------------------------------+
//| Send NACK via ack pipe                                           |
//+------------------------------------------------------------------+
void SendNack(int msgId, string reason)
{
   string json = "{" +
      JsonInt("msg_id", msgId) + "," +
      JsonStr("slave_id", g_terminalId) + "," +
      JsonStr("ack_type", "NACK") + "," +
      JsonStr("reason", reason) + "," +
      JsonInt("ts_ms", GetTimestampMs()) +
      "}";

   if(!g_ackPipe.Send(json))
      g_logger.Error(StringFormat("Failed to send NACK for msg_id=%d reason=%s", msgId, reason));
}

//+------------------------------------------------------------------+
//| Idempotency: check if message was already processed              |
//+------------------------------------------------------------------+
bool IsDuplicateMessage(string masterId, int msgId)
{
   for(int i = 0; i < g_idempotencyCount; i++)
   {
      if(g_idempotency[i].master_id == masterId)
         return (msgId <= g_idempotency[i].last_msg_id);
   }
   return false;
}

//+------------------------------------------------------------------+
//| Idempotency: record a processed message                         |
//+------------------------------------------------------------------+
void RecordProcessedMessage(string masterId, int msgId)
{
   for(int i = 0; i < g_idempotencyCount; i++)
   {
      if(g_idempotency[i].master_id == masterId)
      {
         if(msgId > g_idempotency[i].last_msg_id)
            g_idempotency[i].last_msg_id = msgId;
         return;
      }
   }

   //--- New master_id
   if(g_idempotencyCount < MAX_MASTERS)
   {
      g_idempotency[g_idempotencyCount].master_id   = masterId;
      g_idempotency[g_idempotencyCount].last_msg_id  = msgId;
      g_idempotencyCount++;
   }
   else
   {
      g_logger.Error(StringFormat("Idempotency table full (max %d masters)", MAX_MASTERS));
   }
}

//+------------------------------------------------------------------+
//| LoadIdempotencyState — restore last_msg_id per master from file  |
//| File: MQL5/Files/copier_idem_<account>.csv                       |
//| Format per line: master_id,last_msg_id                           |
//+------------------------------------------------------------------+
void LoadIdempotencyState()
{
   string filename = "copier_idem_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".csv";
   int handle = FileOpen(filename, FILE_READ | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      g_logger.Info("[Slave] No idempotency file found — starting fresh");
      return;
   }
   int loaded = 0;
   while(!FileIsEnding(handle))
   {
      string master_id = FileReadString(handle);
      if(FileIsEnding(handle)) break;  // guard against trailing newline
      int last_id = (int)FileReadNumber(handle);
      if(master_id != "")
      {
         RecordProcessedMessage(master_id, last_id);
         loaded++;
      }
   }
   FileClose(handle);
   g_logger.Info(StringFormat("[Slave] Loaded idempotency state: %d masters", loaded));
}

//+------------------------------------------------------------------+
//| SaveIdempotencyState — persist current idempotency table to file |
//+------------------------------------------------------------------+
void SaveIdempotencyState()
{
   string filename    = "copier_idem_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".csv";
   string tmpFilename = "copier_idem_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".tmp";

   int handle = FileOpen(tmpFilename, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      g_logger.Error("[Slave] Failed to open idempotency temp file for writing");
      return;
   }
   for(int i = 0; i < g_idempotencyCount; i++)
   {
      FileWrite(handle, g_idempotency[i].master_id, g_idempotency[i].last_msg_id);
   }
   FileClose(handle);

   FileDelete(filename);
   if(!FileMove(tmpFilename, 0, filename, 0))
      g_logger.Error("[Slave] Failed to rename idempotency temp file");
}

//+------------------------------------------------------------------+
//| Find pending order by magic number                               |
//+------------------------------------------------------------------+
ulong FindOrderByMagic(long magic)
{
   int total = OrdersTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if((long)OrderGetInteger(ORDER_MAGIC) == magic)
         return ticket;
   }
   return 0;
}

//+------------------------------------------------------------------+
//| Convert string to ENUM_ORDER_TYPE                                |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE StringToOrderType(string type)
{
   if(type == "BUY_LIMIT")  return ORDER_TYPE_BUY_LIMIT;
   if(type == "SELL_LIMIT") return ORDER_TYPE_SELL_LIMIT;
   if(type == "BUY_STOP")   return ORDER_TYPE_BUY_STOP;
   if(type == "SELL_STOP")  return ORDER_TYPE_SELL_STOP;
   return ORDER_TYPE_BUY;
}

//+------------------------------------------------------------------+
//| Execute PENDING_PLACE command                                    |
//+------------------------------------------------------------------+
void ExecutePendingPlace(SlaveCommandData &cmd)
{
   //--- Validate symbol
   if(!SymbolInfoInteger(cmd.symbol, SYMBOL_EXIST))
   {
      g_logger.Error(StringFormat("Symbol not found: %s", cmd.symbol));
      SendNack(cmd.msgId, "SYMBOL_NOT_FOUND");
      return;
   }

   //--- Ensure symbol is in MarketWatch
   SymbolSelect(cmd.symbol, true);

   //--- Check if trading is enabled
   if(!SymbolInfoInteger(cmd.symbol, SYMBOL_TRADE_MODE))
   {
      g_logger.Error(StringFormat("Trading disabled for %s", cmd.symbol));
      SendNack(cmd.msgId, "TRADE_DISABLED");
      return;
   }

   //--- Normalize volume
   double volumeStep = SymbolInfoDouble(cmd.symbol, SYMBOL_VOLUME_STEP);
   double volumeMin  = SymbolInfoDouble(cmd.symbol, SYMBOL_VOLUME_MIN);
   double volumeMax  = SymbolInfoDouble(cmd.symbol, SYMBOL_VOLUME_MAX);

   double normalizedVol = NormalizeVolume(cmd.volume, volumeStep);

   if(normalizedVol < volumeMin)
   {
      g_logger.Error(StringFormat("Volume %.4f < min %.4f for %s",
                                  normalizedVol, volumeMin, cmd.symbol));
      SendNack(cmd.msgId, "INVALID_VOLUME");
      return;
   }

   if(normalizedVol > volumeMax)
   {
      g_logger.Info(StringFormat("Volume %.4f capped to max %.4f for %s",
                                 normalizedVol, volumeMax, cmd.symbol));
      normalizedVol = volumeMax;
   }

   //--- Set magic for the trade
   g_trade.SetExpertMagicNumber(cmd.magic);

   //--- Determine order type
   ENUM_ORDER_TYPE orderType = StringToOrderType(cmd.orderType);

   //--- Comment
   string comment = cmd.comment;
   if(StringLen(comment) == 0)
      comment = StringFormat("Copy:%s:%d", cmd.masterId, cmd.masterTicket);

   //--- Execute pending order (limit_price=0.0 for non-STOP_LIMIT orders, price=cmd.price)
   bool result = g_trade.OrderOpen(cmd.symbol, orderType, normalizedVol,
                                    0.0, cmd.price, cmd.sl, cmd.tp,
                                    ORDER_TIME_GTC, 0, comment);

   if(result)
   {
      ulong orderTicket = g_trade.ResultOrder();
      g_logger.Info(StringFormat("PENDING_PLACE success: sym=%s type=%s vol=%.2f price=%.5f ticket=%d",
                                 cmd.symbol, cmd.orderType, normalizedVol, cmd.price, orderTicket));
      SendAck(cmd.msgId, (long)orderTicket);
   }
   else
   {
      uint retcode = g_trade.ResultRetcode();
      g_logger.Error(StringFormat("PENDING_PLACE failed: sym=%s type=%s retcode=%d comment=%s",
                                  cmd.symbol, cmd.orderType, retcode, g_trade.ResultComment()));
      SendNack(cmd.msgId, "ORDER_FAILED");
   }
}

//+------------------------------------------------------------------+
//| Execute PENDING_MODIFY command                                   |
//+------------------------------------------------------------------+
void ExecutePendingModify(SlaveCommandData &cmd)
{
   ulong ticket = FindOrderByMagic(cmd.magic);
   if(ticket == 0)
   {
      g_logger.Error(StringFormat("PENDING_MODIFY: no order with magic=%d", cmd.magic));
      SendNack(cmd.msgId, "ORDER_NOT_FOUND");
      return;
   }

   bool result = g_trade.OrderModify(ticket, cmd.price, cmd.sl, cmd.tp,
                                      ORDER_TIME_GTC, 0);

   if(result)
   {
      g_logger.Info(StringFormat("PENDING_MODIFY success: ticket=%d price=%.5f sl=%.5f tp=%.5f",
                                 ticket, cmd.price, cmd.sl, cmd.tp));
      SendAck(cmd.msgId, (long)ticket);
   }
   else
   {
      uint retcode = g_trade.ResultRetcode();
      g_logger.Error(StringFormat("PENDING_MODIFY failed: ticket=%d retcode=%d comment=%s",
                                  ticket, retcode, g_trade.ResultComment()));
      SendNack(cmd.msgId, "ORDER_FAILED");
   }
}

//+------------------------------------------------------------------+
//| Execute PENDING_DELETE command                                    |
//+------------------------------------------------------------------+
void ExecutePendingDelete(SlaveCommandData &cmd)
{
   ulong ticket = FindOrderByMagic(cmd.magic);
   if(ticket == 0)
   {
      //--- Order not found — maybe already activated (became a position)
      ulong posTicket = FindPositionByMagic(cmd.magic);
      if(posTicket != 0)
      {
         g_logger.Info(StringFormat("PENDING_DELETE: order already activated as position %d (magic=%d)",
                                    posTicket, cmd.magic));
         SendAck(cmd.msgId, (long)posTicket);
         return;
      }

      g_logger.Error(StringFormat("PENDING_DELETE: no order or position with magic=%d", cmd.magic));
      SendNack(cmd.msgId, "ORDER_NOT_FOUND");
      return;
   }

   bool result = g_trade.OrderDelete(ticket);

   if(result)
   {
      g_logger.Info(StringFormat("PENDING_DELETE success: ticket=%d magic=%d", ticket, cmd.magic));
      SendAck(cmd.msgId, (long)ticket);
   }
   else
   {
      uint retcode = g_trade.ResultRetcode();
      g_logger.Error(StringFormat("PENDING_DELETE failed: ticket=%d retcode=%d comment=%s",
                                  ticket, retcode, g_trade.ResultComment()));
      SendNack(cmd.msgId, "ORDER_FAILED");
   }
}
//+------------------------------------------------------------------+
