//+------------------------------------------------------------------+
//| CopierPipe.mqh — Named pipe client for MT5 Trade Copier         |
//| Connects to Python Hub via Windows named pipes                   |
//+------------------------------------------------------------------+
#ifndef COPIER_PIPE_MQH
#define COPIER_PIPE_MQH

#import "kernel32.dll"
   long   CreateFileW(string lpFileName, uint dwDesiredAccess,
                      uint dwShareMode, long lpSecurityAttributes,
                      uint dwCreationDisposition, uint dwFlagsAndAttributes,
                      long hTemplateFile);
   int    WriteFile(long hFile, uchar &lpBuffer[], uint nNumberOfBytesToWrite,
                    uint &lpNumberOfBytesWritten, long lpOverlapped);
   int    ReadFile(long hFile, uchar &lpBuffer[], uint nNumberOfBytesToRead,
                   uint &lpNumberOfBytesRead, long lpOverlapped);
   int    PeekNamedPipe(long hNamedPipe, uchar &lpBuffer[], uint nBufferSize,
                        uint &lpBytesRead, uint &lpTotalBytesAvail,
                        uint &lpBytesLeftThisMessage);
   int    CloseHandle(long hObject);
   uint   GetLastError();
   int    WaitNamedPipeW(string lpNamedPipeName, uint nTimeOut);
#import

//--- Constants
#define COPIER_PIPE_INVALID_HANDLE   -1
#define COPIER_PIPE_GENERIC_RW       0xC0000000  // GENERIC_READ | GENERIC_WRITE
#define COPIER_PIPE_OPEN_EXISTING    3
#define COPIER_PIPE_BUFFER_SIZE      8192
#define COPIER_PIPE_WAIT_TIMEOUT     2000  // ms to wait if pipe is busy

//+------------------------------------------------------------------+
//| CCopierPipe — named pipe client class                            |
//+------------------------------------------------------------------+
class CCopierPipe
{
private:
   long     m_handle;
   string   m_pipeName;
   string   m_recvBuffer;   // accumulates partial reads

public:
            CCopierPipe();
           ~CCopierPipe();

   bool     Connect(string pipeName);
   void     Disconnect();
   bool     IsConnected();
   bool     Send(string message);
   string   Receive();
   bool     Reconnect(string pipeName);

private:
   string   BuildPipePath(string pipeName);
};

//+------------------------------------------------------------------+
CCopierPipe::CCopierPipe()
   : m_handle(COPIER_PIPE_INVALID_HANDLE),
     m_pipeName(""),
     m_recvBuffer("")
{
}

//+------------------------------------------------------------------+
CCopierPipe::~CCopierPipe()
{
   Disconnect();
}

//+------------------------------------------------------------------+
string CCopierPipe::BuildPipePath(string pipeName)
{
   return "\\\\.\\pipe\\" + pipeName;
}

//+------------------------------------------------------------------+
bool CCopierPipe::Connect(string pipeName)
{
   if(m_handle != COPIER_PIPE_INVALID_HANDLE)
   {
      PrintFormat("[CopierPipe] Already connected to %s, disconnecting first", m_pipeName);
      Disconnect();
   }

   m_pipeName = pipeName;
   string fullPath = BuildPipePath(pipeName);

   m_handle = CreateFileW(fullPath,
                          COPIER_PIPE_GENERIC_RW,  // GENERIC_READ | GENERIC_WRITE
                          0,                        // no sharing
                          0,                        // default security
                          COPIER_PIPE_OPEN_EXISTING,// open existing pipe
                          0,                        // default attributes
                          0);                       // no template

   if(m_handle == COPIER_PIPE_INVALID_HANDLE)
   {
      uint err = kernel32::GetLastError();

      // ERROR_PIPE_BUSY (231) — pipe exists but all instances are busy
      if(err == 231)
      {
         if(WaitNamedPipeW(fullPath, COPIER_PIPE_WAIT_TIMEOUT) != 0)
         {
            // Pipe became available, retry CreateFileW
            m_handle = CreateFileW(fullPath,
                                   COPIER_PIPE_GENERIC_RW,
                                   0, 0,
                                   COPIER_PIPE_OPEN_EXISTING,
                                   0, 0);
         }
      }

      if(m_handle == COPIER_PIPE_INVALID_HANDLE)
      {
         PrintFormat("[CopierPipe] Connect failed to %s — Win32 error %u", fullPath, err);
         return false;
      }
   }

   m_recvBuffer = "";
   PrintFormat("[CopierPipe] Connected to %s (handle=%d)", fullPath, m_handle);
   return true;
}

