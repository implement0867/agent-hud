from typing import Literal

from agent_hud.primitives.base import Author, BoxBase, CellValue, ElementKind, LabelOf, Part, PathError, quote


class TextEl(BoxBase):
    kind: Literal[ElementKind.TEXT] = ElementKind.TEXT
    body: str

    def parts(self) -> list[Part]:
        return [Part("", "", self.body)]

    def set_value(self, anchor: str, value: CellValue) -> None:
        match anchor, value:
            case "", str() as body:
                self.body = body
            case _:
                raise PathError(f"{self.id} takes a markdown string")

    def render(self, label_of: LabelOf) -> str:
        if self.author == Author.USER:
            return f"{self.id}: note {quote(self.body)}{self.feedback_note('')}"
        return f"{self.header(self.kind)}\n{self.body}"
