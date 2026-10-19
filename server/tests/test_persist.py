import asyncio
from pathlib import Path

from agent_hud.board import Board
from agent_hud.persist import Persistence
from tests.conftest import Act, Write


async def test_board_survives_a_restart(board: Board, write: Write, act: Act, tmp_path: Path) -> None:
    path = tmp_path / "state" / "board.json"
    Persistence(board, path, delay=0.01).attach()
    write({"op": "put", "id": "plan", "md": "1. a\n2. b"})
    act(t="react", id="plan", anchor="", reaction="approve")
    await asyncio.sleep(0.05)

    restored = Board(project="test")
    Persistence(restored, path).load()
    assert restored.show(["*"]) == board.show(["*"])
    assert restored.report() == "plan approve", "unread changes survive too"


def test_missing_file_starts_empty(tmp_path: Path) -> None:
    board = Board(project="test")
    Persistence(board, tmp_path / "none.json").load()
    assert board.elements == {}
