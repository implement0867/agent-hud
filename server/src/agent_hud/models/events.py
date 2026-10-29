from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Discriminator, Field, TypeAdapter

from agent_hud.models.actions import Author, TActionId, TBody, TCardId
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
    """An agent's monitor has the user's last turn, and the agent has not written since."""
    waiting = "waiting"
    """An agent's monitor is open, and the agent waits for the user's next turn."""


class Edit(Model):
    """The user's put on a card that was on the board, as the change to its markdown."""

    kind: Literal["edit"]
    id: TCardId
    diff: str = Field(description="A unified diff of the card's markdown, without the file header")


type THeardBody = Annotated[TBody | Edit, Discriminator("kind")]


class Heard(Model):
    """A user's action as the agent's monitor gets it."""

    id: TActionId
    author: Author
    body: THeardBody


class Snapshot(Model):
    kind: Literal[EventKind.snapshot]
    board: Board
    agent: AgentState
    pending: tuple[Heard, ...] = Field(description="The user's turn so far, as the agent will hear it on the send")
    waiting: int = Field(description="The user's turns that were sent and that no agent has taken")


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


HeardBodyAdapter = TypeAdapter[THeardBody](THeardBody)


class Turn(Model):
    """The changes that the user made from one send to the next, as the agent's monitor gets them: the user's actions in order."""

    id: TActionId = Field(
        description="The id of the send or chat message that ended the turn; the same id from two monitors is one turn"
    )
    actions: tuple[THeardBody, ...]

    @classmethod
    def of(cls, turn_id: TActionId, heard: Iterable[Heard]) -> Self:
        """The turn of the actions as the agent hears them."""
        return cls(id=turn_id, actions=tuple(action.body for action in heard))
