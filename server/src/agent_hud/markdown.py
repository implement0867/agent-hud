import re
import textwrap
from dataclasses import dataclass, field
from enum import StrEnum

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
    pass


@dataclass(frozen=True, slots=True)
class TextContent:
    pass


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


type Content = TextContent | ListContent | TableContent


@dataclass(frozen=True, slots=True)
class Parsed:
    title: str
    content: Content
    body: str
    """The markdown after the title heading."""


def split_row(line: str) -> list[str]:
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
    return "".join(child.content for child in node.children if child.type == "inline").strip()


def _span(node: SyntaxTreeNode, lines: list[str]) -> list[str]:
    match node.map:
        case (start, end):
            return lines[start:end]
        case None:
            raise MarkdownError(f"{node.type} has no source lines")


def _item_source(item: SyntaxTreeNode, lines: list[str]) -> str:
    """An item's own markdown: the marker removed, sub-points kept and dedented."""
    first, *rest = _span(item, lines)
    head = re.sub(r"^\s*(?:[-*+]|\d{1,9}[.)])[ \t]?", "", first, count=1)
    tail = textwrap.dedent("\n".join(rest)).strip("\n")
    return f"{head}\n{tail}".strip() if tail else head.strip()


def _table(node: SyntaxTreeNode, lines: list[str]) -> TableContent:
    sections = {child.type: child for child in node.children}
    header_row = sections["thead"].children[0]
    headers = [parse_header(_inline(cell)) for cell in header_row.children]
    rows: list[list[str]] = []
    body_rows = [row for section in node.children if section.type == "tbody" for row in section.children]
    for n, row in enumerate(body_rows, start=1):
        # GFM drops surplus cells silently; the agent should hear about them.
        written = split_row(_span(row, lines)[0])
        if len(written) > len(headers):
            raise MarkdownError(f"table row {n} has {len(written)} cells but the header has {len(headers)}")
        rows.append([_inline(cell) for cell in row.children])
    return TableContent(headers=headers, rows=rows)


def parse(md: str, *, heading_is_title: bool = True) -> Parsed:
    lines = md.splitlines()
    blocks = SyntaxTreeNode(MarkdownIt("commonmark", {"html": False}).enable("table").parse(md)).children
    title = ""
    body = md.strip("\n")
    match blocks:
        case [SyntaxTreeNode(type="heading") as heading, SyntaxTreeNode(map=(start, _)), *_] if heading_is_title:
            title, blocks = _inline(heading), blocks[1:]
            body = "\n".join(lines[start:]).strip("\n")
        case _:
            pass
    match blocks:
        case [node] if node.type in {"bullet_list", "ordered_list"}:
            items = [_item_source(item, lines) for item in node.children]
            return Parsed(title, ListContent(ordered=node.type == "ordered_list", items=items), body)
        case [node] if node.type == "table":
            return Parsed(title, _table(node, lines), body)
        case _:
            return Parsed(title, TextContent(), body)
