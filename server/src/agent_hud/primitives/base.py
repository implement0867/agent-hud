from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Author(StrEnum):
    AGENT = "agent"
    USER = "user"


class Reaction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    QUESTION = "question"


class ElementKind(StrEnum):
    TEXT = "text"
    LIST = "list"
    TABLE = "table"
    LINK = "link"


type ElementId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]
type CellValue = str | float | bool | None
type IdSource = Callable[[str], str]


class PathError(ValueError):
    pass


def quote(text: str, limit: int | None = None) -> str:
    """One line in double quotes, optionally truncated."""
    flat = " / ".join(line.strip() for line in text.strip().splitlines() if line.strip())
    if limit is not None and len(flat) > limit:
        flat = flat[: limit - 1] + "…"
    return '"' + flat.replace('"', "'") + '"'


def cell_text(value: CellValue) -> str:
    match value:
        case None:
            return ""
        case bool() as flag:
            return "x" if flag else ""
        case int() | float() as number:
            return f"{number:g}"
        case str() as text:
            return text


class AnchorRef(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    id: ElementId
    anchor: str


type LabelOf = Callable[[AnchorRef], str | None]


class Comment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    id: str
    author: Author
    text: str = Field(min_length=1)
    seq: int = Field(ge=0)


class Feedback(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    reaction: Reaction | None = None
    revised: bool = False
    comments: list[Comment] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return self.reaction is None and not self.comments

    def render(self) -> str:
        parts = [self.reaction] if self.reaction else []
        parts += [quote(c.text) if c.author == Author.USER else f"agent {quote(c.text)}" for c in self.comments]
        if self.revised:
            parts.append("revised")
        return "; ".join(parts)


@dataclass(frozen=True, slots=True)
class Part:
    """An addressable part. `anchor` is stable; `label` is the positional name the agent uses."""

    anchor: str
    label: str
    text: str


class ElementBase(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    id: ElementId
    author: Author
    feedback: dict[str, Feedback] = Field(default_factory=dict)

    def parts(self) -> list[Part]:
        raise NotImplementedError

    def part(self, anchor: str) -> Part | None:
        return next((p for p in self.parts() if p.anchor == anchor), None)

    def resolve(self, label: str) -> str:
        part = next((p for p in self.parts() if p.label == label), None)
        if part is None:
            raise PathError(f"{self.id} has no part '{label}'")
        return part.anchor

    def label(self, anchor: str) -> str | None:
        match self.part(anchor):
            case None:
                return None
            case Part(label=""):
                return self.id
            case Part(label=label):
                return f"{self.id}.{label}"

    def ends(self) -> tuple[AnchorRef, ...]:
        return ()

    def set_value(self, anchor: str, value: CellValue) -> None:
        raise PathError(f"{self.label(anchor) or self.id} cannot be set")

    def insert(self, before: str | None, value: str, new_id: str, author: Author) -> None:
        """Insert before the part at anchor `before`, or append when it is None."""
        raise PathError(f"{self.id} does not take inserts")

    def remove(self, anchor: str) -> str:
        """Remove a part and return its text."""
        raise PathError(f"{self.label(anchor) or self.id} cannot be removed")

    def feedback_at(self, anchor: str) -> Feedback:
        if self.part(anchor) is None:
            raise PathError(f"{self.id} has no anchor '{anchor}'")
        return self.feedback.setdefault(anchor, Feedback())

    def mark_revised(self, anchor: str) -> None:
        if (fb := self.feedback.get(anchor)) is not None and not fb.is_empty():
            fb.revised = True

    def prune_feedback(self) -> None:
        live = {p.anchor for p in self.parts()}
        self.feedback = {k: v for k, v in self.feedback.items() if k in live and not v.is_empty()}

    def feedback_note(self, anchor: str) -> str:
        fb = self.feedback.get(anchor)
        return f"  [{fb.render()}]" if fb is not None and not fb.is_empty() else ""

    def render(self, label_of: LabelOf) -> str:
        raise NotImplementedError


class BoxBase(ElementBase):
    title: str | None = None
    x: float | None = None
    y: float | None = None
    w: float | None = Field(default=None, gt=0)

    def header(self, kind: ElementKind) -> str:
        title = f" {quote(self.title)}" if self.title else ""
        by = " by user" if self.author == Author.USER else ""
        return f"{self.id}: {kind}{title}{by}{self.feedback_note('')}"

    def succeed(self, old: ElementBase) -> None:
        """Take over the position, anchors and feedback of the element this one replaces."""
        match old:
            case BoxBase(x=x, y=y, w=w):
                self.x, self.y, self.w = x, y, w
            case _:
                pass
        if type(old) is not type(self):
            return
        before = {p.anchor: p.text for p in old.parts()}
        self.adopt(old)
        self.feedback.clear()
        self.feedback.update({k: v.model_copy(deep=True) for k, v in old.feedback.items()})
        for part in self.parts():
            if part.anchor in before and before[part.anchor] != part.text:
                self.mark_revised(part.anchor)

    def adopt(self, old: ElementBase) -> None:
        """Reuse the anchors of `old`, the element of the same kind this one replaces."""
