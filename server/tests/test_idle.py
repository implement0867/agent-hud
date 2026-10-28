import asyncio
from pathlib import Path

import pytest

from agent_hud.exchange import Exchange
from agent_hud.store import StoreFactory
from tests.conversation import open_page, serve
from tests.factories import BOARD

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def ask_health(host: str, port: int) -> bytes:
    """The app's answer to GET /health, as a raw HTTP exchange."""
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"GET /health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    answer = await reader.read()
    writer.close()
    await writer.wait_closed()
    return answer


async def test_the_app_stops_once_idle_and_not_while_a_page_is_connected(
    static_dir: Path, tmp_path: Path, stores: StoreFactory, exchange: Exchange
) -> None:
    """Assemble: the app on a board, with an idle time of half a second, and a page connected to it.
    Act: wait a second with the page connected; then close the page and wait again.
    Assert: the app does not stop while the page is connected, and stops within three seconds of its going."""
    stopped = asyncio.Event()
    async with serve(stores, {BOARD: exchange}, static_dir, tmp_path, idle_seconds=0.5, on_idle=stopped.set) as address:
        async with open_page(address):
            await asyncio.sleep(1.2)
            assert not stopped.is_set()
        async with asyncio.timeout(3):
            await stopped.wait()


async def test_a_request_starts_the_idle_time_again(static_dir: Path, tmp_path: Path, stores: StoreFactory) -> None:
    """Assemble: the app with an idle time of one second, and nothing connected.
    Act: ask /health every 0.4 s for 1.6 s; then stop asking.
    Assert: the app has not stopped while the requests came, and stops within three seconds after the last."""
    stopped = asyncio.Event()
    async with serve(stores, {}, static_dir, tmp_path, idle_seconds=1, on_idle=stopped.set) as (host, port):
        for _ in range(4):
            await asyncio.sleep(0.4)
            assert (await ask_health(host, port)).startswith(b"HTTP/1.1 200")
        assert not stopped.is_set()
        async with asyncio.timeout(3):
            await stopped.wait()


async def test_an_idle_time_of_zero_keeps_the_app_running(
    static_dir: Path, tmp_path: Path, stores: StoreFactory
) -> None:
    """Assemble: the app with an idle time of 0, and nothing connected.
    Act: wait a second.
    Assert: the app has not stopped."""
    stopped = asyncio.Event()
    async with serve(stores, {}, static_dir, tmp_path, idle_seconds=0, on_idle=stopped.set):
        await asyncio.sleep(1)
        assert not stopped.is_set()
