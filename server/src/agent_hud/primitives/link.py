from typing import Literal

from agent_hud.primitives.base import (
    AnchorRef,
    Author,
    CellValue,
    ElementBase,
    ElementKind,
    LabelOf,
    Part,
    PathError,
    quote,
)


class LinkEl(ElementBase):
    kind: Literal[ElementKind.LINK] = ElementKind.LINK
    src: AnchorRef
    dst: AnchorRef
    text: str | None = None

    def ends(self) -> tuple[AnchorRef, ...]:
        return (self.src, self.dst)

    def parts(self) -> list[Part]:
        return [Part("", "", self.text or "")]

    def set_value(self, anchor: str, value: CellValue) -> None:
        match anchor, value:
            case "", str() as text:
                self.text = text.strip() or None
            case "", None:
                self.text = None
            case _:
                raise PathError(f"{self.id} takes a label string")

    def render(self, label_of: LabelOf) -> str:
        src, dst = label_of(self.src), label_of(self.dst)
        ends = f"{src} -> {dst}" if src is not None and dst is not None else "(dangling)"
        text = f" {quote(self.text)}" if self.text else ""
        by = " by user" if self.author == Author.USER else ""
        return f"link {self.id} {ends}{text}{by}{self.feedback_note('')}"
