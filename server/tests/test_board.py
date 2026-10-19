from typing import assert_never

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter

from agent_hud.models.board import Board
from agent_hud.models.card import Card, CardId
from agent_hud.models.ops import Op, PutOp, RemoveOp
from tests.factories import put, remove


@st.composite
def boards_and_ops(draw: st.DrawFn) -> tuple[Board, list[Op]]:
    """A board and ops that share one pool of generated ids, so that ops hit cards that exist and cards that do not."""
    pool = draw(st.lists(st.from_regex(TypeAdapter(CardId).json_schema()["pattern"], fullmatch=True), min_size=1))
    ids = st.sampled_from(pool)
    mds = st.text(min_size=1)
    board = Board(cards=draw(st.dictionaries(ids, st.builds(Card, md=mds))))
    ops = draw(st.lists(st.one_of(st.builds(put, ids, mds), st.builds(remove, ids))))
    return board, ops


def dict_semantics(cards: dict[str, Card], ops: list[Op]) -> dict[str, Card]:
    """The cards after the ops by dict assignment and deletion; KeyError for a missing card."""
    result = dict(cards)
    for op in ops:
        match op:
            case PutOp(id=card_id, md=md):
                result[card_id] = Card(md=md)
            case RemoveOp(id=card_id):
                del result[card_id]
            case _:
                assert_never(op)
    return result


@given(boards_and_ops())
def test_apply_follows_dict_semantics_all_or_nothing(case: tuple[Board, list[Op]]) -> None:
    """Assemble: any board, and any ops on its ids and on other ids.
    Act: apply the ops.
    Assert: the cards equal dict semantics, or, when a remove misses, ValueError and the board is unchanged."""
    board, ops = case
    before = board.model_copy(deep=True)
    try:
        expected = dict_semantics(board.cards, ops)
    except KeyError:
        with pytest.raises(ValueError):
            board.apply(ops)
        assert board == before, "a failed apply must not change the board"
    else:
        board.apply(ops)
        assert board.cards == expected
