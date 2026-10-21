from typing import assert_never

from pydantic import Field

from agent_hud.models.actions import (
    Action,
    Author,
    Comment,
    Put,
    React,
    Reaction,
    Remove,
    Say,
    TActionId,
    TCardId,
    TMessage,
    TRef,
    Unreact,
)
from agent_hud.models.base import Model
from agent_hud.outline import Outline


class Card(Model):
    md: str = Field(min_length=1)
    author: Author


class Said(Model):
    id: TActionId
    author: Author
    text: TMessage


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
            case Put() | Remove() | Say():
                raise ValueError(f"a thread does not take {action.body.kind}")
            case _:
                assert_never(action.body)


class Board(Model):
    cards: dict[TCardId, Card] = Field(default_factory=dict)
    threads: dict[TRef, Thread] = Field(default_factory=dict)

    def apply(self, action: Action) -> "Board":
        """The board after the action. ValueError if the action does not fit the board."""
        match action.body:
            case Put(id=card_id, md=md):
                return Board(
                    cards={**self.cards, card_id: Card(md=md, author=action.author)}, threads=self._without(card_id)
                )
            case Remove(id=card_id) if card_id in self.cards:
                return Board(
                    cards={k: v for k, v in self.cards.items() if k != card_id}, threads=self._without(card_id)
                )
            case Remove(id=card_id):
                raise ValueError(f"no card '{card_id}'")
            case React(ref=ref) | Unreact(ref=ref) | Comment(ref=ref) if not self._has(ref):
                raise ValueError(f"no part '{ref}'")
            case React(ref=ref) | Unreact(ref=ref) | Comment(ref=ref):
                thread = self.threads.get(ref, Thread()).apply(action)
                return Board(cards=self.cards, threads={**self.threads, ref: thread})
            case Say():
                return self
            case _:
                assert_never(action.body)

    def _has(self, ref: TRef) -> bool:
        card_id, _, path = ref.partition("/")
        return card_id in self.cards and (not path or path in Outline(self.cards[card_id].md))

    def _without(self, card_id: TCardId) -> dict[TRef, Thread]:
        return {ref: thread for ref, thread in self.threads.items() if ref.partition("/")[0] != card_id}
