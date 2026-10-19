from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from agent_hud.primitives.base import (
    Author,
    BoxBase,
    CellValue,
    ElementBase,
    ElementKind,
    LabelOf,
    Part,
    PathError,
)


class ListItem(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    id: str
    author: Author
    text: str


class ListEl(BoxBase):
    kind: Literal[ElementKind.LIST] = ElementKind.LIST
    ordered: bool
    items: list[ListItem]

    def parts(self) -> list[Part]:
        items = (Part(item.id, str(n), item.text) for n, item in enumerate(self.items, start=1))
        return [Part("", "", self.title), *items]

    def _item(self, anchor: str) -> ListItem:
        item = next((item for item in self.items if item.id == anchor), None)
        if item is None:
            raise PathError(f"{self.id} has no item '{anchor}'")
        return item

    def set_value(self, anchor: str, value: CellValue) -> None:
        match value:
            case str() as text if text.strip():
                self._item(anchor).text = text.strip()
            case _:
                raise PathError(f"{self.label(anchor)} takes non-empty text")

    def insert(self, at: str, value: str, new_id: str, author: Author) -> None:
        if not value.strip():
            raise PathError("list items need text")
        match at:
            case "":
                position = len(self.items)
            case anchor:
                position = self.items.index(self._item(anchor))
        self.items.insert(position, ListItem(id=new_id, author=author, text=value.strip()))

    def remove(self, anchor: str) -> str:
        item = self._item(anchor)
        self.items.remove(item)
        return item.text

    def adopt(self, old: ElementBase) -> None:
        match old:
            case ListEl(items=old_items):
                by_text = {item.text: item for item in old_items}
            case _:
                return
        for item in self.items:
            if (kept := by_text.pop(item.text, None)) is not None:
                item.id, item.author = kept.id, kept.author

    def render(self, label_of: LabelOf) -> str:
        lines = [self.header(self.kind)]
        for n, item in enumerate(self.items, start=1):
            marker = f"{n}." if self.ordered else f"({n})"
            by = " (user)" if item.author == Author.USER else ""
            text = item.text.replace("\n", "\n   ")
            lines.append(f"{marker} {text}{by}{self.feedback_note(item.id)}")
        return "\n".join(lines)
