"""Optional board persistence to a JSON file, debounced."""

import asyncio
import logging
from pathlib import Path

from agent_hud.board import Board, BoardState

log = logging.getLogger(__name__)


class Persistence:
    def __init__(self, board: Board, path: Path, delay: float = 0.5) -> None:
        self.board: Board = board
        self.path: Path = path
        self.delay: float = delay
        self._handle: asyncio.TimerHandle | None = None

    def load(self) -> None:
        if self.path.is_file():
            self.board.restore(BoardState.model_validate_json(self.path.read_bytes()))

    def attach(self) -> None:
        self.board.on_persist = self.schedule

    def schedule(self) -> None:
        if self._handle is None:
            self._handle = asyncio.get_running_loop().call_later(self.delay, self.save)

    def save(self) -> None:
        self._handle = None
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(self.board.dump().model_dump_json())
            tmp.replace(self.path)
        except OSError:
            log.exception("could not save board to %s", self.path)
