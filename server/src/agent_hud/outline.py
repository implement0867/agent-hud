from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from agent_hud.models.columns import Column, ColumnKind


def fence_options(info: str) -> dict[str, str]:
    """The key=value words after the language of a fenced code block, such as file=src/app.py start=40."""
    return {key: value for word in info.split()[1:] for key, sep, value in [word.partition("=")] if sep}


class Outline:
    """
    The parts of a markdown document the board can address, and the text of each:
    headings, paragraphs outside list items, list items, table body rows and code lines by number in document order,
    and input cells as row/column. A code line's text starts with its file and line number when its block has a file option.
    """

    def __init__(self, md: str) -> None:
        self.texts: dict[str, str] = {}
        self.inputs: dict[str, Column] = {}
        columns: list[Column] = []
        for node in SyntaxTreeNode(MarkdownIt("commonmark").enable("table").parse(md)).walk():
            match node.type, node.parent:
                case "list_item", _:
                    self._add(next((child.content for child in node.walk() if child.type == "inline"), ""))
                case "heading", _:
                    self._add(node.children[0].content)
                case "paragraph", SyntaxTreeNode(type="list_item"):
                    pass
                case "paragraph", _:
                    self._add(node.children[0].content)
                case "tr", SyntaxTreeNode(type="thead"):
                    columns = [Column.from_header(cell.children[0].content) for cell in node.children]
                case "tr", SyntaxTreeNode(type="tbody"):
                    row = self._add(
                        " | ".join("".join(inline.content for inline in cell.children) for cell in node.children)
                    )
                    for n, column in enumerate(columns, start=1):
                        if column.kind is not ColumnKind.static:
                            self.inputs[f"{row}/{n}"] = column
                case "fence" | "code_block", _:
                    options = fence_options(node.info)
                    start = int(options.get("start", "1")) if options.get("start", "").isdigit() else 1
                    for n, line in enumerate(node.content.removesuffix("\n").split("\n"), start=start):
                        self._add(f"{options['file']}:{n}: {line}" if "file" in options else line)
                case _:
                    pass

    def _add(self, text: str) -> str:
        path = str(len(self.texts) + 1)
        self.texts[path] = text
        return path

    @property
    def paths(self) -> set[str]:
        return set(self.texts)

    def __contains__(self, path: str) -> bool:
        return path in self.texts
