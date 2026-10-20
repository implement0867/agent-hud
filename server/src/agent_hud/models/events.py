from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent_hud.models.board import Board


class EventKind(StrEnum):
    board = "board"


class BoardEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[EventKind.board]
    board: Board
