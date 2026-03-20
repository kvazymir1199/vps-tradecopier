//+------------------------------------------------------------------+
//|                                               CopierDatabase.mqh |
//|                                                           Tino-V |
//+------------------------------------------------------------------+
#property copyright "Tino-V"
#property strict

//+------------------------------------------------------------------+
//| Summary: Self-registration of EA in shared SQLite DB             |
//|          so Hub can discover terminals and create pipes.         |
//|          DB is in Common\Files\TradeCopier\copier.db             |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| RegisterTerminalInDB                                             |
//| Inserts terminal record into shared SQLite. Idempotent.          |
//+------------------------------------------------------------------+
bool RegisterTerminalInDB(string terminal_id, string role, string db_file)
{
   // Create folder in Common Files if it doesn't exist
   FolderCreate("TradeCopier", FILE_COMMON);

   // Open or create DB in Common Files
   int db = DatabaseOpen(db_file,
      DATABASE_OPEN_READWRITE | DATABASE_OPEN_CREATE | DATABASE_OPEN_COMMON);

   if(db == INVALID_HANDLE)
   {
      Print("[CopierDatabase] DB open failed: ", GetLastError());
      return false;
   }

   // WAL mode + busy timeout for concurrent access with Hub
   DatabaseExecute(db, "PRAGMA journal_mode=WAL");
   DatabaseExecute(db, "PRAGMA busy_timeout=5000");

   // Create terminals table if Hub hasn't started yet
   DatabaseExecute(db,
      "CREATE TABLE IF NOT EXISTS terminals ("
      "terminal_id TEXT PRIMARY KEY,"
      "role TEXT NOT NULL,"
      "account_number INTEGER,"
      "broker_server TEXT,"
      "status TEXT NOT NULL DEFAULT 'Starting',"
      "status_message TEXT DEFAULT '',"
      "created_at INTEGER NOT NULL,"
      "last_heartbeat INTEGER NOT NULL)");

   // INSERT OR IGNORE — idempotent, won't overwrite existing record
   long now_ms = (long)TimeGMT() * 1000;
   string sql = StringFormat(
      "INSERT OR IGNORE INTO terminals "
      "(terminal_id, role, status, status_message, created_at, last_heartbeat) "
      "VALUES ('%s', '%s', 'Starting', '', %lld, %lld)",
      terminal_id, role, now_ms, now_ms);

   bool ok = DatabaseExecute(db, sql);
   if(!ok)
      Print("[CopierDatabase] INSERT failed: ", GetLastError());

   DatabaseClose(db);

   if(ok)
      Print("[CopierDatabase] Registered '", terminal_id, "' (", role, ") in DB");

   return ok;
}
