"""Canvas primitives.

To add a primitive: subclass `BoxBase` (or `TableBase` to extend tables), give it a
`kind` literal, add it to `Box`, and mirror its schema in `ui/src/protocol/schema.ts`.
"""

from functools import cache
from typing import Annotated

from pydantic import Discriminator, TypeAdapter

from agent_hud.markdown import ListContent, MarkdownError, TableContent, TextContent, parse
from agent_hud.primitives.base import Author, BoxKind, ElementKind, IdSource
from agent_hud.primitives.itable import ITableEl
from agent_hud.primitives.link import AnchorRef, LinkEl
from agent_hud.primitives.listing import ListEl, ListItem
from agent_hud.primitives.table import TableEl
from agent_hud.primitives.text import TextEl

type Box = TextEl | ListEl | TableEl | ITableEl
type Element = Annotated[TextEl | ListEl | TableEl | ITableEl | LinkEl, Discriminator("kind")]

__all__ = ["AnchorRef", "Box", "Element", "ITableEl", "LinkEl", "ListEl", "TableEl", "TextEl", "build_box", "elements"]


@cache
def elements() -> TypeAdapter[list[Element]]:
    return TypeAdapter(list[Element])


def build_box(*, id: str, md: str, title: str | None, kind: BoxKind | None, ids: IdSource, author: Author) -> Box:
    """Build a primitive from markdown, inferring the kind unless one is forced."""
    parsed = parse(md)
    heading = title if title is not None else parsed.title
    match kind, parsed.content:
        case BoxKind.TEXT, _:
            body = md.strip("\n") if title is not None or parsed.title is None else _body_without_title(md)
            return TextEl(kind=ElementKind.TEXT, id=id, author=author, title=heading, body=body)
        case None, TextContent(body=body):
            return TextEl(kind=ElementKind.TEXT, id=id, author=author, title=heading, body=body)
        case None | BoxKind.LIST, ListContent(ordered=ordered, items=items):
            listing = ListEl(kind=ElementKind.LIST, id=id, author=author, title=heading, ordered=ordered, items=[])
            listing.items = [ListItem(id=ids("k"), author=author, text=text) for text in items]
            return listing
        case BoxKind.TABLE, TableContent() as table:
            return TableEl.from_content(id=id, title=heading, content=table, ids=ids, author=author)
        case BoxKind.ITABLE, TableContent() as table:
            return ITableEl.from_content(id=id, title=heading, content=table, ids=ids, author=author)
        case None, TableContent() as table:
            cls = ITableEl if table.interactive else TableEl
            return cls.from_content(id=id, title=heading, content=table, ids=ids, author=author)
        case forced, _:
            raise MarkdownError(f"kind '{forced}' needs a markdown {'table' if forced != 'list' else 'list'}")


def _body_without_title(md: str) -> str:
    lines = md.strip("\n").splitlines()
    return "\n".join(lines[1:]).strip("\n")
