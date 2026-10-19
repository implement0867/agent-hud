from typing import Annotated, Literal

from pydantic import Discriminator

from agent_hud.markdown import ListContent, MarkdownError, TableContent, TextContent, parse
from agent_hud.primitives.base import AnchorRef, Author, ElementKind, IdSource
from agent_hud.primitives.link import LinkEl
from agent_hud.primitives.listing import ListEl, ListItem
from agent_hud.primitives.table import TableEl
from agent_hud.primitives.text import TextEl

type Box = TextEl | ListEl | TableEl
type BoxKind = Literal[ElementKind.TEXT, ElementKind.LIST, ElementKind.TABLE]
type Element = Annotated[TextEl | ListEl | TableEl | LinkEl, Discriminator("kind")]

__all__ = ["AnchorRef", "Box", "BoxKind", "Element", "LinkEl", "ListEl", "TableEl", "TextEl", "build_box"]


def build_box(*, id: str, md: str, title: str | None, kind: BoxKind | None, ids: IdSource, author: Author) -> Box:
    """Build a card from markdown, inferring the kind unless one is given."""
    parsed = parse(md, heading_is_title=title is None)
    heading = parsed.title if title is None else title
    match kind, parsed.content:
        case (ElementKind.TEXT, _) | (None, TextContent()):
            return TextEl(id=id, author=author, title=heading, body=parsed.body)
        case (ElementKind.LIST | None, ListContent(ordered=ordered, items=items)):
            entries = [ListItem(id=ids("k"), author=author, text=text) for text in items]
            return ListEl(id=id, author=author, title=heading, ordered=ordered, items=entries)
        case (ElementKind.TABLE | None, TableContent() as table):
            return TableEl.from_content(id=id, title=heading, content=table, ids=ids, author=author)
        case forced, _:
            raise MarkdownError(f"kind '{forced}' needs a markdown {forced}")
