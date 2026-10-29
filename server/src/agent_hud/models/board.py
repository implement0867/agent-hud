from collections.abc import Sequence
from typing import Self, assert_never

from pydantic import AwareDatetime, Field, ValidationError, field_validator

from agent_hud.models.actions import (
    Action,
    Author,
    Clear,
    Comment,
    Link,
    Misfit,
    Move,
    Place,
    Put,
    Remove,
    Resize,
    Restore,
    Say,
    Send,
    TActionId,
    TCardId,
    TMessage,
    TQuote,
    Unlink,
)
from agent_hud.models.base import Model
from agent_hud.text import quote_offsets, strip_whitespace, visible_text


def join_error_messages(error: ValidationError) -> str:
    """The messages of a validation error on one line, without pydantic's prefix and footer."""
    return ", ".join(str(detail["msg"]).removeprefix("Value error, ") for detail in error.errors())


class Card(Model):
    md: str = Field(min_length=1)
    author: Author = Field(description="Who put the card first")
    edited: bool = Field(
        default=False,
        description="Whether the latest version is by the other author: the user edited the agent's card, or the agent the user's note",
    )

    @field_validator("md")
    @classmethod
    def _readable(cls, md: str) -> str:
        visible_text(md)
        return md


class Said(Model):
    """A chat message, or a comment in the thread that thread names."""

    id: TActionId
    author: Author
    text: TMessage
    thread: TActionId | None = Field(default=None, description="The thread of a comment; none for a chat message")
    at: AwareDatetime | None = Field(default=None, description="When it was said")


class Anchor(Model):
    """A place in a card: the words that quote names at one of the places they occur, or the card as a whole."""

    card: TCardId
    quote: TQuote = Field(default="", description="The words, as the card shows them; empty for the card as a whole")
    occurrence: int = Field(default=0, description="Which place of the quote in the card's text, from 0")

    def follow(self, before: str, after: str) -> Self | None:
        """
        The anchor on the new markdown of its card: at the place of the quote nearest to where it was, or None when
        the new text does not have the quote. An anchor on the card as a whole stays.
        """
        if not self.quote:
            return self
        was = quote_offsets(before, self.quote)
        found = quote_offsets(after, self.quote)
        if not found:
            return None
        at = was[min(self.occurrence, len(was) - 1)] if was else 0
        nearest = min(range(len(found)), key=lambda n: abs(found[n] - at))
        return self.model_copy(update={"occurrence": nearest})


class Thread(Anchor):
    """The comments on one place of a card, oldest first."""

    comments: tuple[Said, ...] = ()

    def comment(self, said: Said) -> "Thread":
        return self.model_copy(update={"comments": (*self.comments, said)})


class Arrow(Anchor):
    """An arrow from a place of a card to another card."""

    dst: TCardId = Field(description="The card the arrow points to")
    text: str
    author: Author


class Point(Model):
    x: float
    y: float


class Size(Model):
    width: float | None = Field(default=None, description="The width in pixels; none fits the content")
    height: float | None = Field(default=None, description="The height in pixels; none fits the content")


class Version(Model):
    """A card as it was before a put replaced it or a remove took it away, with the threads it had."""

    card: Card
    threads: dict[TActionId, Thread] = Field(default_factory=dict)