//+------------------------------------------------------------------+
void CCopierPipe::Disconnect()
{
   if(m_handle != COPIER_PIPE_INVALID_HANDLE)
   {
      CloseHandle(m_handle);
      PrintFormat("[CopierPipe] Disconnected from %s", m_pipeName);
      m_handle = COPIER_PIPE_INVALID_HANDLE;
   }
   m_recvBuffer = "";
}

//+------------------------------------------------------------------+
bool CCopierPipe::IsConnected()
{
   return (m_handle != COPIER_PIPE_INVALID_HANDLE);
}

//+------------------------------------------------------------------+
bool CCopierPipe::Send(string message)
{
   if(m_handle == COPIER_PIPE_INVALID_HANDLE)
   {
      Print("[CopierPipe] Send failed — not connected");
      return false;
   }

   // Ensure message ends with newline delimiter
   if(StringLen(message) == 0)
      return true;

   if(StringGetCharacter(message, StringLen(message) - 1) != '\n')
      message += "\n";

   // Convert to UTF-8 byte array
   uchar sendBuf[];
   int bytes = StringToCharArray(message, sendBuf, 0, WHOLE_ARRAY, CP_UTF8);
   if(bytes <= 0)
   {
      Print("[CopierPipe] Send failed — string conversion error");
      return false;
   }

   // StringToCharArray appends a null terminator; send without it
   int sendLen = bytes - 1;
   if(sendLen <= 0)
      return true;

   uchar trimBuf[];
   ArrayResize(trimBuf, sendLen);
   ArrayCopy(trimBuf, sendBuf, 0, 0, sendLen);

   uint bytesWritten = 0;
   int result = WriteFile(m_handle, trimBuf, (uint)sendLen, bytesWritten, 0);

   if(result == 0)
   {
      uint err = kernel32::GetLastError();
      PrintFormat("[CopierPipe] WriteFile failed — Win32 error %u", err);
      Disconnect();
      return false;
   }

   if(bytesWritten != (uint)sendLen)
   {
      PrintFormat("[CopierPipe] WriteFile partial write: %u of %d bytes", bytesWritten, sendLen);
   }

   return true;
}

//+------------------------------------------------------------------+
string CCopierPipe::Receive()
{
   if(m_handle == COPIER_PIPE_INVALID_HANDLE)
      return "";

   // Check if data is available without blocking
   uchar peekBuf[];
   ArrayResize(peekBuf, 1);
   uint bytesRead     = 0;
   uint totalAvail    = 0;
   uint bytesLeft     = 0;

   int peekResult = PeekNamedPipe(m_handle, peekBuf, 0, bytesRead, totalAvail, bytesLeft);

   if(peekResult == 0)
   {
      uint err = kernel32::GetLastError();
      PrintFormat("[CopierPipe] PeekNamedPipe failed — Win32 error %u", err);
      Disconnect();
      return "";
   }

   // Read all available data
   if(totalAvail > 0)
   {
      uint readSize = MathMin(totalAvail, COPIER_PIPE_BUFFER_SIZE);
      uchar readBuf[];
      ArrayResize(readBuf, (int)readSize);

      uint actualRead = 0;
      int readResult = ReadFile(m_handle, readBuf, readSize, actualRead, 0);

      if(readResult == 0)
      {
         uint err = kernel32::GetLastError();
         PrintFormat("[CopierPipe] ReadFile failed — Win32 error %u", err);
         Disconnect();
         return "";
      }

      if(actualRead > 0)
      {
         string chunk = CharArrayToString(readBuf, 0, (int)actualRead, CP_UTF8);
         m_recvBuffer += chunk;
      }
   }

   // Extract first complete line from buffer
   int nlPos = StringFind(m_recvBuffer, "\n");
   if(nlPos < 0)
      return "";

   string line = StringSubstr(m_recvBuffer, 0, nlPos);
   m_recvBuffer = StringSubstr(m_recvBuffer, nlPos + 1);

   // Trim trailing \r if present (CR+LF)
   int lineLen = StringLen(line);
   if(lineLen > 0 && StringGetCharacter(line, lineLen - 1) == '\r')
      line = StringSubstr(line, 0, lineLen - 1);

   return line;
}

//+------------------------------------------------------------------+
bool CCopierPipe::Reconnect(string pipeName)
{
   Disconnect();
   return Connect(pipeName);
}

#endif // COPIER_PIPE_MQH
