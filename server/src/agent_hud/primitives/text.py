from typing import Literal

from pydantic import Field

from agent_hud.primitives.base import Author, BoxBase, CellValue, ElementKind, PathError


class TextEl(BoxBase):
    """A markdown block. The user can react to, comment on, or rewrite the whole body."""

    kind: Literal[ElementKind.TEXT] = Field(
        default=ElementKind.TEXT, description="Discriminator", examples=[ElementKind.TEXT]
    )
    body: str = Field(description="Markdown source", examples=["Caching moves to the edge."])

    def kind_name(self) -> str:
        return "note" if self.author == Author.USER else "text"

    def anchor_text(self, anchor: str) -> str | None:
        return self.body if anchor == "" else None

    def set_value(self, anchor: str, value: CellValue) -> None:
        match anchor, value:
            case "", str() as body:
                self.body = body
            case _:
                raise PathError(f"{self.id} takes a markdown string")

    def render(self) -> str:
        return f"{self.header()}\n{self.body}"
