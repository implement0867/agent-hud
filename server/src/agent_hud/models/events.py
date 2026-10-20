from enum import StrEnum
from typing import Literal

from agent_hud.models.base import Model
from agent_hud.models.board import Board


class EventKind(StrEnum):
    board_changed = "board_changed"
    message_sent = "message_sent"


class BoardChanged(Model):
    kind: Literal[EventKind.board_changed]
    board: Board


class MessageSent(Model):
    kind: Literal[EventKind.message_sent]
    message: str
