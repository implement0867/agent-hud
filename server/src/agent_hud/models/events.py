from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Discriminator, StringConstraints

from agent_hud.models.base import Model
from agent_hud.models.board import Board
from agent_hud.models.card import Reaction, TCardId

type TMessage = Annotated[str, StringConstraints(pattern=r"\S")]


class EventKind(StrEnum):
    board_changed = "board_changed"
    message_sent = "message_sent"
    message_received = "message_received"
    reaction_set = "reaction_set"


class BoardChanged(Model):
    kind: Literal[EventKind.board_changed]
    board: Board


class MessageSent(Model):
    kind: Literal[EventKind.message_sent]
    message: TMessage


class MessageReceived(Model):
    kind: Literal[EventKind.message_received]


class ReactionSet(Model):
    kind: Literal[EventKind.reaction_set]
    id: TCardId
    reaction: Reaction | None


type TPageEvent = Annotated[MessageSent | ReactionSet, Discriminator("kind")]
