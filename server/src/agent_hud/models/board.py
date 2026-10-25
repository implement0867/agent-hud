from typing import assert_never

from pydantic import AwareDatetime, Field, ValidationError, field_validator

from agent_hud.models.actions import (
    Action,
    Author,
    Clear,
    Comment,
    Fill,
    Link,
    Move,
    Place,
    Put,
    React,
    Reaction,
    Remove,
    Resize,
    Restore,
    Say,
    Send,
    TActionId,
    TBody,
    TCardId,
    TMessage,
    TRef,
    TValue,
    Unlink,
    Unreact,
)
from agent_hud.models.base import Model
from agent_hud.models.columns import Column
from agent_hud.models.refs import Ref, card_of, named_refs
from agent_hud.outline import Outline, outline_of


def one_line(error: ValidationError) -> str:
    """The messages of a validation error on one line, without pydantic's prefix and footer."""
    return ", ".join(str(detail["msg"]).removeprefix("Value error, ") for detail in error.errors())


def part_range(card_id: TCardId, outline: Outline) -> str:
    """The range of the card's parts, for an error on a ref that is not one of them."""
    count = len(outline.texts)
    return f"card '{card_id}' has parts 1 to {count}" if count else f"card '{card_id}' has no parts"


def column_label(label: str, column: Column) -> str:
    """The label of a cell or column with the column's name, such as 3 (size)."""
    return f"{label} ({column.name})" if column.name else label


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
        outline_of(md)
        return md


class Said(Model):
    """A chat message, or a comment on the part that ref names."""

    id: TActionId
    author: Author
    text: TMessage
    ref: TRef | None = None
    at: AwareDatetime | None = Field(default=None, description="When it was said")


class Arrow(Model):
    src: TRef
    dst: TRef
    text: str
    author: Author


class Point(Model):
    x: float
    y: float


class Thread(Model):
    """The reaction of each author and the comments on one part of the board."""

    reactions: dict[Author, Reaction] = Field(default_factory=dict)
    comments: tuple[Said, ...] = ()

    def react(self, author: Author, reaction: Reaction) -> "Thread":
        return self.model_copy(update={"reactions": {**self.reactions, author: reaction}})

    def unreact(self, author: Author) -> "Thread":
        return self.model_copy(update={"reactions": {k: v for k, v in self.reactions.items() if k != author}})

    def comment(self, said: Said) -> "Thread":
        return self.model_copy(update={"comments": (*self.comments, said)})

    def at(self, ref: TRef) -> "Thread":
        """The thread with its comments on the part that ref names."""
        return self.model_copy(
            update={"comments": tuple(said.model_copy(update={"ref": ref}) for said in self.comments)}
        )


def matched(before: Outline, after: Outline) -> dict[str, str]:
    """The path in the new outline of each part of the old one whose text is there, matched in order."""
    free: dict[str, list[str]] = {}
    for path, text in after.texts.items():
        free.setdefault(text, []).append(path)
    return {path: free[text].pop(0) for path, text in before.texts.items() if free.get(text)}


class Version(Model):
    """A card as it was before a put replaced it or a remove took it away, with its feedback."""

    card: Card
    threads: dict[TRef, Thread] = Field(default_factory=dict)
    values: dict[TRef, TValue] = Field(default_factory=dict)


