from collections.abc import Callable
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_hud.primitives.base import Author, CellValue, ElementBase, ElementId, ElementKind, PathError, quote


class AnchorRef(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    id: ElementId = Field(description="Element id", examples=["plan"])
    anchor: str = Field(description="Anchor key inside the element; empty for the element", examples=["k4"])


class LinkEl(ElementBase):
    """An arrow from one anchor to another, such as `plan.6 -> plan.1 "entails"`."""

    kind: Literal[ElementKind.LINK] = Field(
        default=ElementKind.LINK, description="Discriminator", examples=[ElementKind.LINK]
    )
    src: AnchorRef = Field(description="Arrow tail", examples=[{"id": "plan", "anchor": "k6"}])
    dst: AnchorRef = Field(description="Arrow head", examples=[{"id": "plan", "anchor": "k1"}])
    text: str | None = Field(default=None, description="Text on the arrow", examples=["entails?"])

    def ends(self) -> tuple[AnchorRef, ...]:
        return (self.src, self.dst)

    def anchor_text(self, anchor: str) -> str | None:
        return self.text if anchor == "" else None

    def set_value(self, anchor: str, value: CellValue) -> None:
        match anchor, value:
            case "", str() as text:
                self.text = text.strip() or None
            case "", None:
                self.text = None
            case _:
                raise PathError(f"{self.id} takes a label string")

    def describe(self, label_of: Callable[[AnchorRef], str | None]) -> str | None:
        """`l3 plan.6 -> plan.1 "entails?"`, or None when an end is gone."""
        src, dst = label_of(self.src), label_of(self.dst)
        if src is None or dst is None:
            return None
        note = f" {quote(self.text)}" if self.text else ""
        return f"{self.id} {src} -> {dst}{note}"

    def render_with(self, label_of: Callable[[AnchorRef], str | None]) -> str:
        by = " by user" if self.author == Author.USER else ""
        return f"link {self.describe(label_of) or self.id + ' (dangling)'}{by}{self.feedback_note('')}"

    def render(self) -> str:
        return f"link {self.id}"
