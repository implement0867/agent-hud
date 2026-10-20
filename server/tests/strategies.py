from hypothesis import strategies as st
from pydantic import TypeAdapter

from agent_hud.models.board import Board
from agent_hud.models.card import Card, CardId
from agent_hud.models.ops import Op
from tests.factories import put, remove


def card_ids() -> st.SearchStrategy[str]:
    return st.from_regex(TypeAdapter(CardId).json_schema()["pattern"], fullmatch=True)


def boards(ids: st.SearchStrategy[str]) -> st.SearchStrategy[Board]:
    return st.builds(Board, cards=st.dictionaries(ids, st.builds(Card, md=st.text(min_size=1))))


def ops(ids: st.SearchStrategy[str]) -> st.SearchStrategy[Op]:
    return st.one_of(st.builds(put, ids, st.text(min_size=1)), st.builds(remove, ids))
