"""Shared vocabulary for canvas primitives.

Every primitive is a Pydantic model with a `kind` discriminator. A primitive exposes
*anchors*: stable keys for the parts a user can react to or comment on (a list item,
a table row, a cell). Anchors keep their key when items move, while the agent sees
positional *labels* (`plan.3`, `opts.r2.pick`) that are cheap to read and write.
"""

from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Author(StrEnum):
    AGENT = "agent"
    USER = "user"


class Reaction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    QUESTION = "question"


class BoxKind(StrEnum):
    """Element kinds that occupy a card; the agent may force one on `put`."""

    TEXT = "text"
    LIST = "list"
    TABLE = "table"
    ITABLE = "itable"


class ElementKind(StrEnum):
    TEXT = "text"
    LIST = "list"
    TABLE = "table"
    ITABLE = "itable"
    LINK = "link"


type ElementId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]
type CellValue = str | float | bool | None
type IdSource = Callable[[str], str]
"""Returns a fresh board-unique id that starts with the given prefix."""


class AnchorRefLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def anchor(self) -> str: ...


class PathError(ValueError):
    """A label or anchor does not name a part of the element."""


def quote(text: str, limit: int | None = None) -> str:
    """Quote text for the agent on one line, optionally truncated."""
    flat = " / ".join(line.strip() for line in text.strip().splitlines() if line.strip())
    if limit is not None and len(flat) > limit:
        flat = flat[: limit - 1] + "…"
    return '"' + flat.replace('"', "'") + '"'


class Comment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    id: str = Field(description="Board-unique comment id", examples=["c12"])
    author: Author = Field(description="Who wrote the comment", examples=[Author.USER])
    text: str = Field(min_length=1, description="Comment body", examples=["Wording is unclear"])
    seq: int = Field(ge=0, description="Board change sequence when posted", examples=[7])


class Feedback(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    reaction: Reaction | None = Field(
        default=None, description="User verdict on the anchor", examples=[Reaction.APPROVE]
    )
    revised: bool = Field(
        default=False,
        description="The agent changed the anchor content after the user reacted or commented",
        examples=[True],
    )
    comments: list[Comment] = Field(
        default_factory=list, description="Thread on the anchor, oldest first", examples=[[]]
    )

    def is_empty(self) -> bool:
        return self.reaction is None and not self.comments

    def render(self) -> str:
        parts = [self.reaction] if self.reaction else []
        parts += [quote(c.text) if c.author == Author.USER else f"agent {quote(c.text)}" for c in self.comments]
        if self.revised:
            parts.append("revised")
        return "; ".join(parts)


class ElementBase(BaseModel):
    """Behaviour every element shares. Primitives override the anchor and mutation hooks."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    id: ElementId = Field(description="Board-unique element id", examples=["plan"])
    author: Author = Field(description="Who created the element", examples=[Author.AGENT])
    feedback: dict[str, Feedback] = Field(
        default_factory=dict,
        description="Feedback keyed by anchor; the empty key is the whole element",
        examples=[{"": {"reaction": "approve", "revised": False, "comments": []}}],
    )

    # -- anchors -----------------------------------------------------------------------------

    def anchor_keys(self) -> list[str]:
        """All anchors in display order. The empty anchor is the element itself."""
        return [""]

    def suffix(self, anchor: str) -> str | None:
        """Agent-facing label suffix for an anchor, or None when the anchor no longer exists."""
        return "" if anchor == "" else None

    def resolve(self, suffix: str) -> str:
        """Anchor key for an agent-facing label suffix."""
        if suffix == "":
            return ""
        raise PathError(f"{self.id} has no part '{suffix}'")

    def label(self, anchor: str) -> str | None:
        match self.suffix(anchor):
            case None:
                return None
            case "":
                return self.id
            case suffix:
                return f"{self.id}.{suffix}"

    def anchor_text(self, anchor: str) -> str | None:
        """Current text content at the anchor, used in reports."""
        return None

    def value_text(self, anchor: str) -> str:
        """Current value at the anchor as the agent reads it after a user edit."""
        return quote(self.anchor_text(anchor) or "")

    def ends(self) -> tuple[AnchorRefLike, ...]:
        """Anchors this element points at; an element whose ends vanish is removed."""
        return ()

    # -- mutations ---------------------------------------------------------------------------

    def set_value(self, anchor: str, value: CellValue) -> None:
        raise PathError(f"{self.label(anchor) or self.id} cannot be set")

    def insert(self, at: str, value: str, ids: IdSource, author: Author) -> str:
        """Insert before the part at label suffix `at` (append when empty). Returns the new anchor."""
        raise PathError(f"{self.id} does not take inserts")

    def remove(self, anchor: str) -> str:
        """Remove a part. Returns its text for the change log."""
        raise PathError(f"{self.label(anchor) or self.id} cannot be removed")

    # -- feedback ----------------------------------------------------------------------------

    def feedback_at(self, anchor: str) -> Feedback:
        if anchor not in self.anchor_keys():
            raise PathError(f"{self.id} has no anchor '{anchor}'")
        return self.feedback.setdefault(anchor, Feedback())

    def mark_revised(self, anchor: str) -> None:
        if (fb := self.feedback.get(anchor)) is not None and not fb.is_empty():
            fb.revised = True

    def prune_feedback(self) -> None:
        """Drop feedback whose anchor is gone or that holds nothing."""
        live = set(self.anchor_keys())
        self.feedback = {k: v for k, v in self.feedback.items() if k in live and not v.is_empty()}

    def feedback_note(self, anchor: str) -> str:
        fb = self.feedback.get(anchor)
        return f"  [{fb.render()}]" if fb is not None and not fb.is_empty() else ""

    # -- rendering ---------------------------------------------------------------------------

    def render(self) -> str:
        """Full state for the agent, feedback inline."""
        raise NotImplementedError


class BoxBase(ElementBase):
    """An element that occupies a box on the canvas."""

    title: str | None = Field(default=None, description="Card heading", examples=["Plan"])
    x: float | None = Field(default=None, description="Left edge in canvas units; null until placed", examples=[40.0])
    y: float | None = Field(default=None, description="Top edge in canvas units; null until placed", examples=[40.0])
    w: float | None = Field(
        default=None, gt=0, description="Width set by the user; null for automatic", examples=[420.0]
    )

    def header(self) -> str:
        title = f" {quote(self.title)}" if self.title else ""
        by = " by user" if self.author == Author.USER else ""
        return f"{self.id}: {self.kind_name()}{title}{by}{self.feedback_note('')}"

    def kind_name(self) -> str:
        raise NotImplementedError

    def succeed(self, old: ElementBase) -> None:
        """Take over the position, anchors and feedback of the element this one replaces."""
        match old:
            case BoxBase(x=x, y=y, w=w):
                self.x, self.y, self.w = x, y, w
            case _:
                pass
        if type(old) is not type(self):
            return
        before = {anchor: old.anchor_text(anchor) for anchor in old.anchor_keys()}
        self.adopt(old)
        self.feedback.clear()
        self.feedback.update({k: v.model_copy(deep=True) for k, v in old.feedback.items()})
        for anchor, text in before.items():
            if anchor in self.anchor_keys() and self.anchor_text(anchor) != text:
                self.mark_revised(anchor)

    def adopt(self, old: ElementBase) -> None:
        """Carry anchor keys over from a replaced element of the same kind."""
