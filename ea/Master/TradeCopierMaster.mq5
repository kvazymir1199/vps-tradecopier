//+------------------------------------------------------------------+
//| TradeCopierMaster.mq5                                            |
//| Master EA: scans positions, sends OPEN/MODIFY/CLOSE/CLOSE_PARTIAL|
//| messages to Python Hub via named pipe.                           |
//+------------------------------------------------------------------+
#property copyright "Tino-V"
#property version   "1.00"
#property strict

#include "..\Include\CopierLogger.mqh"
#include "..\Include\CopierPipe.mqh"
#include "..\Include\CopierProtocol.mqh"
#include "..\Include\CopierDatabase.mqh"

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input int    HeartbeatSec = 10;

//+------------------------------------------------------------------+
//| Magic number filter: set both to 0 to track ALL positions        |
//+------------------------------------------------------------------+
input long InpMagicMin = 0;   // Min magic (0 = no filter)
input long InpMagicMax = 0;   // Max magic (0 = no filter)

//+------------------------------------------------------------------+
//| Tracked position state                                           |
//+------------------------------------------------------------------+
struct TrackedPosition
{
   long   ticket;
   long   magic;
   string symbol;
   string direction;  // "BUY" or "SELL"
   double volume;
   double sl;
   double tp;
};

//+------------------------------------------------------------------+
//| Global variables                                                 |
//+------------------------------------------------------------------+
CCopierLogger  g_logger;
CCopierPipe    g_pipe;

TrackedPosition g_positions[];
int             g_posCount;

int             g_msgId;
datetime        g_lastHeartbeat;

string          GV_MSG_ID_KEY;   // GlobalVariable name for msg_id persistence

// Auto-generated from account number
string g_terminalId;
string g_pipeName;
string g_dbFile = "TradeCopier\\copier.db";
string g_vpsId  = "vps_1";

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Auto-generate terminal ID and pipe name from account number
   long account = AccountInfoInteger(ACCOUNT_LOGIN);
   g_terminalId = "master_" + IntegerToString(account);
   g_pipeName   = "copier_master_" + IntegerToString(account);

   g_logger.Init("Master_" + g_terminalId);
   g_logger.Info("=== TradeCopierMaster initializing ===");
   g_logger.Info(StringFormat("TerminalID=%s  Pipe=%s  HB=%ds",
                              g_terminalId, g_pipeName, HeartbeatSec));

   //--- Restore msg_id from GlobalVariable for persistence
   GV_MSG_ID_KEY = "CopierMaster_MsgId_" + g_terminalId;
   if(GlobalVariableCheck(GV_MSG_ID_KEY))
      g_msgId = (int)GlobalVariableGet(GV_MSG_ID_KEY);
   else
      g_msgId = 0;

   g_logger.Info(StringFormat("Restored msg_id=%d", g_msgId));

   //--- Initialize tracked positions array
   g_posCount = 0;
   ArrayResize(g_positions, 0);

   //--- Register in shared SQLite DB so Hub discovers us
   if(!RegisterTerminalInDB(g_terminalId, "master", g_dbFile))
      g_logger.Error("DB registration failed — Hub won't auto-create pipe");

   //--- Connect pipe (silent — Hub may not have created it yet)
   if(!g_pipe.Connect(g_pipeName, true))
   {
      g_logger.Info("Waiting for Hub to create pipe...");
   }
   else
   {
      //--- Send REGISTER
      g_msgId++;
      string regMsg = BuildRegisterMessage(g_terminalId, "MASTER",
                                           AccountInfoInteger(ACCOUNT_LOGIN),
                                           AccountInfoString(ACCOUNT_COMPANY));
      if(g_pipe.Send(regMsg))
         g_logger.Info("REGISTER sent");
      else
         g_logger.Error("Failed to send REGISTER");

      PersistMsgId();
   }

   //--- Do initial scan so we have baseline
   ScanPositions();

   //--- Start 100ms timer
   g_lastHeartbeat = TimeLocal();
   EventSetMillisecondTimer(100);

   g_logger.Info(StringFormat("Init complete. Tracking %d positions", g_posCount));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   g_pipe.Disconnect();
   g_logger.Info(StringFormat("Shutdown (reason=%d)", reason));
}

//+------------------------------------------------------------------+
//| OnTrade — triggered on any trade event                           |
//+------------------------------------------------------------------+
void OnTrade()
{
   ScanPositions();
}

//+------------------------------------------------------------------+
//| OnTimer — poll pipe + heartbeat                                  |
//+------------------------------------------------------------------+
void OnTimer()
{
   //--- Ensure pipe is connected
   if(!g_pipe.IsConnected())
   {
      if(!g_pipe.Connect(g_pipeName, true))
         return;

      //--- Re-register after reconnect
      g_msgId++;
      string regMsg = BuildRegisterMessage(g_terminalId, "MASTER",
                                           AccountInfoInteger(ACCOUNT_LOGIN),
                                           AccountInfoString(ACCOUNT_COMPANY));
      g_pipe.Send(regMsg);
      PersistMsgId();
      g_logger.Info("Re-registered after reconnect");
   }

   //--- Poll pipe for any responses (discard; master is fire-and-forget)
   string recv = g_pipe.Receive();
   while(StringLen(recv) > 0)
   {
      g_logger.Debug(StringFormat("Received: %s", recv));
      recv = g_pipe.Receive();
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
      if(g_pipe.Send(hbMsg))
         g_logger.Debug("Heartbeat sent");
      else
         g_logger.Error("Heartbeat send failed");

      g_lastHeartbeat = TimeLocal();
   }
}

