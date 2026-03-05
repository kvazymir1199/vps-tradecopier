//+------------------------------------------------------------------+
//| CopierLogger.mqh — Daily rotating file logger for Trade Copier  |
//| Writes to MQL5/Files/CopierLogs/{prefix}_YYYYMMDD.log           |
//+------------------------------------------------------------------+
#ifndef COPIER_LOGGER_MQH
#define COPIER_LOGGER_MQH

//+------------------------------------------------------------------+
//| Log level enum                                                   |
//+------------------------------------------------------------------+
enum ENUM_COPIER_LOG_LEVEL
{
   LOG_LEVEL_DEBUG = 0,
   LOG_LEVEL_INFO  = 1,
   LOG_LEVEL_ERROR = 2
};

//+------------------------------------------------------------------+
//| CCopierLogger — daily rotating file logger                       |
//+------------------------------------------------------------------+
class CCopierLogger
{
private:
   string               m_prefix;
   bool                 m_initialized;
   ENUM_COPIER_LOG_LEVEL m_minLevel;

   // Current file state
   int                  m_fileHandle;
   string               m_currentDate;  // "YYYYMMDD" of the open file

   void     WriteEntry(string level, string msg);
   string   GetDateStr();
   string   GetTimeStr();
   bool     EnsureFileOpen();
   void     CloseFile();
   string   BuildFilePath(string dateStr);

public:
            CCopierLogger();
           ~CCopierLogger();

   void     Init(string prefix, ENUM_COPIER_LOG_LEVEL minLevel = LOG_LEVEL_DEBUG);
   void     Info(string msg);
   void     Error(string msg);
   void     Debug(string msg);
   void     SetMinLevel(ENUM_COPIER_LOG_LEVEL level);
};

//+------------------------------------------------------------------+
CCopierLogger::CCopierLogger()
   : m_prefix(""),
     m_initialized(false),
     m_minLevel(LOG_LEVEL_DEBUG),
     m_fileHandle(INVALID_HANDLE),
     m_currentDate("")
{
}

//+------------------------------------------------------------------+
CCopierLogger::~CCopierLogger()
{
   CloseFile();
}

//+------------------------------------------------------------------+
void CCopierLogger::Init(string prefix, ENUM_COPIER_LOG_LEVEL minLevel)
{
   m_prefix      = prefix;
   m_minLevel    = minLevel;
   m_initialized = true;

   // Create the CopierLogs directory by opening and immediately closing
   // a temp file. MQL5 FileOpen auto-creates subdirectories.
   string testPath = "CopierLogs\\_init.tmp";
   int testHandle = FileOpen(testPath, FILE_WRITE | FILE_TXT);
   if(testHandle != INVALID_HANDLE)
   {
      FileClose(testHandle);
      FileDelete(testPath);
   }
}

//+------------------------------------------------------------------+
void CCopierLogger::SetMinLevel(ENUM_COPIER_LOG_LEVEL level)
{
   m_minLevel = level;
}

//+------------------------------------------------------------------+
void CCopierLogger::Info(string msg)
{
   if(m_minLevel <= LOG_LEVEL_INFO)
      WriteEntry("INFO", msg);
}

//+------------------------------------------------------------------+
void CCopierLogger::Error(string msg)
{
   if(m_minLevel <= LOG_LEVEL_ERROR)
      WriteEntry("ERROR", msg);

   // Also print errors to the Experts tab for visibility
   PrintFormat("[%s] [ERROR] %s", m_prefix, msg);
}

//+------------------------------------------------------------------+
void CCopierLogger::Debug(string msg)
{
   if(m_minLevel <= LOG_LEVEL_DEBUG)
      WriteEntry("DEBUG", msg);
}

//+------------------------------------------------------------------+
void CCopierLogger::WriteEntry(string level, string msg)
{
   if(!m_initialized)
   {
      PrintFormat("[CopierLogger] Not initialized — dropping: [%s] %s", level, msg);
      return;
   }

   if(!EnsureFileOpen())
   {
      PrintFormat("[CopierLogger] Cannot open log file — [%s] %s", level, msg);
      return;
   }

   string line = "[" + GetTimeStr() + "] [" + level + "] " + msg;
   FileWriteString(m_fileHandle, line + "\n");
   FileFlush(m_fileHandle);
}

//+------------------------------------------------------------------+
bool CCopierLogger::EnsureFileOpen()
{
   string today = GetDateStr();

   // If the date rolled over, close the old file
   if(m_fileHandle != INVALID_HANDLE && m_currentDate != today)
   {
      CloseFile();
   }

   // Open file if not already open
   if(m_fileHandle == INVALID_HANDLE)
   {
      string filePath = BuildFilePath(today);

      m_fileHandle = FileOpen(filePath,
                              FILE_WRITE | FILE_TXT | FILE_SHARE_READ | FILE_UNICODE,
                              '\t',               // delimiter (unused for TXT)
                              CP_UTF8);

      if(m_fileHandle == INVALID_HANDLE)
      {
         PrintFormat("[CopierLogger] FileOpen failed for %s — error %d",
                     filePath, GetLastError());
         return false;
      }

      // Seek to end so we append to existing file
      FileSeek(m_fileHandle, 0, SEEK_END);
      m_currentDate = today;
   }

   return true;
}

//+------------------------------------------------------------------+
void CCopierLogger::CloseFile()
{
   if(m_fileHandle != INVALID_HANDLE)
   {
      FileClose(m_fileHandle);
      m_fileHandle = INVALID_HANDLE;
   }
   m_currentDate = "";
}

//+------------------------------------------------------------------+
string CCopierLogger::BuildFilePath(string dateStr)
{
   // Files go under MQL5/Files/CopierLogs/
   return "CopierLogs\\" + m_prefix + "_" + dateStr + ".log";
}

//+------------------------------------------------------------------+
string CCopierLogger::GetDateStr()
{
   MqlDateTime dt;
   TimeToStruct(TimeLocal(), dt);

   return StringFormat("%04d%02d%02d", dt.year, dt.mon, dt.day);
}

//+------------------------------------------------------------------+
string CCopierLogger::GetTimeStr()
{
   MqlDateTime dt;
   TimeToStruct(TimeLocal(), dt);

   return StringFormat("%02d:%02d:%02d", dt.hour, dt.min, dt.sec);
}

#endif // COPIER_LOGGER_MQH
