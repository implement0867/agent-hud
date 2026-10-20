from typing import assert_never

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.models.board import Board
from agent_hud.models.card import Card
from agent_hud.models.ops import Op, PutOp, RemoveOp
from tests.strategies import boards, card_ids, ops


@st.composite
def boards_and_ops(draw: st.DrawFn) -> tuple[Board, list[Op]]:
    """A board and ops that share one pool of generated ids, so that ops hit cards that exist and cards that do not."""
    ids = st.sampled_from(draw(st.lists(card_ids(), min_size=1)))
    return draw(boards(ids)), draw(st.lists(ops(ids)))


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
