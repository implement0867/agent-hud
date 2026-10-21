import textwrap

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode


def _item_source(item: SyntaxTreeNode, lines: list[str]) -> str | None:
    """The item's own markdown: its first paragraph, then its other blocks dedented. None if it does not start with text."""
    match item.map, item.children:
        case (_, item_end), [SyntaxTreeNode(type="paragraph", map=(_, end)) as first, *_]:
            text = "".join(child.content for child in first.children).strip()
            tail = textwrap.dedent("\n".join(lines[end:item_end])).rstrip("\n")
            return f"{text}\n{tail}" if tail else text
        case _:
            return None


def numbered_items(md: str) -> list[str]:
    """The markdown of each item if md is one numbered list whose items each start with text, else none."""
    lines = md.splitlines()
    match SyntaxTreeNode(MarkdownIt("commonmark", {"html": False}).parse(md)).children:
        case [SyntaxTreeNode(type="ordered_list") as listing]:
            sources = [_item_source(item, lines) for item in listing.children]
            return [] if None in sources else [source for source in sources if source is not None]
        case _:
            return []
