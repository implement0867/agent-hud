from hypothesis import strategies as st
from pydantic import TypeAdapter

from agent_hud.models.actions import Action, Author, Reaction, TAgentBody, TBody, TCardId, TMessage, TValue
from tests.factories import clear, comment, fill, link, move, place, put, react, remove, say, send, unlink, unreact


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


def table_md(rows: list[list[str]], specs: list[str] | None = None) -> str:
    """A table with a header row of the width of the first row, whose columns take the specs in order, then none."""
    width = len(rows[0])
    headers = [f"h{spec}" for spec in [*(specs or []), *[""] * width][:width]]
    lines = [headers, ["---"] * width, *rows]
    return "\n".join("| " + " | ".join(cells) + " |" for cells in lines)


def tables() -> st.SearchStrategy[list[list[str]]]:
    """Rows of one width, of words that markdown reads as plain text."""
    return st.integers(1, 3).flatmap(
        lambda width: st.lists(st.lists(item_texts(), min_size=width, max_size=width), min_size=1)
    )


def mds() -> st.SearchStrategy[str]:
    """Card markdown, often with a list, so that refs to list items fit some cards and not others."""
    lists = st.builds(list_md, st.sampled_from(["- ", "1. "]), st.lists(item_texts(), min_size=1, max_size=3))
    tables_md = st.builds(
        table_md, tables(), st.lists(st.sampled_from(["", " {text}", " {number}", " {check}", " {a, b}"]))
    )
    return st.one_of(st.text(st.characters(codec="utf-8", exclude_characters="{"), min_size=1), lists, tables_md)


def refs(ids: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
    numbers = st.integers(1, 4)
    return st.one_of(ids, st.builds("{}/{}".format, ids, numbers), st.builds("{}/{}/{}".format, ids, numbers, numbers))


def values() -> st.SearchStrategy[TValue]:
    return st.one_of(
        st.text(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
        st.sampled_from(["a", "b"]),
    )


def coordinates() -> st.SearchStrategy[float]:
    return st.floats(allow_nan=False, allow_infinity=False)


def agent_bodies(ids: st.SearchStrategy[str]) -> st.SearchStrategy[TAgentBody]:
    return st.one_of(
        st.builds(put, ids, mds()),
        st.builds(remove, ids),
        st.builds(react, refs(ids), st.from_type(Reaction)),
        st.builds(unreact, refs(ids)),
        st.builds(comment, refs(ids), messages()),
        st.builds(say, messages()),
        st.builds(fill, refs(ids), values()),
        st.builds(link, ids, refs(ids), refs(ids)),
        st.builds(unlink, ids),
        st.builds(move, ids, coordinates(), coordinates()),
        st.builds(clear),
    )


def bodies(ids: st.SearchStrategy[str]) -> st.SearchStrategy[TBody]:
    return st.one_of(agent_bodies(ids), st.builds(place, ids, coordinates(), coordinates()), st.builds(send))


def actions(ids: st.SearchStrategy[str]) -> st.SearchStrategy[Action]:
    return st.builds(Action, id=action_ids(), author=st.from_type(Author), body=bodies(ids))


def blanks() -> st.SearchStrategy[str]:
    """Text of space separators only, which the regex engines of Python, Rust and JavaScript all count as white space."""
    return st.text(st.characters(categories=["Zs"]))
