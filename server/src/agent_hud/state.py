from dataclasses import dataclass, field
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from agent_hud.changes import Change, ChangeKind
from agent_hud.primitives import AnchorRef, Box, Element, LinkEl
from agent_hud.primitives.base import PathError


@dataclass(slots=True)
class Delta:
    """What a mutation changed, for publishing to the canvas tabs."""

    upserted: list[str] = field(default_factory=list)
    gone: list[str] = field(default_factory=list)
    submitted: bool = False


class BoardState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    elements: dict[str, Element] = Field(default_factory=dict)
    changes: list[Change] = Field(default_factory=list)
    """User actions, read by the agent as a delta."""
    seq: int = 0
    next_id: int = 0
    cursor: int = 0
    """The last change the agent has read."""

    def new_id(self, prefix: str) -> str:
        while True:
            self.next_id += 1
            if (candidate := f"{prefix}{self.next_id}") not in self.elements:
                return candidate

    def log(self, kind: ChangeKind, el_id: str = "", anchor: str = "", *, label: str = "", text: str = "") -> int:
        self.seq += 1
        self.changes.append(Change(seq=self.seq, kind=kind, id=el_id, anchor=anchor, label=label, text=text))
        return self.seq

    @property
    def pending(self) -> int:
        return sum(1 for c in self.changes if c.seq > self.cursor)

    def unread_submit(self) -> bool:
        return any(c.kind == ChangeKind.SUBMIT and c.seq > self.cursor for c in self.changes)

    def label_of(self, ref: AnchorRef) -> str:
        return self.find(ref.id).label(ref.anchor)

    def exists(self, ref: AnchorRef) -> bool:
        return ref.id in self.elements and self.elements[ref.id].has(ref.anchor)

    def find(self, el_id: str) -> Element:
        if (el := self.elements.get(el_id)) is None:
            raise PathError(f"no element '{el_id}' (ids: {', '.join(self.elements) or 'none'})")
        return el

    def box(self, el_id: str) -> Box:
        match self.find(el_id):
            case LinkEl():
                raise PathError(f"{el_id} is a link")
            case box:
                return box

    def resolve(self, label: str) -> tuple[Element, str]:
        el_id, _, suffix = label.partition(".")
        el = self.find(el_id)
        return el, el.resolve(suffix)

    def drop_dangling(self) -> list[str]:
        """Remove elements, such as links, whose ends are gone."""
        dead = [el.id for el in self.elements.values() if not all(self.exists(ref) for ref in el.ends())]
        for el_id in dead:
            del self.elements[el_id]
        return dead
