from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_hud.primitives.base import Author, BoxBase, CellValue, ElementBase, ElementKind, IdSource, PathError


class ListItem(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(description="Stable anchor key of the item", examples=["k4"])
    author: Author = Field(description="Who added the item", examples=[Author.AGENT])
    text: str = Field(description="Inline markdown; indented lines hold sub-points", examples=["Add a cache layer"])


class ListEl(BoxBase):
    """A numbered or bulleted list. Each item is its own anchor, labelled by position."""

    kind: Literal[ElementKind.LIST] = Field(
        default=ElementKind.LIST, description="Discriminator", examples=[ElementKind.LIST]
    )
    ordered: bool = Field(description="Numbered when true", examples=[True])
    items: list[ListItem] = Field(description="Items in display order", examples=[[]])

    def kind_name(self) -> str:
        return "list"

    def anchor_keys(self) -> list[str]:
        return ["", *(item.id for item in self.items)]

    def suffix(self, anchor: str) -> str | None:
        if anchor == "":
            return ""
        return next((str(n) for n, item in enumerate(self.items, start=1) if item.id == anchor), None)

    def _index(self, suffix: str, *, allow_end: bool = False) -> int:
        limit = len(self.items) + (1 if allow_end else 0)
        if not suffix.isdigit() or not 1 <= int(suffix) <= limit:
            raise PathError(f"{self.id} has items 1..{len(self.items)}, not '{suffix}'")
        return int(suffix) - 1

    def resolve(self, suffix: str) -> str:
        return "" if suffix == "" else self.items[self._index(suffix)].id

    def _item(self, anchor: str) -> ListItem:
        item = next((item for item in self.items if item.id == anchor), None)
        if item is None:
            raise PathError(f"{self.id} has no item '{anchor}'")
        return item

    def anchor_text(self, anchor: str) -> str | None:
        return next((item.text for item in self.items if item.id == anchor), None)

    def set_value(self, anchor: str, value: CellValue) -> None:
        match value:
            case str() as text if text.strip():
                self._item(anchor).text = text.strip()
            case _:
                raise PathError(f"{self.label(anchor) or self.id} takes non-empty text")

    def insert(self, at: str, value: str, ids: IdSource, author: Author) -> str:
        if not value.strip():
            raise PathError("list items need text")
        position = len(self.items) if at == "" else self._index(at, allow_end=True)
        item = ListItem(id=ids("k"), author=author, text=value.strip())
        self.items.insert(position, item)
        return item.id

    def remove(self, anchor: str) -> str:
        item = self._item(anchor)
        self.items.remove(item)
        return item.text

    def adopt(self, old: ElementBase) -> None:
        """Keep anchors and feedback of items whose text survives a re-put."""
        match old:
            case ListEl(items=old_items):
                pass
            case _:
                return
        by_text = {item.text: item for item in old_items}
        for item in self.items:
            if (kept := by_text.pop(item.text, None)) is not None:
                item.id, item.author = kept.id, kept.author

    def render(self) -> str:
        lines = [self.header()]
        for n, item in enumerate(self.items, start=1):
            marker = f"{n}." if self.ordered else f"({n})"
            by = " (user)" if item.author == Author.USER else ""
            text = item.text.replace("\n", "\n   ")
            lines.append(f"{marker} {text}{by}{self.feedback_note(item.id)}")
        return "\n".join(lines)
