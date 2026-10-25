from functools import lru_cache

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from agent_hud.models.columns import Column, ColumnKind, Table
from agent_hud.models.refs import Ref


def fence_options(info: str) -> dict[str, str]:
    """The key=value words after the language of a fenced code block, such as file=src/app.py start=40."""
    return {key: value for word in info.split()[1:] for key, sep, value in [word.partition("=")] if sep}


class Outline:
    """
    The parts of a markdown document the board can address, and the text of each:
    headings, paragraphs outside list items, list items, table body rows and code lines by number in document order,
    and the input columns of each table body row. A code line's text starts with its file and line number when its block
    has a file option.
    """

    def __init__(self, md: str) -> None:
        self.texts: dict[str, str] = {}
        self.rows: dict[str, dict[str, Column]] = {}
        """The input columns of each table body row by column number, such as {"3": {"2": Column(...)}}."""
        self.tables: list[Table] = []
        """Each table, with the numbers of its body rows and its input columns."""
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
                    inputs = {
                        str(n): column
                        for n, column in enumerate(columns, start=1)
                        if column.kind is not ColumnKind.static
                    }
                    self.tables.append(Table(rows=[], columns=inputs))
                case "tr", SyntaxTreeNode(type="tbody"):
                    row = self._add(
                        " | ".join("".join(inline.content for inline in cell.children) for cell in node.children)
                    )
                    table = self.tables[-1]
                    self.rows[row] = table.columns
                    self.tables[-1] = table.model_copy(update={"rows": [*table.rows, row]})
                case "fence" | "code_block", _:
                    options = fence_options(node.info)
                    start = int(first) if (first := options.get("start", "")).isdigit() else 1
                    for n, line in enumerate(node.content.removesuffix("\n").split("\n"), start=start):
                        self._add(f"{options['file']}:{n}: {line}" if "file" in options else line)
                case _:
                    pass

    def _add(self, text: str) -> str:
        path = str(len(self.texts) + 1)
        self.texts[path] = text
        return path

    @property
    def inputs(self) -> dict[str, Column]:
        """Each input cell by row and column, such as 3/2."""
        return {f"{row}/{n}": column for row, columns in self.rows.items() for n, column in columns.items()}

    def input_at(self, cell: Ref) -> Column | None:
        """The input column of the cell, or None when the cell is not in an input column of a row."""
        return self.rows.get(cell.part, {}).get(cell.column)

    @property
    def paths(self) -> set[str]:
        return set(self.texts)

    def __contains__(self, path: str) -> bool:
        return path in self.texts


@lru_cache(maxsize=256)
def outline_of(md: str) -> Outline:
    """The outline of the markdown, parsed once for each text; callers read it and do not change it."""
    return Outline(md)