//+------------------------------------------------------------------+
//| ScanPositions — compare current vs tracked, emit messages        |
//+------------------------------------------------------------------+
void ScanPositions()
{
   //--- Build snapshot of current positions matching magic pattern
   int totalPositions = PositionsTotal();
   TrackedPosition current[];
   int curCount = 0;
   ArrayResize(current, totalPositions);

   for(int i = 0; i < totalPositions; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      long magic = (long)PositionGetInteger(POSITION_MAGIC);
      if(InpMagicMin != 0 || InpMagicMax != 0)
      {
         if(magic < InpMagicMin || magic >= InpMagicMax)
            continue;
      }

      TrackedPosition pos;
      pos.ticket    = (long)ticket;
      pos.magic     = magic;
      pos.symbol    = PositionGetString(POSITION_SYMBOL);
      pos.direction = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL";
      pos.volume    = PositionGetDouble(POSITION_VOLUME);
      pos.sl        = PositionGetDouble(POSITION_SL);
      pos.tp        = PositionGetDouble(POSITION_TP);

      current[curCount] = pos;
      curCount++;
   }
   ArrayResize(current, curCount);

   //--- Detect NEW positions (in current but not in tracked)
   for(int c = 0; c < curCount; c++)
   {
      int idx = FindTrackedByTicket(current[c].ticket);
      if(idx < 0)
      {
         //--- New position
         g_msgId++;
         string msg = BuildOpenMessage(g_msgId, g_terminalId,
                                       current[c].ticket,
                                       current[c].symbol,
                                       current[c].direction,
                                       current[c].volume,
                                       0.0,  // price not needed for copy signal
                                       current[c].sl,
                                       current[c].tp,
                                       current[c].magic,
                                       "");
         if(g_pipe.Send(msg))
            g_logger.Info(StringFormat("OPEN sent: ticket=%d magic=%d sym=%s dir=%s vol=%.2f",
                                       current[c].ticket, current[c].magic,
                                       current[c].symbol, current[c].direction,
                                       current[c].volume));
         else
            g_logger.Error(StringFormat("OPEN send failed: ticket=%d", current[c].ticket));

         PersistMsgId();
      }
      else
      {
         //--- Existing position — check for modifications
         TrackedPosition prev = g_positions[idx];

         //--- Check SL/TP change
         if(CompareDouble(prev.sl, current[c].sl) == false ||
            CompareDouble(prev.tp, current[c].tp) == false)
         {
            g_msgId++;
            string msg = BuildModifyMessage(g_msgId, g_terminalId,
                                            current[c].ticket,
                                            current[c].magic,
                                            current[c].sl,
                                            current[c].tp);
            if(g_pipe.Send(msg))
               g_logger.Info(StringFormat("MODIFY sent: ticket=%d sl=%.5f tp=%.5f",
                                          current[c].ticket, current[c].sl, current[c].tp));
            else
               g_logger.Error(StringFormat("MODIFY send failed: ticket=%d", current[c].ticket));

            PersistMsgId();
         }

         //--- Check volume decrease (partial close)
         if(current[c].volume < prev.volume - 0.000001)
         {
            double closedVolume = prev.volume - current[c].volume;
            g_msgId++;
            string msg = BuildClosePartialMessage(g_msgId, g_terminalId,
                                                  current[c].ticket,
                                                  current[c].magic,
                                                  closedVolume);
            if(g_pipe.Send(msg))
               g_logger.Info(StringFormat("CLOSE_PARTIAL sent: ticket=%d closed_vol=%.2f remaining=%.2f",
                                          current[c].ticket, closedVolume, current[c].volume));
            else
               g_logger.Error(StringFormat("CLOSE_PARTIAL send failed: ticket=%d", current[c].ticket));

            PersistMsgId();
         }
      }
   }

   //--- Detect CLOSED positions (in tracked but not in current)
   for(int t = 0; t < g_posCount; t++)
   {
      bool found = false;
      for(int c = 0; c < curCount; c++)
      {
         if(g_positions[t].ticket == current[c].ticket)
         {
            found = true;
            break;
         }
      }

      if(!found)
      {
         g_msgId++;
         string msg = BuildCloseMessage(g_msgId, g_terminalId,
                                        g_positions[t].ticket,
                                        g_positions[t].magic);
         if(g_pipe.Send(msg))
            g_logger.Info(StringFormat("CLOSE sent: ticket=%d magic=%d",
                                       g_positions[t].ticket, g_positions[t].magic));
         else
            g_logger.Error(StringFormat("CLOSE send failed: ticket=%d", g_positions[t].ticket));

         PersistMsgId();
      }
   }

   //--- Update tracked array with current snapshot
   g_posCount = curCount;
   ArrayResize(g_positions, curCount);
   for(int i = 0; i < curCount; i++)
      g_positions[i] = current[i];
}

//+------------------------------------------------------------------+
//| Find a tracked position by ticket                                |
//+------------------------------------------------------------------+
int FindTrackedByTicket(long ticket)
{
   for(int i = 0; i < g_posCount; i++)
   {
      if(g_positions[i].ticket == ticket)
         return i;
   }
   return -1;
}

//+------------------------------------------------------------------+
//| Compare two doubles with tolerance                               |
//+------------------------------------------------------------------+
bool CompareDouble(double a, double b)
{
   return MathAbs(a - b) < 0.000001;
}

//+------------------------------------------------------------------+
//| Persist msg_id to GlobalVariable                                 |
//+------------------------------------------------------------------+
void PersistMsgId()
{
   GlobalVariableSet(GV_MSG_ID_KEY, (double)g_msgId);
}
//+------------------------------------------------------------------+
