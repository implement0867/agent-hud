from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Discriminator, TypeAdapter

from agent_hud.models.actions import TActionId, TBody
from agent_hud.models.base import Model
from agent_hud.models.board import Board


class EventKind(StrEnum):
    snapshot = "snapshot"
    accepted = "accepted"
    rejected = "rejected"


class Snapshot(Model):
    kind: Literal[EventKind.snapshot]
    board: Board


class Accepted(Model):
    kind: Literal[EventKind.accepted]
    id: TActionId


class Rejected(Model):
    kind: Literal[EventKind.rejected]
    id: TActionId
    reason: str


class Request(Model):
    """An action the page asks the board to take for the user."""

    id: TActionId
    body: TBody


type TPageEvent = Annotated[Snapshot | Accepted | Rejected, Discriminator("kind")]

PageEventAdapter = TypeAdapter[TPageEvent](TPageEvent)
