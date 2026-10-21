from hypothesis import strategies as st
from pydantic import TypeAdapter

from agent_hud.models.actions import Action, Author, Reaction, TBody, TCardId, TMessage
from tests.factories import comment, put, react, remove, say, unreact


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


def mds() -> st.SearchStrategy[str]:
    """Card markdown, often with a list, so that refs to list items fit some cards and not others."""
    lists = st.builds(list_md, st.sampled_from(["- ", "1. "]), st.lists(item_texts(), min_size=1, max_size=3))
    return st.one_of(st.text(min_size=1), lists)


def refs(ids: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
    return st.one_of(ids, st.builds("{}/{}".format, ids, st.integers(1, 4)))


def bodies(ids: st.SearchStrategy[str]) -> st.SearchStrategy[TBody]:
    return st.one_of(
        st.builds(put, ids, mds()),
        st.builds(remove, ids),
        st.builds(react, refs(ids), st.from_type(Reaction)),
        st.builds(unreact, refs(ids)),
        st.builds(comment, refs(ids), messages()),
        st.builds(say, messages()),
    )


def actions(ids: st.SearchStrategy[str]) -> st.SearchStrategy[Action]:
    return st.builds(Action, id=action_ids(), author=st.from_type(Author), body=bodies(ids))


def blanks() -> st.SearchStrategy[str]:
    """Text of space separators only, which the regex engines of Python, Rust and JavaScript all count as white space."""
    return st.text(st.characters(categories=["Zs"]))
