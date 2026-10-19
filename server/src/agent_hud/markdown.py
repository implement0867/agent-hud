"""Turn the markdown an agent writes into primitive content.

Parsing is markdown-it-py (CommonMark plus GFM tables). A body that is one list becomes a
list primitive, one table becomes a table, and anything else stays markdown text. A leading
heading becomes the card title. Column headers may carry a type in braces to make a table
interactive; that annotation is agent-hud syntax, not markdown:

    | Option | Pick {check} | Effort {low,med,high} | Notes {text} | Cost {number} |
"""

import re
import textwrap
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache

from markdown_it import MarkdownIt
from markdown_it.rules_block.table import escapedSplit
from markdown_it.tree import SyntaxTreeNode


class ColumnType(StrEnum):
    STATIC = "static"
    TEXT = "text"
    CHECK = "check"
    NUMBER = "number"
    SELECT = "select"


class MarkdownError(ValueError):
    """The markdown does not fit the requested primitive."""


@dataclass(frozen=True, slots=True)
class TextContent:
    body: str


@dataclass(frozen=True, slots=True)
class ListContent:
    ordered: bool
    items: list[str]


@dataclass(frozen=True, slots=True)
class HeaderSpec:
    title: str
    type: ColumnType = ColumnType.STATIC
    options: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TableContent:
    headers: list[HeaderSpec]
    rows: list[list[str]]

    @property
    def interactive(self) -> bool:
        return any(h.type != ColumnType.STATIC for h in self.headers)


type Content = TextContent | ListContent | TableContent


@dataclass(frozen=True, slots=True)
class Parsed:
    title: str | None
    content: Content


@cache
def _parser() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False}).enable("table")


def split_row(line: str) -> list[str]:
    """Cells of one table row, split the way the GFM table rule splits them (`\\|` escapes)."""
    cells = escapedSplit(line.strip())
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return [cell.strip() for cell in cells]


def parse_header(cell: str) -> HeaderSpec:
    match re.fullmatch(r"(.*?)\s*\{([^{}]*)\}", cell.strip()):
        case None:
            return HeaderSpec(title=cell.strip())
        case m:
            title, spec = m.group(1).strip(), m.group(2).strip()
    match spec.lower():
        case ColumnType.TEXT | ColumnType.CHECK | ColumnType.NUMBER as known:
            return HeaderSpec(title=title, type=ColumnType(known))
        case _:
            options = [o.strip() for o in spec.split(",") if o.strip()]
            if len(options) < 2:
                raise MarkdownError(f"column '{title}': type must be text, check, number or a list like {{a,b}}")
            return HeaderSpec(title=title, type=ColumnType.SELECT, options=options)


def _inline(node: SyntaxTreeNode) -> str:
    """Raw markdown of a block's inline content, such as a heading or a table cell."""
    return "".join(child.content for child in node.children if child.type == "inline").strip()


def _span(node: SyntaxTreeNode, lines: list[str]) -> list[str]:
    start, end = node.map or (0, 0)
    return lines[start:end]


def _item_source(item: SyntaxTreeNode, lines: list[str]) -> str:
    """An item's own markdown: the marker removed, sub-points kept and dedented."""
    first, *rest = _span(item, lines) or [""]
    head = re.sub(r"^\s*(?:[-*+]|\d{1,9}[.)])[ \t]?", "", first, count=1)
    tail = textwrap.dedent("\n".join(rest)).strip("\n")
    return f"{head}\n{tail}".strip() if tail else head.strip()


def _table(node: SyntaxTreeNode, lines: list[str]) -> TableContent:
    sections = {child.type: child for child in node.children}
    header_row = sections["thead"].children[0]
    headers = [parse_header(_inline(cell)) for cell in header_row.children]
    rows: list[list[str]] = []
    body = sections.get("tbody")
    for n, row in enumerate(body.children if body is not None else [], start=1):
        # GFM drops surplus cells silently; the agent should hear about them.
        written = split_row(_span(row, lines)[0]) if row.map else []
        if len(written) > len(headers):
            raise MarkdownError(f"table row {n} has {len(written)} cells but the header has {len(headers)}")
        rows.append([_inline(cell) for cell in row.children])
    return TableContent(headers=headers, rows=rows)


def parse(md: str) -> Parsed:
    """Infer the primitive content of a markdown body."""
    lines = md.splitlines()
    blocks = SyntaxTreeNode(_parser().parse(md)).children
    title: str | None = None
    if len(blocks) > 1 and blocks[0].type == "heading":
        title, blocks = _inline(blocks[0]), blocks[1:]
    match blocks:
        case [node] if node.type in {"bullet_list", "ordered_list"}:
            items = [_item_source(item, lines) for item in node.children]
            return Parsed(title=title, content=ListContent(ordered=node.type == "ordered_list", items=items))
        case [node] if node.type == "table":
            return Parsed(title=title, content=_table(node, lines))
        case [first, *_] if title is not None and first.map is not None:
            return Parsed(title=title, content=TextContent(body="\n".join(lines[first.map[0] :]).strip("\n")))
        case _:
            return Parsed(title=None, content=TextContent(body=md.strip("\n")))
