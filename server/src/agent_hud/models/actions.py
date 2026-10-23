from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Discriminator, Field, StringConstraints

from agent_hud.models.base import Model

type TCardId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]
type TRef = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}(/[1-9][0-9]*){0,2}$")]
type TActionId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
type TMessage = Annotated[str, StringConstraints(pattern=r"\S")]
type TValue = str | float | bool | None


class Author(StrEnum):
    agent = "agent"
    user = "user"


class Reaction(StrEnum):
    approve = "approve"
    reject = "reject"
    question = "question"


class ActionKind(StrEnum):
    put = "put"
    remove = "remove"
    react = "react"
    unreact = "unreact"
    comment = "comment"
    say = "say"
    fill = "fill"
    link = "link"
    unlink = "unlink"
    move = "move"
    clear = "clear"
    send = "send"


class Put(Model):
    kind: Literal[ActionKind.put]
    id: TCardId = Field(description="Card id, such as plan")
    md: str = Field(min_length=1, description="Markdown shown on the card")


class Remove(Model):
    kind: Literal[ActionKind.remove]
    id: TCardId


class React(Model):
    kind: Literal[ActionKind.react]
    ref: TRef = Field(
        description="A card id, or a card id and the number of a list item, table row or code line in it, such as plan/2"
    )
    reaction: Reaction


class Unreact(Model):
    kind: Literal[ActionKind.unreact]
    ref: TRef


class Comment(Model):
    kind: Literal[ActionKind.comment]
    ref: TRef
    text: TMessage


class Say(Model):
    kind: Literal[ActionKind.say]
    text: TMessage


class Fill(Model):
    kind: Literal[ActionKind.fill]
    ref: TRef = Field(
        description="A cell of an input column, as the card id, row number and column number, such as plan/3/2"
    )
    value: TValue = Field(description="Text, a number, true or false, or one of the options; null clears the cell")


class Link(Model):
    kind: Literal[ActionKind.link]
    id: TCardId = Field(description="Arrow id, such as why")
    src: TRef = Field(description="The part the arrow starts at")
    dst: TRef = Field(description="The part the arrow points to")
    text: str = Field(default="", description="Text on the arrow")


class Unlink(Model):
    kind: Literal[ActionKind.unlink]
    id: TCardId


class Move(Model):
    kind: Literal[ActionKind.move]
    id: TCardId
    x: float = Field(strict=True, allow_inf_nan=False, description="Left edge of the card on the board, in pixels")
    y: float = Field(strict=True, allow_inf_nan=False, description="Top edge of the card on the board, in pixels")


class Clear(Model):
    """A new start: every card goes to its history with its feedback, and the board, its arrows and its chat empty."""

    kind: Literal[ActionKind.clear]


class Send(Model):
    """The end of the user's turn: the agent's monitor gets the user's actions since the last send."""

    kind: Literal[ActionKind.send]


type TAgentBody = Annotated[
    Put | Remove | React | Unreact | Comment | Say | Fill | Link | Unlink | Move | Clear, Discriminator("kind")
]
"""An action of the agent: each kind but send, which only the user's page sends."""
type TBody = Annotated[
    Put | Remove | React | Unreact | Comment | Say | Fill | Link | Unlink | Move | Clear | Send, Discriminator("kind")
]


class Action(Model):
    id: TActionId
    author: Author
    body: TBody

    @property
    def ends_turn(self) -> bool:
        """A send or a chat message from the user ends the user's turn."""
        match self.author, self.body:
            case Author.user, Send() | Say():
                return True
            case _:
                return False


class Misfit(ValueError):
    """An action of a batch that the board does not take: its index in the batch, counted from 1, its kind and the reason."""

    def __init__(self, index: int, kind: ActionKind | None, reason: str) -> None:
        super().__init__(reason)
        self.index = index
        self.kind = kind
        self.reason = reason

    def in_batch(self) -> str:
        """The reason with the action's index and kind, and that the batch was not applied."""
        action = f"action {self.index} ({self.kind})" if self.kind else f"action {self.index}"
        return f"{action}: {self.reason}; no actions were applied"
