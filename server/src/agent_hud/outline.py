from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode


class Outline:
    """The paths of the parts of a markdown document that the board can address: each list item and table body row, by its number in document order."""

    def __init__(self, md: str) -> None:
        nodes = SyntaxTreeNode(MarkdownIt("commonmark").enable("table").parse(md)).walk()
        count = sum(
            node.type == "list_item" or (node.type == "tr" and node.parent is not None and node.parent.type == "tbody")
            for node in nodes
        )
        self.paths = frozenset(str(n) for n in range(1, count + 1))

    def __contains__(self, path: str) -> bool:
        return path in self.paths
