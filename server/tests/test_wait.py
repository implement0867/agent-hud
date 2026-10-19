import asyncio

from agent_hud.board import Board
from tests.conftest import Act


async def _noop(_: float) -> None:
    return None


async def test_wait_returns_when_the_user_submits(board: Board, act: Act) -> None:
    waiter = asyncio.create_task(board.wait_for_submit(5, _noop, interval=0.01))
    await asyncio.sleep(0.03)
    assert board.status().waiting, "the page is told the agent is waiting"
    act(t="submit", message=None)
    assert await waiter is True
    assert not board.status().waiting


async def test_wait_times_out_and_ticks(board: Board) -> None:
    ticks: list[float] = []

    async def tick(elapsed: float) -> None:
        ticks.append(elapsed)

    assert await board.wait_for_submit(0.05, tick, interval=0.01) is False
    assert ticks, "progress ticks keep the MCP client's idle timer alive"


async def test_unread_submit_returns_at_once(board: Board, act: Act) -> None:
    act(t="submit", message="done")
    assert await board.wait_for_submit(0.01, _noop) is True
