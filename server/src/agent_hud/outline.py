from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from agent_hud.models.columns import Column, ColumnKind


class Outline:
    """The parts of a markdown document the board can address: list items, table body rows and code lines by number in document order, and input cells as row/column."""

    def __init__(self, md: str) -> None:
        self.paths: set[str] = set()
        self.inputs: dict[str, Column] = {}
        columns: list[Column] = []
        for node in SyntaxTreeNode(MarkdownIt("commonmark").enable("table").parse(md)).walk():
            match node.type, node.parent:
                case "list_item", _:
                    self.paths.add(str(len(self.paths) + 1))
                case "tr", SyntaxTreeNode(type="thead"):
                    columns = [Column.from_header(cell.children[0].content) for cell in node.children]
                case "tr", SyntaxTreeNode(type="tbody"):
                    row = str(len(self.paths) + 1)
                    self.paths.add(row)
                    for n, column in enumerate(columns, start=1):
                        if column.kind is not ColumnKind.static:
                            self.inputs[f"{row}/{n}"] = column
                case "fence" | "code_block", _:
                    first = len(self.paths) + 1
                    lines = node.content.removesuffix("\n").count("\n") + 1
                    self.paths |= {str(n) for n in range(first, first + lines)}
                case _:
                    pass

    def __contains__(self, path: str) -> bool:
        return path in self.paths
