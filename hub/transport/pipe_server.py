import asyncio
import logging
import time
from collections.abc import Callable, Awaitable

import win32pipe
import win32file
import win32security
import pywintypes

logger = logging.getLogger(__name__)

PIPE_BUFFER_SIZE = 4096
PIPE_POLL_INTERVAL_SEC = 0.05  # 50 ms — balance between latency and CPU


class PipeServer:
    """Async named pipe server.

    Creates a pipe and waits for clients.  After accepting a connection the
    server immediately creates a **new** pipe instance so the next client can
    connect without waiting — this is the standard Windows named-pipe server
    pattern and prevents ERROR_PIPE_BUSY (231) on reconnect.
    """

    def __init__(self, pipe_name: str, on_message: Callable[[str], Awaitable[str | None]], write_only: bool = False):
        self._pipe_name = f"\\\\.\\pipe\\{pipe_name}"
        self._on_message = on_message
        self._write_only = write_only
        self._running = False
        self._handle = None  # latest active client handle (used for external writes)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self):
        self._running = True
        while self._running:
            try:
                loop = asyncio.get_event_loop()
                handle = await loop.run_in_executor(None, self._create_and_connect)
                if not handle or not self._running:
                    # Dummy connect from stop() or shutdown — close and exit
                    if handle:
                        try:
                            win32file.CloseHandle(handle)
                        except Exception:
                            pass
                    continue

                # Store as active handle (hub uses _handle / _write for slave cmd pipes)
                self._handle = handle
                logger.info(f"Pipe {self._pipe_name} client connected")

                # Write-only pipes (e.g. slave cmd) don't need a read loop —
                # skip _serve_client to avoid wasting a thread pool slot.
                if not self._write_only:
                    asyncio.create_task(self._serve_client(handle))

            except Exception as e:
                logger.error(f"Pipe {self._pipe_name} error: {e}")
                if self._running:
                    await asyncio.sleep(1)

    def stop(self):
        self._running = False
        # Unblock any pending ConnectNamedPipe by connecting a dummy client
        try:
            h = win32file.CreateFile(
                self._pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING, 0, None,
            )
            win32file.CloseHandle(h)
        except pywintypes.error:
            pass

    # Keep _write for backward compat — hub calls pipe._write(encoded)
    def _write(self, data: str):
        handle = self._handle
        if handle:
            self._write_to(handle, data)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _serve_client(self, handle):
        buffer = ""
        loop = asyncio.get_event_loop()
        try:
            while self._running:
                data = await loop.run_in_executor(None, self._read_from, handle)
                if data is None:
                    break  # pipe broken — exit the serve loop
                if data == "":
                    # No data yet — pipe healthy. Yield control so other tasks run.
                    await asyncio.sleep(PIPE_POLL_INTERVAL_SEC)
                    continue
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    stripped = line.strip()
                    if not stripped:
                        continue
                    # Fire-and-forget for HEARTBEAT — it writes symbols to the DB,
                    # and we must not let that block trade-message routing on the
                    # same pipe. Trade messages (OPEN/CLOSE/MODIFY) and REGISTER
                    # stay synchronous so their response order is preserved.
                    if '"type":"HEARTBEAT"' in stripped[:60]:
                        asyncio.create_task(self._on_message(stripped))
                        continue
                    response = await self._on_message(stripped)
                    if response:
                        await loop.run_in_executor(None, self._write_to, handle, response)
        except Exception as e:
            logger.error(f"Pipe {self._pipe_name} client error: {e}")
        finally:
            try:
                win32file.CloseHandle(handle)
            except Exception:
                pass
            # Clear _handle only if it still points to this client
            if self._handle == handle:
                self._handle = None
            logger.info(f"Pipe {self._pipe_name} client disconnected")

    @staticmethod
    def _make_security_attributes():
        """Return a SECURITY_ATTRIBUTES with a NULL DACL (grants Everyone full access).

        Needed because the Hub runs as Administrator (UAC-elevated via start.bat),
        while MT5 EAs run as a normal user.  Without explicit permissions the OS
        would deny GENERIC_WRITE access to non-admin clients.
        """
        sd = win32security.SECURITY_DESCRIPTOR()
        # NULL DACL = grant all access to everyone
        sd.SetSecurityDescriptorDacl(True, None, False)
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.SECURITY_DESCRIPTOR = sd
        return sa

    def _create_and_connect(self):
        sa = self._make_security_attributes()
        handle = win32pipe.CreateNamedPipe(
            self._pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
            win32pipe.PIPE_UNLIMITED_INSTANCES,
            PIPE_BUFFER_SIZE,
            PIPE_BUFFER_SIZE,
            0,
            sa,
        )
        win32pipe.ConnectNamedPipe(handle, None)
        return handle

    @staticmethod
    def _read_from(handle) -> str | None:
        """Non-blocking read with PeekNamedPipe.

        Returns:
            str with data — data was read successfully
            ""             — pipe is healthy but nothing to read yet (caller sleeps)
            None           — pipe is broken/closed (caller exits the serve loop)

        This avoids ReadFile() blocking the executor thread forever on a
        half-closed pipe handle. Such stuck threads previously froze the
        entire event loop when multiple clients reconnected rapidly.
        """
        try:
            # Peek first to check pipe state and available bytes — this call
            # returns immediately and raises on a broken pipe.
            _, bytes_avail, _ = win32pipe.PeekNamedPipe(handle, 0)
        except pywintypes.error:
            return None  # pipe broken

        if bytes_avail == 0:
            return ""  # healthy but empty

        try:
            _, data = win32file.ReadFile(handle, PIPE_BUFFER_SIZE)
            return data.decode("utf-8")
        except pywintypes.error:
            return None

    @staticmethod
    def _write_to(handle, data: str):
        try:
            win32file.WriteFile(handle, data.encode("utf-8"))
        except pywintypes.error:
            pass
