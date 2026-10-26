from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Discriminator, Field, StringConstraints, model_validator

from agent_hud.models.base import Model

type TCardId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]
type TActionId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
type TMessage = Annotated[str, StringConstraints(pattern=r"\S")]
type TQuote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class Author(StrEnum):
    agent = "agent"
    user = "user"


class ActionKind(StrEnum):
    put = "put"
    remove = "remove"
    restore = "restore"
    comment = "comment"
    say = "say"
    link = "link"
    unlink = "unlink"
    move = "move"
    resize = "resize"
    place = "place"
    clear = "clear"
    send = "send"


class Put(Model):
    kind: Literal[ActionKind.put]
    id: TCardId = Field(description="Card id, such as plan")
    md: str = Field(min_length=1, description="Markdown shown on the card")
    version: int | None = Field(
        default=None,
        ge=0,
        description="The number of earlier versions the card has, as its history counts them; the put is refused when the card has another number or is gone, so that an edit does not replace a newer card. Without it, the put replaces whatever is there",
    )


class Remove(Model):
    kind: Literal[ActionKind.remove]
    id: TCardId


class Restore(Model):
    """The last version of a removed card, back on the board as it was; its history stays."""

    kind: Literal[ActionKind.restore]
    id: TCardId


class Comment(Model):
    """A comment on the text that quote names in the card, or on the card as a whole; it starts a thread there, or joins the thread on the same text."""

    kind: Literal[ActionKind.comment]
    card: TCardId = Field(description="Card id, such as plan")
    quote: TQuote = Field(
        default="",
        description="The words of the card the comment is on, as the card shows them, without markdown; empty for the card as a whole",
    )
    occurrence: int | None = Field(
        default=None,
        ge=0,
        description="Which place of the quote, from 0, when the card has the quote at more than one place",
    )
    text: TMessage


class Say(Model):
    kind: Literal[ActionKind.say]
    text: TMessage


class Link(Model):
    kind: Literal[ActionKind.link]
    id: TCardId = Field(description="Arrow id, such as why")
    card: TCardId = Field(description="The card the arrow starts at")
    quote: TQuote = Field(default="", description="The words of the card the arrow starts at; empty for the card")
    occurrence: int | None = Field(default=None, ge=0, description="Which place of the quote, from 0")
    dst: TCardId = Field(description="The card the arrow points to")
    text: str = Field(default="", description="Text on the arrow")


class Unlink(Model):
    kind: Literal[ActionKind.unlink]
    id: TCardId


class Move(Model):
    kind: Literal[ActionKind.move]
    id: TCardId
    x: float = Field(strict=True, allow_inf_nan=False, description="Left edge of the card on the board, in pixels")
    y: float = Field(strict=True, allow_inf_nan=False, description="Top edge of the card on the board, in pixels")


class Resize(Model):
    """The size of a card; a dimension it leaves out stays as it is."""

    kind: Literal[ActionKind.resize]
    id: TCardId
    width: float | None = Field(
        default=None, strict=True, gt=0, allow_inf_nan=False, description="Width of the card on the board, in pixels"
    )
    height: float | None = Field(
        default=None,
        strict=True,
        gt=0,
        allow_inf_nan=False,
        description="Height of the card on the board, in pixels; a card shorter than its text scrolls",
    )

    @model_validator(mode="after")
    def _some(self) -> Self:
        if self.width is None and self.height is None:
            raise ValueError("resize takes a width, a height or both")
        return self


class Place(Model):
    """
    The place that the page gives a card that has none, once the page has the card's size: the first place of a card
    wins, so that every tab and reload shows the card there, and a later place changes nothing.
    """

    kind: Literal[ActionKind.place]
    id: TCardId
    x: float = Field(strict=True, allow_inf_nan=False)
    y: float = Field(strict=True, allow_inf_nan=False)


class Clear(Model):
    """A new start: every card goes to its history with its feedback, and the board, its arrows and its chat empty."""

    kind: Literal[ActionKind.clear]


class Send(Model):
    """The end of the user's turn: the agent's monitor gets the user's actions since the last send."""

    kind: Literal[ActionKind.send]


type TAgentBody = Annotated[
    Put | Remove | Restore | Comment | Say | Link | Unlink | Move | Resize | Clear,
    Discriminator("kind"),
]
"""An action of the agent: each kind but place and send, which only the user's page sends."""
type TBody = Annotated[
    Put | Remove | Restore | Comment | Say | Link | Unlink | Move | Resize | Place | Clear | Send,
    Discriminator("kind"),
]


class Action(Model):
    id: TActionId
    author: Author
    body: TBody
    at: AwareDatetime | None = Field(default=None, description="When the board took the action")

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