class Board(Model):
    cards: dict[TCardId, Card] = Field(default_factory=dict)
    threads: dict[TRef, Thread] = Field(default_factory=dict)
    values: dict[TRef, TValue] = Field(default_factory=dict)
    arrows: dict[TCardId, Arrow] = Field(default_factory=dict)
    messages: tuple[Said, ...] = Field(default=(), description="The chat, and each comment on a part, in order")
    positions: dict[TCardId, Point] = Field(default_factory=dict)
    widths: dict[TCardId, float] = Field(
        default_factory=dict, description="The width of each card that the user or the agent resized, in pixels"
    )
    history: dict[TCardId, tuple[Version, ...]] = Field(
        default_factory=dict, description="The earlier versions of each card, oldest first"
    )

    def texts_of(self, card_id: TCardId) -> dict[str, str]:
        """The text of each part of the card by its number, in document order, such as {"1": "parse", "2": "render"}."""
        return outline_of(self.cards[card_id].md).texts

    def part_texts(self, body: TBody) -> dict[TRef, str]:
        """The text of each part that the action names, as the board has it now."""
        return {ref: text for ref in named_refs(body) if (text := self._text(ref)) is not None}

    def _text(self, ref: TRef) -> str | None:
        card_id, part, _ = Ref.parse(ref)
        return self.texts_of(card_id).get(part) if card_id in self.cards else None

    def apply(self, action: Action) -> "Board":
        """The board after the action. ValueError, which names the valid choices, if the action does not fit the board."""
        match action.body:
            case Put(id=card_id, md=md, version=version):
                if version is not None:
                    self._check_version(card_id, version)
                try:
                    card = Card(md=md, author=action.author)
                except ValidationError as error:
                    raise ValueError(f"card '{card_id}': {one_line(error)}") from error
                return self._revise(card_id, card)
            case Restore(id=card_id):
                if card_id in self.cards:
                    raise ValueError(f"card '{card_id}' is on the board")
                if not (versions := self.history.get(card_id)):
                    raise ValueError(f"no card '{card_id}' in the history")
                return self._revise(card_id, versions[-1].card)
            case Remove(id=card_id):
                self._outline_of(card_id)
                return self._retire(card_id)
            case Comment(ref=ref, text=text):
                self._check_part(ref)
                said = Said(id=action.id, author=action.author, text=text, ref=ref, at=action.at)
                threads = {**self.threads, ref: self.threads.get(ref, Thread()).comment(said)}
                return self.model_copy(update={"threads": threads, "messages": (*self.messages, said)})
            case React(ref=ref, reaction=reaction):
                self._check_part(ref)
                thread = self.threads.get(ref, Thread()).react(action.author, reaction)
                return self.model_copy(update={"threads": {**self.threads, ref: thread}})
            case Unreact(ref=ref):
                self._check_part(ref)
                thread = self.threads.get(ref, Thread()).unreact(action.author)
                return self.model_copy(update={"threads": {**self.threads, ref: thread}})
            case Fill(ref=ref, value=value):
                column = self._input_of(ref)
                if not column.fits(value):
                    label = column_label(f"'{ref}'", column)
                    raise ValueError(f"input {label} takes {column.takes}")
                return self.model_copy(update={"values": {**self.values, ref: value}})
            case Link(id=arrow_id, src=src, dst=dst, text=text):
                self._check_part(src)
                self._check_part(dst)
                arrow = Arrow(src=src, dst=dst, text=text, author=action.author)
                return self.model_copy(update={"arrows": {**self.arrows, arrow_id: arrow}})
            case Unlink(id=arrow_id):
                if arrow_id not in self.arrows:
                    raise ValueError(f"no arrow '{arrow_id}'")
                return self.model_copy(update={"arrows": {k: v for k, v in self.arrows.items() if k != arrow_id}})
            case Move(id=card_id, x=x, y=y):
                self._outline_of(card_id)
                return self.model_copy(update={"positions": {**self.positions, card_id: Point(x=x, y=y)}})
            case Place(id=card_id, x=x, y=y):
                self._outline_of(card_id)
                if card_id in self.positions:
                    return self
                return self.model_copy(update={"positions": {**self.positions, card_id: Point(x=x, y=y)}})
            case Resize(id=card_id, width=width):
                self._outline_of(card_id)
                return self.model_copy(update={"widths": {**self.widths, card_id: width}})
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

    def _outline_of(self, card_id: TCardId) -> Outline:
        """The outline of the card. ValueError, which lists the cards, if the board has no such card."""
        if card_id not in self.cards:
            cards = f"the cards are {', '.join(self.cards)}" if self.cards else "the board has no cards"
            raise ValueError(f"no card '{card_id}': {cards}")
        return outline_of(self.cards[card_id].md)

    def _check_version(self, card_id: TCardId, version: int) -> None:
        """ValueError unless the card is on the board with that number of earlier versions."""
        earlier = len(self.history.get(card_id, ()))
        if card_id not in self.cards:
            raise ValueError(f"card '{card_id}' is gone: it was removed after version {earlier}")
        if earlier != version:
            raise ValueError(f"card '{card_id}' changed: it has {earlier} earlier versions, not {version}")

    def _check_part(self, ref: TRef) -> None:
        """ValueError, which gives the range of parts, unless the ref names a card of the board or a part of it."""
        card_id, part, column = Ref.parse(ref)
        outline = self._outline_of(card_id)
        if column:
            raise ValueError(f"'{ref}' is a cell, not a part: {part_range(card_id, outline)}")
        if part and part not in outline:
            raise ValueError(f"no part '{ref}': {part_range(card_id, outline)}")

    def _input_of(self, ref: TRef) -> Column:
        """The input column of the cell. ValueError, which names the input columns, unless the ref names an input cell."""
        cell = Ref.parse(ref)
        outline = self._outline_of(cell.card)
        if not cell.column:
            raise ValueError(f"'{ref}' is not a cell: fill takes a card id, row and column such as {cell.card}/2/3")
        if cell.part not in outline:
            raise ValueError(f"no part '{cell.row}': {part_range(cell.card, outline)}")
        inputs = outline.rows.get(cell.part, {})
        match inputs.get(cell.column):
            case None if not inputs:
                raise ValueError(f"part '{cell.row}' is not a table row with input columns")
            case None:
                columns = ", ".join(column_label(n, found) for n, found in inputs.items())
                raise ValueError(f"no input '{ref}': the input columns of row '{cell.row}' are {columns}")
            case found:
                return found

    def _revise(self, card_id: TCardId, card: Card) -> "Board":
        """
        The board with the card in place of the one with its id, if there was one; the card keeps that one's author,
        and counts as edited when the other author put it.
        The feedback on the parts whose text is unchanged follows them, matched by text in order, as do the values
        whose column still takes them; the arrows at those parts and at the card itself stay. The rest of the feedback
        goes to the card's history with the card as it was.
        """
        if card_id not in self.cards:
            return self.model_copy(update={"cards": {**self.cards, card_id: card}})
        old = self.cards[card_id]
        card = card.model_copy(update={"author": old.author, "edited": card.author != old.author})
        after = outline_of(card.md)
        moved = {"": ""} if old.md == card.md else {}
        moved |= matched(outline_of(old.md), after)

        def follow(ref: TRef) -> TRef | None:
            """Where the feedback on a ref of the card goes: the ref of its part on the new card, if its text is there."""
            found = Ref.parse(ref)
            new_part = moved.get(found.part)
            return None if new_part is None else str(found._replace(part=new_part))

        def carried(ref: TRef) -> TRef | None:
            """Where an arrow's end goes: it stays on another card or on the card itself, and follows a part."""
            return ref if ref == card_id or card_of(ref) != card_id else follow(ref)

        threads: dict[TRef, Thread] = {}
        gone_threads: dict[TRef, Thread] = {}
        renamed: dict[TActionId, TRef] = {}
        for ref, thread in self.threads.items():
            if card_of(ref) != card_id:
                threads[ref] = thread
            elif (new := follow(ref)) is not None:
                threads[new] = thread.at(new)
                if new != ref:
                    renamed |= {said.id: new for said in thread.comments}
            else:
                gone_threads[ref] = thread
        values: dict[TRef, TValue] = {}
        gone_values: dict[TRef, TValue] = {}
        for ref, value in self.values.items():
            if card_of(ref) != card_id:
                values[ref] = value
            elif (new := follow(ref)) is not None and (column := after.input_at(Ref.parse(new))) and column.fits(value):
                values[new] = value
            else:
                gone_values[ref] = value
        arrows = {
            arrow_id: arrow.model_copy(update={"src": src, "dst": dst})
            for arrow_id, arrow in self.arrows.items()
            if (src := carried(arrow.src)) is not None and (dst := carried(arrow.dst)) is not None
        }
        version = Version(card=old, threads=gone_threads, values=gone_values)
        return self.model_copy(
            update={
                "cards": {**self.cards, card_id: card},
                "threads": threads,
                "values": values,
                "arrows": arrows,
                "messages": tuple(
                    said.model_copy(update={"ref": renamed[said.id]}) if said.id in renamed else said
                    for said in self.messages
                ),
                "history": {**self.history, card_id: (*self.history.get(card_id, ()), version)},
            }
        )

    def _retire(self, card_id: TCardId) -> "Board":
        """
        The board without the card, its place, its width, its threads and values and the arrows at it, with the card
        and its feedback at the end of its history.
        """
        on_card = {ref for ref in [*self.threads, *self.values] if card_of(ref) == card_id}
        version = Version(
            card=self.cards[card_id],
            threads={ref: thread for ref, thread in self.threads.items() if ref in on_card},
            values={ref: value for ref, value in self.values.items() if ref in on_card},
        )
        return self.model_copy(
            update={
                "cards": {k: v for k, v in self.cards.items() if k != card_id},
                "positions": {k: v for k, v in self.positions.items() if k != card_id},
                "widths": {k: v for k, v in self.widths.items() if k != card_id},
                "threads": {ref: thread for ref, thread in self.threads.items() if ref not in on_card},
                "values": {ref: value for ref, value in self.values.items() if ref not in on_card},
                "arrows": {
                    arrow_id: arrow
                    for arrow_id, arrow in self.arrows.items()
                    if card_id not in (card_of(arrow.src), card_of(arrow.dst))
                },
                "history": {**self.history, card_id: (*self.history.get(card_id, ()), version)},
            }
        )
