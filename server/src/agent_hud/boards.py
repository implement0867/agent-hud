import re
from hashlib import sha1
from pathlib import Path
from typing import Annotated, ClassVar, NewType

from pydantic import AfterValidator, Field

from agent_hud.hud import Hud
from agent_hud.models.base import Model
from agent_hud.models.events import AgentState

BoardId = NewType("BoardId", str)
"""The name of one board: 1 to 64 letters, digits, `_` or `-`. It is also the stem of the board's state file."""


def is_board_id(text: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_-]{1,64}", text) is not None


def parse_board_id(text: str) -> BoardId:
    """Return text as a BoardId. Raise ValueError if it is not 1 to 64 letters, digits, `_` or `-`."""
    if not is_board_id(text):
        raise ValueError(f"{text!r} is not a board id: use 1 to 64 letters, digits, _ or -")
    return BoardId(text)


def board_id_for_project(project: str) -> BoardId:
    """Return a valid project key as is, and for a path, its last part plus a 6-digit hash of the full path."""
    if is_board_id(project):
        return BoardId(project)
    last_part = next((part for part in reversed(re.split(r"[\\/]+", project)) if part), "")
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", last_part).strip("-")[:32] or "board"
    return parse_board_id(f"{name}-{sha1(project.encode()).hexdigest()[:6]}")


class BoardSummary(Model):
    """One row of the page's list of boards."""

    id: Annotated[BoardId, AfterValidator(parse_board_id)]
    cards: int = Field(description="The number of cards on the board")
    agent: AgentState


class BoardRegistry:
    """
    Maps each board id to the open Hud of that board.
    With a directory, each board keeps its state in `<directory>/<board id>.db`, and every such file opens at the start.
    """

    default_board_id: ClassVar[BoardId] = BoardId("shared")

    def __init__(self, directory: Path | None, default_hud: Hud | None = None) -> None:
        self._directory = directory
        self._huds_by_board_id: dict[BoardId, Hud] = {}
        if default_hud is not None:
            self._huds_by_board_id[self.default_board_id] = default_hud
        if directory is not None:
            for state_file in sorted(directory.glob("*.db")):
                board_id = state_file.stem
                if is_board_id(board_id) and board_id not in self._huds_by_board_id:
                    self._huds_by_board_id[BoardId(board_id)] = Hud(state_file)
        if self.default_board_id not in self._huds_by_board_id:
            self._huds_by_board_id[self.default_board_id] = self._open(self.default_board_id)

    def _open(self, board_id: BoardId) -> Hud:
        return Hud(None if self._directory is None else self._directory / f"{board_id}.db")

    def board_id_for(self, project: str | None) -> BoardId:
        """The board id of the project, or the default board id without a project."""
        return board_id_for_project(project) if project else self.default_board_id

    def hud_for(self, project: str | None) -> Hud:
        """The Hud of the project's board, opened if it is new."""
        board_id = self.board_id_for(project)
        if board_id not in self._huds_by_board_id:
            self._huds_by_board_id[board_id] = self._open(board_id)
        return self._huds_by_board_id[board_id]

    def find(self, board_id: str) -> Hud | None:
        """The Hud of an open board, or None."""
        return self._huds_by_board_id.get(BoardId(board_id)) if is_board_id(board_id) else None

    def summaries(self) -> list[BoardSummary]:
        """A summary of each open board, the default board first."""
        return [
            BoardSummary(id=board_id, cards=len(hud.board.cards), agent=hud.snapshot().agent)
            for board_id, hud in sorted(
                self._huds_by_board_id.items(), key=lambda item: (item[0] != self.default_board_id, item[0])
            )
        ]

    def compact(self) -> None:
        for hud in self._huds_by_board_id.values():
            hud.compact()

    def close(self) -> None:
        for hud in self._huds_by_board_id.values():
            hud.close()
