import asyncio
import logging
from collections.abc import Callable, Awaitable

import win32pipe
import win32file
import pywintypes

logger = logging.getLogger(__name__)

PIPE_BUFFER_SIZE = 4096


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
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        response = await self._on_message(line)
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

    def _create_and_connect(self):
        handle = win32pipe.CreateNamedPipe(
            self._pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
            win32pipe.PIPE_UNLIMITED_INSTANCES,
            PIPE_BUFFER_SIZE,
            PIPE_BUFFER_SIZE,
            0,
            None,
        )
        win32pipe.ConnectNamedPipe(handle, None)
        return handle

    @staticmethod
    def _read_from(handle) -> str | None:
        try:
            hr, data = win32file.ReadFile(handle, PIPE_BUFFER_SIZE)
            return data.decode("utf-8")
        except pywintypes.error:
            return None

    @staticmethod
    def _write_to(handle, data: str):
        try:
            win32file.WriteFile(handle, data.encode("utf-8"))
        except pywintypes.error:
            pass
