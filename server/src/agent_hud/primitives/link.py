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
    text: str = ""

    def ends(self) -> tuple[AnchorRef, ...]:
        return (self.src, self.dst)

    def parts(self) -> list[Part]:
        return [Part("", "", self.text)]

    def set_value(self, anchor: str, value: CellValue) -> None:
        match anchor, value:
            case "", str() as text:
                self.text = text.strip()
            case _:
                raise PathError(f"{self.id} takes a label string")

    def render(self, label_of: LabelOf) -> str:
        text = f" {quote(self.text)}" if self.text else ""
        by = " by user" if self.author == Author.USER else ""
        return f"link {self.id} {label_of(self.src)} -> {label_of(self.dst)}{text}{by}{self.feedback_note('')}"
