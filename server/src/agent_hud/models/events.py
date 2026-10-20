from enum import StrEnum
from typing import Annotated, Literal

from pydantic import StringConstraints

from agent_hud.models.base import Model
from agent_hud.models.board import Board

type Message = Annotated[str, StringConstraints(pattern=r"\S")]


class Turn(StrEnum):
    agent = "agent"
    user = "user"


class View(Model):
    """What the page shows: the board, and whose turn it is. It is the user's turn while the agent waits."""

    board: Board
    turn: Turn


class EventKind(StrEnum):
    view_changed = "view_changed"
    message_sent = "message_sent"
    message_received = "message_received"


class ViewChanged(Model):
    kind: Literal[EventKind.view_changed]
    view: View


class MessageSent(Model):
    kind: Literal[EventKind.message_sent]
    message: Message


class MessageReceived(Model):
    kind: Literal[EventKind.message_received]
