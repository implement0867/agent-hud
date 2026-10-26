from hypothesis import strategies as st
from pydantic import TypeAdapter

from agent_hud.models.actions import Action, Author, TAgentBody, TBody, TCardId, TMessage
from tests.factories import (
    clear,
    comment,
    link,
    move,
    place,
    put,
    remove,
    resize,
    restore,
    say,
    send,
    unlink,
)


def card_ids() -> st.SearchStrategy[str]:
    return st.from_regex(TypeAdapter(TCardId).json_schema()["pattern"], fullmatch=True)


def action_ids() -> st.SearchStrategy[str]:
    return st.uuids().map(lambda uuid: uuid.hex)


def messages() -> st.SearchStrategy[str]:
    return st.from_regex(TypeAdapter(TMessage).json_schema()["pattern"])


def item_texts() -> st.SearchStrategy[str]:
    """Words that markdown reads as plain text."""
    return st.from_regex(r"[A-Za-z]([A-Za-z0-9 ]*[A-Za-z0-9])?", fullmatch=True)


def list_md(marker: str, texts: list[str]) -> str:
    return "\n".join(f"{marker}{text}" for text in texts)


def table_md(rows: list[list[str]]) -> str:
    """A table with a header row of the width of the first row."""
    width = len(rows[0])
    lines = [[f"h{n}" for n in range(width)], ["---"] * width, *rows]
    return "\n".join("| " + " | ".join(cells) + " |" for cells in lines)


def tables() -> st.SearchStrategy[list[list[str]]]:
    """Rows of one width, of words that markdown reads as plain text."""
    return st.integers(1, 3).flatmap(
        lambda width: st.lists(st.lists(item_texts(), min_size=width, max_size=width), min_size=1)
    )


def mds() -> st.SearchStrategy[str]:
    """Card markdown, often with a list of words, so that quotes of those words fit some cards and not others."""
    lists = st.builds(list_md, st.sampled_from(["- ", "1. "]), st.lists(item_texts(), min_size=1, max_size=3))
    return st.one_of(st.text(st.characters(codec="utf-8"), min_size=1), lists, st.builds(table_md, tables()))


def quotes() -> st.SearchStrategy[str]:
    """Words that a card may show, the card as a whole, or words that no card shows."""
    return st.one_of(st.just(""), item_texts(), st.just("nowhere at all"))


def occurrences() -> st.SearchStrategy[int | None]:
    return st.one_of(st.none(), st.integers(0, 2))


def coordinates() -> st.SearchStrategy[float]:
    return st.floats(allow_nan=False, allow_infinity=False)


def widths() -> st.SearchStrategy[float]:
    return st.floats(min_value=0, exclude_min=True, allow_infinity=False)


def sizes() -> st.SearchStrategy[tuple[float | None, float | None]]:
    """A width, a height or both."""
    return st.tuples(st.none() | widths(), st.none() | widths()).filter(lambda size: size != (None, None))


def agent_bodies(ids: st.SearchStrategy[str]) -> st.SearchStrategy[TAgentBody]:
    return st.one_of(
        st.builds(put, ids, mds()),
        st.builds(remove, ids),
        st.builds(restore, ids),
        st.builds(comment, ids, messages(), quotes(), occurrences()),
        st.builds(say, messages()),
        st.builds(link, ids, ids, ids, st.text(), quotes(), occurrences()),
        st.builds(unlink, ids),
        st.builds(move, ids, coordinates(), coordinates()),
        sizes().flatmap(lambda size: st.builds(resize, ids, st.just(size[0]), st.just(size[1]))),
        st.builds(clear),
    )


def bodies(ids: st.SearchStrategy[str]) -> st.SearchStrategy[TBody]:
    return st.one_of(agent_bodies(ids), st.builds(place, ids, coordinates(), coordinates()), st.builds(send))


def actions(ids: st.SearchStrategy[str]) -> st.SearchStrategy[Action]:
    return st.builds(Action, id=action_ids(), author=st.from_type(Author), body=bodies(ids))


def blanks() -> st.SearchStrategy[str]:
    """Text of space separators only, which the regex engines of Python, Rust and JavaScript all count as white space."""
    return st.text(st.characters(categories=["Zs"]))
