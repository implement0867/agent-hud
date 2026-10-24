import re
from hashlib import sha1
from pathlib import Path

from pydantic import Field

from agent_hud.hud import Hud
from agent_hud.models.base import Model
from agent_hud.models.events import AgentState

type TBoardId = str


def board_id(key: str) -> TBoardId:
    """
    The id of the board of a key. A plain id, of letters, digits, _ and -, is its own. Any other key, such as the
    directory of the agent's project, gives its last name and a short hash of the whole, so that two directories of
    one name have two boards, and the id names the project.
    """
    if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key):
        return key
    last = next((part for part in reversed(re.split(r"[\\/]+", key)) if part), "")
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", last).strip("-")[:32] or "board"
    return f"{name}-{sha1(key.encode()).hexdigest()[:6]}"


class BoardInfo(Model):
    """A board, for the page's list of boards."""

    id: TBoardId
    cards: int = Field(description="The number of cards on the board")
    agent: AgentState


class Huds:
    """
    The boards, one hud each, by the key that the agent sends with its requests: the directory of its project, or the
    shared board without one. With a directory, each board keeps its state in its own file there, named by its id, and
    every board with a file opens at the start, so that one process holds the directory and the page can open each.
    """

    shared: TBoardId = "shared"

    def __init__(self, directory: Path | None, shared: Hud | None = None) -> None:
        self._directory = directory
        self._huds: dict[TBoardId, Hud] = {}
        if shared is not None:
            self._huds[self.shared] = shared
        if directory is not None:
            for file in sorted(directory.glob("*.db")):
                if file.stem != self.shared or shared is None:
                    self._huds[file.stem] = Hud(file)
        if self.shared not in self._huds:
            self._huds[self.shared] = self._open(self.shared)

    def _open(self, board: TBoardId) -> Hud:
        return Hud(None if self._directory is None else self._directory / f"{board}.db")

    def of(self, key: str | None) -> Hud:
        """The hud of the board of the key, opened if it is new; the shared board without a key."""
        board = board_id(key) if key else self.shared
        if board not in self._huds:
            self._huds[board] = self._open(board)
        return self._huds[board]

    def id_of(self, key: str | None) -> TBoardId:
        return board_id(key) if key else self.shared

    def get(self, board: TBoardId) -> Hud | None:
        """The hud of the board with the id, if there is one."""
        return self._huds.get(board)

    def boards(self) -> list[BoardInfo]:
        """Each board by id, with its card count and the state of its agent, the shared board first."""
        return [
            BoardInfo(id=board, cards=len(hud.board.cards), agent=hud.snapshot().agent)
            for board, hud in sorted(self._huds.items(), key=lambda item: (item[0] != self.shared, item[0]))
        ]

    def compact(self) -> None:
        for hud in self._huds.values():
            hud.compact()

    def close(self) -> None:
        for hud in self._huds.values():
            hud.close()
