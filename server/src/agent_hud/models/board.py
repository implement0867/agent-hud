from typing import assert_never

from pydantic import Field, field_validator

from agent_hud.models.actions import (
    Action,
    Author,
    Comment,
    Fill,
    Link,
    Put,
    React,
    Reaction,
    Remove,
    Say,
    TActionId,
    TCardId,
    TMessage,
    TRef,
    TValue,
    Unlink,
    Unreact,
)
from agent_hud.models.base import Model
from agent_hud.models.columns import Column
from agent_hud.outline import Outline


class Card(Model):
    md: str = Field(min_length=1)
    author: Author

    @field_validator("md")
    @classmethod
    def _readable(cls, md: str) -> str:
        Outline(md)
        return md


class Said(Model):
    id: TActionId
    author: Author
    text: TMessage


class Arrow(Model):
    src: TRef
    dst: TRef
    text: str
    author: Author


class Thread(Model):
    """The reaction and comments on one part of the board."""

    reaction: Reaction | None = None
    comments: tuple[Said, ...] = ()

    def apply(self, action: Action) -> "Thread":
        match action.body:
            case React(reaction=reaction):
                return self.model_copy(update={"reaction": reaction})
            case Unreact():
                return self.model_copy(update={"reaction": None})
            case Comment(text=text):
                said = Said(id=action.id, author=action.author, text=text)
                return self.model_copy(update={"comments": (*self.comments, said)})
            case Put() | Remove() | Say() | Fill() | Link() | Unlink():
                raise ValueError(f"a thread does not take {action.body.kind}")
            case _:
                assert_never(action.body)


class Board(Model):
    cards: dict[TCardId, Card] = Field(default_factory=dict)
    threads: dict[TRef, Thread] = Field(default_factory=dict)
    values: dict[TRef, TValue] = Field(default_factory=dict)
    arrows: dict[TCardId, Arrow] = Field(default_factory=dict)

    def apply(self, action: Action) -> "Board":
        """The board after the action. ValueError if the action does not fit the board."""
        match action.body:
            case Put(id=card_id, md=md):
                cards = {**self.cards, card_id: Card(md=md, author=action.author)}
                return self._clear(card_id).model_copy(update={"cards": cards})
            case Remove(id=card_id) if card_id in self.cards:
                cards = {k: v for k, v in self.cards.items() if k != card_id}
                return self._clear(card_id).model_copy(update={"cards": cards})
            case Remove(id=card_id):
                raise ValueError(f"no card '{card_id}'")
            case React(ref=ref) | Unreact(ref=ref) | Comment(ref=ref) if ref not in self._parts(ref):
                raise ValueError(f"no part '{ref}'")
            case React(ref=ref) | Unreact(ref=ref) | Comment(ref=ref):
                thread = self.threads.get(ref, Thread()).apply(action)
                return self.model_copy(update={"threads": {**self.threads, ref: thread}})
            case Fill(ref=ref, value=value):
                match self._inputs(ref).get(ref):
                    case None:
                        raise ValueError(f"no input '{ref}'")
                    case column if not column.fits(value):
                        raise ValueError(f"input '{ref}' takes {column.kind} values")
                    case _:
                        return self.model_copy(update={"values": {**self.values, ref: value}})
            case Link(src=src) if src not in self._parts(src):
                raise ValueError(f"no part '{src}'")
            case Link(dst=dst) if dst not in self._parts(dst):
                raise ValueError(f"no part '{dst}'")
            case Link(id=arrow_id, src=src, dst=dst, text=text):
                arrow = Arrow(src=src, dst=dst, text=text, author=action.author)
                return self.model_copy(update={"arrows": {**self.arrows, arrow_id: arrow}})
            case Unlink(id=arrow_id) if arrow_id in self.arrows:
                return self.model_copy(update={"arrows": {k: v for k, v in self.arrows.items() if k != arrow_id}})
            case Unlink(id=arrow_id):
                raise ValueError(f"no arrow '{arrow_id}'")
            case Say():
                return self
            case _:
                assert_never(action.body)

    def _parts(self, ref: TRef) -> set[TRef]:
        """The card that the ref names, and its parts, as refs."""
        card_id = ref.partition("/")[0]
        if card_id not in self.cards:
            return set()
        return {card_id, *(f"{card_id}/{path}" for path in Outline(self.cards[card_id].md).paths)}

    def _inputs(self, ref: TRef) -> dict[TRef, Column]:
        """The input cells of the card that the ref names, by ref."""
        card_id = ref.partition("/")[0]
        if card_id not in self.cards:
            return {}
        return {f"{card_id}/{path}": column for path, column in Outline(self.cards[card_id].md).inputs.items()}

    def _clear(self, card_id: TCardId) -> "Board":
        """The board without the threads, values and arrows on the card."""
        threads = {ref: thread for ref, thread in self.threads.items() if ref.partition("/")[0] != card_id}
        values = {ref: value for ref, value in self.values.items() if ref.partition("/")[0] != card_id}
        arrows = {
            arrow_id: arrow
            for arrow_id, arrow in self.arrows.items()
            if card_id not in (arrow.src.partition("/")[0], arrow.dst.partition("/")[0])
        }
        return self.model_copy(update={"threads": threads, "values": values, "arrows": arrows})
