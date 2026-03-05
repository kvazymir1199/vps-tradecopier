import asyncio
import pytest
import win32pipe
import win32file
from hub.transport.pipe_server import PipeServer


PIPE_NAME = "test_copier_pipe"


async def _connect_client(pipe_name: str) -> int:
    """Connect to pipe as client, returns handle."""
    full_name = f"\\\\.\\pipe\\{pipe_name}"
    loop = asyncio.get_event_loop()
    handle = await loop.run_in_executor(
        None,
        lambda: win32file.CreateFile(
            full_name,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        ),
    )
    return handle


@pytest.mark.asyncio
async def test_pipe_server_receives_message():
    received = []

    async def handler(msg: str) -> str | None:
        received.append(msg)
        return None

    server = PipeServer(PIPE_NAME, handler)
    server_task = asyncio.create_task(server.start())

    await asyncio.sleep(0.2)

    handle = await _connect_client(PIPE_NAME)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, lambda: win32file.WriteFile(handle, b'{"test": "hello"}\n')
    )
    await asyncio.sleep(0.3)
    win32file.CloseHandle(handle)

    server.stop()
    await asyncio.sleep(0.5)
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass

    assert len(received) == 1
    assert '"test"' in received[0]


@pytest.mark.asyncio
async def test_pipe_server_sends_response():
    async def handler(msg: str) -> str | None:
        return '{"ack": true}\n'

    server = PipeServer(f"{PIPE_NAME}_resp", handler)
    server_task = asyncio.create_task(server.start())

    await asyncio.sleep(0.2)

    handle = await _connect_client(f"{PIPE_NAME}_resp")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, lambda: win32file.WriteFile(handle, b'{"cmd": "ping"}\n')
    )
    await asyncio.sleep(0.3)

    hr, data = await loop.run_in_executor(
        None, lambda: win32file.ReadFile(handle, 4096)
    )
    response = data.decode("utf-8")
    win32file.CloseHandle(handle)

    server.stop()
    await asyncio.sleep(0.5)
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass

    assert '"ack"' in response
