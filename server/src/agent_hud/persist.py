import asyncio
import contextlib
import logging
from pathlib import Path

from agent_hud.hub import Hub
from agent_hud.state import BoardState

log = logging.getLogger(__name__)


class Persistence:
    """Keeps the board in a JSON file: loads it on attach, then saves shortly after each change."""

    def __init__(self, path: Path, delay: float = 0.5) -> None:
        self.path: Path = path
        self.delay: float = delay
        self._pending: asyncio.TimerHandle | None = None

    def attach(self, hub: Hub) -> None:
        if self.path.is_file():
            hub.state = BoardState.model_validate_json(self.path.read_bytes())
        hub.listen(lambda _: self._schedule(hub.state))

    def _schedule(self, state: BoardState) -> None:
        if self._pending is not None:
            return
        try:
            self._pending = asyncio.get_running_loop().call_later(self.delay, self.save, state)
        except RuntimeError:
            self.save(state)

    def save(self, state: BoardState) -> None:
        self._pending = None
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(state.model_dump_json())
            tmp.replace(self.path)
        except OSError:
            log.exception("could not save board to %s", self.path)
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
