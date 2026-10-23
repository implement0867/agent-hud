from typing import assert_never

from pydantic import Field, ValidationError, field_validator

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
from agent_hud.outline import Outline


def one_line(error: ValidationError) -> str:
    """The messages of a validation error on one line, without pydantic's prefix and footer."""
    return ", ".join(str(detail["msg"]).removeprefix("Value error, ") for detail in error.errors())


def parts_of(card_id: TCardId, outline: Outline) -> str:
    """The range of the card's parts, for an error on a ref that is not one of them."""
    count = len(outline.texts)
    return f"card '{card_id}' has parts 1 to {count}" if count else f"card '{card_id}' has no parts"


def describe(label: str, column: Column) -> str:
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
        Outline(md)
        return md


class Said(Model):
    """A chat message, or a comment on the part that ref names."""

    id: TActionId
    author: Author
    text: TMessage
    ref: TRef | None = None


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

    def apply(self, action: Action) -> "Thread":
        match action.body:
            case React(reaction=reaction):
                return self.model_copy(update={"reactions": {**self.reactions, action.author: reaction}})
            case Unreact():
                return self.model_copy(
                    update={"reactions": {k: v for k, v in self.reactions.items() if k != action.author}}
                )
            case Comment(ref=ref, text=text):
                said = Said(id=action.id, author=action.author, text=text, ref=ref)
                return self.model_copy(update={"comments": (*self.comments, said)})
            case (
                Put()
                | Remove()
                | Restore()
                | Say()
                | Fill()
                | Link()
                | Unlink()
                | Move()
                | Resize()
                | Place()
                | Clear()
                | Send()
            ):
                raise ValueError(f"a thread does not take {action.body.kind}")
            case _:
                assert_never(action.body)

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
        return Outline(self.cards[card_id].md).texts

    def part_texts(self, body: TBody) -> dict[TRef, str]:
        """The text of each part that the action names, as the board has it now."""
        match body:
            case React(ref=ref) | Unreact(ref=ref) | Comment(ref=ref):
                refs = [ref]
            case Fill(ref=ref):
                refs = [ref.rpartition("/")[0]]
            case Link(src=src, dst=dst):
                refs = [src, dst]
            case _:
                refs = []
        return {ref: text for ref in refs if (text := self._text(ref)) is not None}

    def _text(self, ref: TRef) -> str | None:
        card_id, _, path = ref.partition("/")
        return self.texts_of(card_id).get(path) if card_id in self.cards else None

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
                self._check_card(card_id)
                cards = {k: v for k, v in self.cards.items() if k != card_id}
                positions = {k: v for k, v in self.positions.items() if k != card_id}
                widths = {k: v for k, v in self.widths.items() if k != card_id}
                return self._retire(card_id).model_copy(
                    update={"cards": cards, "positions": positions, "widths": widths}
                )
            case Comment(ref=ref):
                self._check_part(ref)
                thread = self.threads.get(ref, Thread()).apply(action)
                messages = (*self.messages, thread.comments[-1])
                return self.model_copy(update={"threads": {**self.threads, ref: thread}, "messages": messages})
            case React(ref=ref) | Unreact(ref=ref):
                self._check_part(ref)
                thread = self.threads.get(ref, Thread()).apply(action)
                return self.model_copy(update={"threads": {**self.threads, ref: thread}})
            case Fill(ref=ref, value=value):
                column = self._check_cell(ref)
                if not column.fits(value):
                    raise ValueError(f"input {describe(f"'{ref}'", column)} takes {column.takes}")
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
                self._check_card(card_id)
                return self.model_copy(update={"positions": {**self.positions, card_id: Point(x=x, y=y)}})
            case Resize(id=card_id, width=width):
                self._check_card(card_id)
                return self.model_copy(update={"widths": {**self.widths, card_id: width}})
            case Place(id=card_id, x=x, y=y):
                self._check_card(card_id)
                if card_id in self.positions:
                    return self
                return self.model_copy(update={"positions": {**self.positions, card_id: Point(x=x, y=y)}})
            case Say(text=text):
                said = Said(id=action.id, author=action.author, text=text)
                return self.model_copy(update={"messages": (*self.messages, said)})
            case Clear():
                retired = self
                for card_id in self.cards:
                    retired = retired._retire(card_id)
                return retired.model_copy(update={"cards": {}, "positions": {}, "widths": {}, "messages": ()})
            case Send():
                return self
            case _:
                assert_never(action.body)

    def _check_card(self, card_id: TCardId) -> Outline:
        """The outline of the card. ValueError, which lists the cards, if the board has no such card."""
        if card_id not in self.cards:
            cards = f"the cards are {', '.join(self.cards)}" if self.cards else "the board has no cards"
            raise ValueError(f"no card '{card_id}': {cards}")
        return Outline(self.cards[card_id].md)

    def _check_version(self, card_id: TCardId, version: int) -> None:
        """ValueError unless the card is on the board with that number of earlier versions."""
        earlier = len(self.history.get(card_id, ()))
        if card_id not in self.cards:
            raise ValueError(f"card '{card_id}' is gone: it was removed after version {earlier}")
        if earlier != version:
            raise ValueError(f"card '{card_id}' changed: it has {earlier} earlier versions, not {version}")

    def _check_part(self, ref: TRef) -> None:
        """ValueError, which gives the range of parts, unless the ref names a card of the board or a part of it."""
        card_id, _, path = ref.partition("/")
        outline = self._check_card(card_id)
        if "/" in path:
            raise ValueError(f"'{ref}' is a cell, not a part: {parts_of(card_id, outline)}")
        if path and path not in outline:
            raise ValueError(f"no part '{ref}': {parts_of(card_id, outline)}")

    def _check_cell(self, ref: TRef) -> Column:
        """The input column of the cell. ValueError, which names the input columns, unless the ref names an input cell."""
        card_id, _, path = ref.partition("/")
        row, _, column = path.partition("/")
        outline = self._check_card(card_id)
        if not column:
            raise ValueError(f"'{ref}' is not a cell: fill takes a card id, row and column such as {card_id}/2/3")
        if row not in outline:
            raise ValueError(f"no part '{card_id}/{row}': {parts_of(card_id, outline)}")
        inputs = {cell.partition("/")[2]: found for cell, found in outline.inputs.items() if cell.startswith(f"{row}/")}
        match inputs.get(column):
            case None if not inputs:
                raise ValueError(f"part '{card_id}/{row}' is not a table row with input columns")
            case None:
                columns = ", ".join(describe(n, found) for n, found in inputs.items())
                raise ValueError(f"no input '{ref}': the input columns of row '{card_id}/{row}' are {columns}")
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
        cards = {**self.cards, card_id: card}
        after = Outline(card.md)
        moved = {"": ""} if old.md == card.md else {}
        moved |= matched(Outline(old.md), after)

        def on_card(ref: TRef) -> bool:
            return ref.partition("/")[0] == card_id

        def follow(ref: TRef) -> TRef | None:
            """The ref of the part on the new card, if its text is there; the card itself, if its markdown is unchanged."""
            row, _, column = ref.partition("/")[2].partition("/")
            if (new_row := moved.get(row)) is None:
                return None
            return "/".join(part for part in (card_id, new_row, column) if part)

        threads: dict[TRef, Thread] = {}
        gone_threads: dict[TRef, Thread] = {}
        renamed: dict[TActionId, TRef] = {}
        for ref, thread in self.threads.items():
            if not on_card(ref):
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
            if not on_card(ref):
                values[ref] = value
            elif (
                (new := follow(ref)) is not None
                and (column := after.inputs.get(new.partition("/")[2]))
                and column.fits(value)
            ):
                values[new] = value
            else:
                gone_values[ref] = value
        arrows: dict[TCardId, Arrow] = {}
        for arrow_id, arrow in self.arrows.items():
            ends = [ref if ref == card_id or not on_card(ref) else follow(ref) for ref in (arrow.src, arrow.dst)]
            match ends:
                case [str() as src, str() as dst]:
                    arrows[arrow_id] = arrow.model_copy(update={"src": src, "dst": dst})
                case _:
                    pass
        version = Version(card=old, threads=gone_threads, values=gone_values)
        return self.model_copy(
            update={
                "cards": cards,
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
        """The board without the threads, values and arrows on the card, and with the card and its feedback in its history."""
        if card_id not in self.cards:
            return self
        on_card = {ref for ref in [*self.threads, *self.values] if ref.partition("/")[0] == card_id}
        version = Version(
            card=self.cards[card_id],
            threads={ref: thread for ref, thread in self.threads.items() if ref in on_card},
            values={ref: value for ref, value in self.values.items() if ref in on_card},
        )
        arrows = {
            arrow_id: arrow
            for arrow_id, arrow in self.arrows.items()
            if card_id not in (arrow.src.partition("/")[0], arrow.dst.partition("/")[0])
        }
        return self.model_copy(
            update={
                "threads": {ref: thread for ref, thread in self.threads.items() if ref not in on_card},
                "values": {ref: value for ref, value in self.values.items() if ref not in on_card},
                "arrows": arrows,
                "history": {**self.history, card_id: (*self.history.get(card_id, ()), version)},
            }
        )
