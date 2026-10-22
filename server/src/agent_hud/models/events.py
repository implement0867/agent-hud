from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Discriminator, Field, TypeAdapter

from agent_hud.models.actions import Action, TActionId, TBody, TRef
from agent_hud.models.base import Model
from agent_hud.models.board import Board


class EventKind(StrEnum):
    snapshot = "snapshot"
    accepted = "accepted"
    rejected = "rejected"


class AgentState(StrEnum):
    away = "away"
    """No agent's monitor is open."""
    working = "working"
    """An agent has the user's last turn, and has not written since."""
    waiting = "waiting"
    """An agent's monitor is open, and the agent waits for the user's next turn."""


class Snapshot(Model):
    kind: Literal[EventKind.snapshot]
    board: Board
    agent: AgentState
    unsent: int = Field(description="The user's actions since their last send, without moves")


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


class Heard(Action):
    """A user's action as the agent's monitor gets it."""

    parts: dict[TRef, str] = Field(
        description="The text of each part that the action names, as it was when the user acted"
    )


class Turn(Model):
    """The user's actions from one send to the next, as one line on the agent's monitor."""

    actions: tuple[Heard, ...]
