import asyncio
import logging
from collections.abc import Callable, Awaitable

import win32pipe
import win32file
import pywintypes

logger = logging.getLogger(__name__)

PIPE_BUFFER_SIZE = 4096


class PipeServer:
    """Async named pipe server. Creates a pipe, waits for client, reads newline-delimited messages."""

    def __init__(self, pipe_name: str, on_message: Callable[[str], Awaitable[str | None]]):
        self._pipe_name = f"\\\\.\\pipe\\{pipe_name}"
        self._on_message = on_message
        self._running = False
        self._handle = None

    async def start(self):
        self._running = True
        while self._running:
            try:
                await self._accept_and_serve()
            except Exception as e:
                logger.error(f"Pipe {self._pipe_name} error: {e}")
                if self._running:
                    await asyncio.sleep(1)

    async def _accept_and_serve(self):
        loop = asyncio.get_event_loop()
        self._handle = await loop.run_in_executor(None, self._create_and_connect)
        if not self._handle:
            return
        try:
            buffer = ""
            while self._running:
                data = await loop.run_in_executor(None, self._read)
                if data is None:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        response = await self._on_message(line)
                        if response:
                            await loop.run_in_executor(None, self._write, response)
        finally:
            win32file.CloseHandle(self._handle)
            self._handle = None

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

    def _read(self) -> str | None:
        try:
            hr, data = win32file.ReadFile(self._handle, PIPE_BUFFER_SIZE)
            return data.decode("utf-8")
        except pywintypes.error:
            return None

    def _write(self, data: str):
        try:
            win32file.WriteFile(self._handle, data.encode("utf-8"))
        except pywintypes.error:
            pass

    def stop(self):
        self._running = False
