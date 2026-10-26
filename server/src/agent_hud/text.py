import re
from functools import lru_cache

from markdown_it import MarkdownIt
from markdown_it.token import Token


def fence_options(info: str) -> dict[str, str]:
    """The key=value words after the language of a fenced code block, such as file=src/app.py start=40."""
    return {key: value for word in info.split()[1:] for key, sep, value in [word.partition("=")] if sep}


def squeeze(text: str) -> str:
    """
    The text without its white space. Quotes match the card's text in this form, so that the page's text and the
    server's agree where they join blocks, lines and cells in other ways.
    """
    return re.sub(r"\s+", "", text)


def inline_text(token: Token) -> str:
    """The text that an inline token shows: its text and code, without images and raw HTML."""
    return "".join(child.content for child in token.children or [] if child.type in {"text", "code_inline"})


@lru_cache(maxsize=256)
def text_of(md: str) -> str:
    """
    The text of the markdown as the page shows it: the text of each block, and each line of code, one per line.
    A task item's box and a table cell of a box alone, [ ] or [x], show as a checkbox, which has no text.
    """
    parser = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    lines: list[str] = []
    opened: list[str] = []
    for token in parser.parse(md):
        match token.type:
            case "inline":
                text = inline_text(token)
                match opened[-2:]:
                    case ["list_item_open", "paragraph_open"]:
                        text = re.sub(r"^\[[ xX]\](\s|$)", "", text)
                    case [*_, "td_open" | "th_open"] if re.fullmatch(r"\[[ xX]\]", text.strip()):
                        text = ""
                    case _:
                        pass
                lines.append(text)
            case "fence" | "code_block":
                lines.extend(token.content.removesuffix("\n").split("\n"))
            case kind if kind.endswith("_open"):
                opened.append(kind)
            case kind if kind.endswith("_close"):
                opened.pop()
            case _:
                pass
    return "\n".join(lines)


def places(md: str, quote: str) -> list[int]:
    """Where the quote starts in the card's text, squeezed, at each place it occurs; every place for an empty quote."""
    text, wanted = squeeze(text_of(md)), squeeze(quote)
    if not wanted:
        return [0]
    found: list[int] = []
    at = text.find(wanted)
    while at != -1:
        found.append(at)
        at = text.find(wanted, at + 1)
    return found
