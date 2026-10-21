from hypothesis import strategies as st
from pydantic import TypeAdapter

from agent_hud.models.board import Board
from agent_hud.models.card import Card, Comment, Reaction, TCardId
from agent_hud.models.events import TMessage
from agent_hud.models.ops import TOp
from tests.factories import put, remove


def card_ids() -> st.SearchStrategy[str]:
    return st.from_regex(TypeAdapter(TCardId).json_schema()["pattern"], fullmatch=True)


def boards(ids: st.SearchStrategy[str]) -> st.SearchStrategy[Board]:
    return st.builds(
        Board,
        cards=st.dictionaries(
            ids,
            st.builds(
                Card,
                md=st.text(min_size=1),
                reaction=reactions(),
                comments=st.lists(st.builds(Comment, text=messages())),
            ),
        ),
    )


def reactions() -> st.SearchStrategy[Reaction | None]:
    return st.from_type(Reaction | None)


def ops(ids: st.SearchStrategy[str]) -> st.SearchStrategy[TOp]:
    return st.one_of(st.builds(put, ids, st.text(min_size=1)), st.builds(remove, ids))


def item_texts() -> st.SearchStrategy[str]:
    """Words that markdown reads as plain text."""
    return st.from_regex(r"[A-Za-z]([A-Za-z0-9 ]*[A-Za-z0-9])?", fullmatch=True)


def list_md(marker: str, texts: list[str]) -> str:
    return "\n".join(f"{marker}{text}" for text in texts)


def messages() -> st.SearchStrategy[str]:
    return st.from_regex(TypeAdapter(TMessage).json_schema()["pattern"])


def blanks() -> st.SearchStrategy[str]:
    """Text of space separators only, which the regex engines of Python, Rust and JavaScript all count as white space."""
    return st.text(st.characters(categories=["Zs"]))