class Board(Model):
    cards: dict[TCardId, Card] = Field(default_factory=dict)
    threads: dict[TActionId, Thread] = Field(
        default_factory=dict, description="The threads of comments, by the id of the comment that started each"
    )
    arrows: dict[TCardId, Arrow] = Field(default_factory=dict)
    messages: tuple[Said, ...] = Field(default=(), description="The chat, and each comment, in order")
    positions: dict[TCardId, Point] = Field(default_factory=dict)
    sizes: dict[TCardId, Size] = Field(
        default_factory=dict, description="The size of each card that the user or the agent resized, in pixels"
    )
    history: dict[TCardId, tuple[Version, ...]] = Field(
        default_factory=dict, description="The earlier versions of each card, oldest first"
    )

    def apply_all(self, actions: Sequence[Action]) -> "Board":
        """The board after the actions, in order. Misfit, with the index of the action, when one does not fit the board."""
        board = self
        for n, action in enumerate(actions, start=1):
            try:
                board = board.apply(action)
            except ValueError as error:
                raise Misfit(n, action.body.kind, str(error)) from error
        return board

    def apply(self, action: Action) -> "Board":
        """The board after the action. ValueError, which names the valid choices, if the action does not fit the board."""
        match action.body:
            case Put(id=card_id, md=md, version=version):
                if version is not None:
                    self._check_version(card_id, version)
                try:
                    card = Card(md=md, author=action.author)
                except ValidationError as error:
                    raise ValueError(f"card '{card_id}': {join_error_messages(error)}") from error
                return self._revise(card_id, card)
            case Restore(id=card_id):
                if card_id in self.cards:
                    raise ValueError(f"card '{card_id}' is on the board")
                if not (versions := self.history.get(card_id)):
                    raise ValueError(f"no card '{card_id}' in the history")
                return self._revise(card_id, versions[-1].card)
            case Remove(id=card_id):
                self._check_card(card_id)
                return self._retire(card_id)
            case Comment(card=card_id, quote=quote, occurrence=occurrence, text=text):
                thread_id = self._thread_at(card_id, quote, occurrence) or action.id
                thread = self.threads.get(thread_id) or Thread(
                    card=card_id, quote=quote, occurrence=self._occurrence(card_id, quote, occurrence)
                )
                said = Said(id=action.id, author=action.author, text=text, thread=thread_id, at=action.at)
                threads = {**self.threads, thread_id: thread.comment(said)}
                return self.model_copy(update={"threads": threads, "messages": (*self.messages, said)})
            case Link(id=arrow_id, card=card_id, quote=quote, occurrence=occurrence, dst=dst, text=text):
                kept = self.arrows.get(arrow_id)
                at = (
                    kept.occurrence
                    if kept is not None
                    and occurrence is None
                    and (kept.card, strip_whitespace(kept.quote)) == (card_id, strip_whitespace(quote))
                    else self._occurrence(card_id, quote, occurrence)
                )
                self._check_card(dst)
                arrow = Arrow(card=card_id, quote=quote, occurrence=at, dst=dst, text=text, author=action.author)
                return self.model_copy(update={"arrows": {**self.arrows, arrow_id: arrow}})
            case Unlink(id=arrow_id):
                if arrow_id not in self.arrows:
                    raise ValueError(f"no arrow '{arrow_id}'")
                return self.model_copy(update={"arrows": {k: v for k, v in self.arrows.items() if k != arrow_id}})
            case Move(id=card_id, x=x, y=y):
                self._check_card(card_id)
                return self.model_copy(update={"positions": {**self.positions, card_id: Point(x=x, y=y)}})
            case Place(id=card_id, x=x, y=y):
                self._check_card(card_id)
                if card_id in self.positions:
                    return self
                return self.model_copy(update={"positions": {**self.positions, card_id: Point(x=x, y=y)}})
            case Resize(id=card_id, width=width, height=height):
                self._check_card(card_id)
                size = self.sizes.get(card_id, Size())
                size = Size(
                    width=size.width if width is None else width, height=size.height if height is None else height
                )
                return self.model_copy(update={"sizes": {**self.sizes, card_id: size}})
            case Say(text=text):
                said = Said(id=action.id, author=action.author, text=text, at=action.at)
                return self.model_copy(update={"messages": (*self.messages, said)})
            case Clear():
                retired = self
                for card_id in self.cards:
                    retired = retired._retire(card_id)
                return retired.model_copy(update={"messages": ()})
            case Send():
                return self
            case _:
                assert_never(action.body)

    def _check_card(self, card_id: TCardId) -> None:
        """ValueError, which lists the cards, if the board has no such card."""
        if card_id not in self.cards:
            cards = f"the cards are {', '.join(self.cards)}" if self.cards else "the board has no cards"
            raise ValueError(f"no card '{card_id}': {cards}")

    def _check_version(self, card_id: TCardId, version: int) -> None:
        """ValueError unless the card is on the board with that number of earlier versions."""
        earlier = len(self.history.get(card_id, ()))
        if card_id not in self.cards:
            raise ValueError(f"card '{card_id}' is gone: it was removed after version {earlier}")
        if earlier != version:
            raise ValueError(f"card '{card_id}' changed: it has {earlier} earlier versions, not {version}")

    def _occurrence(self, card_id: TCardId, quote: str, occurrence: int | None) -> int:
        """
        The place of the quote in the card: the one given, or the only one. ValueError, which says how many places the
        card has the quote at, when the card does not have it there, or has it at more than one place and none is given.
        """
        self._check_card(card_id)
        if not quote:
            return 0
        count = len(quote_offsets(self.cards[card_id].md, quote))
        match count, occurrence:
            case 0, _:
                raise ValueError(f"card '{card_id}' does not show the words '{quote}': quote its text without markdown")
            case 1, None:
                return 0
            case _, None:
                raise ValueError(
                    f"card '{card_id}' shows '{quote}' at {count} places: give the occurrence, from 0, or quote more words"
                )
            case _, found if found >= count:
                raise ValueError(
                    f"card '{card_id}' shows '{quote}' at {count} places, so occurrence is 0 to {count - 1}"
                )
            case _, found:
                return found

    def _thread_at(self, card_id: TCardId, quote: str, occurrence: int | None) -> TActionId | None:
        """The thread on the same words of the card, at the occurrence when one is given, if there is one."""
        return next(
            (
                thread_id
                for thread_id, thread in self.threads.items()
                if thread.card == card_id
                and strip_whitespace(thread.quote) == strip_whitespace(quote)
                and occurrence in (None, thread.occurrence)
            ),
            None,
        )

    def _revise(self, card_id: TCardId, card: Card) -> "Board":
        """
        The board with the card in place of the one with its id, if there was one; the card keeps that one's author,
        and counts as edited when the other author put it.
        The threads and arrows on words that the new text still has follow them, to the place nearest to where they
        were; the threads on words that are gone go to the card's history with the card as it was, and their arrows drop.
        """
        if card_id not in self.cards:
            return self.model_copy(update={"cards": {**self.cards, card_id: card}})
        old = self.cards[card_id]
        card = card.model_copy(update={"author": old.author, "edited": card.author != old.author})
        threads: dict[TActionId, Thread] = {}
        gone: dict[TActionId, Thread] = {}
        for thread_id, thread in self.threads.items():
            if thread.card != card_id:
                threads[thread_id] = thread
            elif (moved := thread.follow(old.md, card.md)) is not None:
                threads[thread_id] = moved
            else:
                gone[thread_id] = thread
        arrows = {
            arrow_id: moved
            for arrow_id, arrow in self.arrows.items()
            if (moved := arrow if arrow.card != card_id else arrow.follow(old.md, card.md)) is not None
        }
        version = Version(card=old, threads=gone)
        return self.model_copy(
            update={
                "cards": {**self.cards, card_id: card},
                "threads": threads,
                "arrows": arrows,
                "history": {**self.history, card_id: (*self.history.get(card_id, ()), version)},
            }
        )

    def _retire(self, card_id: TCardId) -> "Board":
        """
        The board without the card, its place, its size, its threads and the arrows at it, with the card and its
        threads at the end of its history.
        """
        version = Version(
            card=self.cards[card_id],
            threads={thread_id: thread for thread_id, thread in self.threads.items() if thread.card == card_id},
        )
        return self.model_copy(
            update={
                "cards": {k: v for k, v in self.cards.items() if k != card_id},
                "positions": {k: v for k, v in self.positions.items() if k != card_id},
                "sizes": {k: v for k, v in self.sizes.items() if k != card_id},
                "threads": {k: v for k, v in self.threads.items() if v.card != card_id},
                "arrows": {k: v for k, v in self.arrows.items() if card_id not in (v.card, v.dst)},
                "history": {**self.history, card_id: (*self.history.get(card_id, ()), version)},
            }
        )
