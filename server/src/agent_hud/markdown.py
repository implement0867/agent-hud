from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode


def list_item_count(md: str) -> int:
    return sum(node.type == "list_item" for node in SyntaxTreeNode(MarkdownIt("commonmark").parse(md)).walk())
