from enum import StrEnum
from typing import Literal

from agent_hud.models.base import Model
from agent_hud.models.board import Board


class EventKind(StrEnum):
    board = "board"
    send = "send"


class BoardEvent(Model):
    kind: Literal[EventKind.board]
    board: Board


class SendEvent(Model):
    kind: Literal[EventKind.send]
    message: str
