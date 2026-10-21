from typing import assert_never

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.markdown import list_item_count
from agent_hud.models.board import Board
from agent_hud.models.card import Card, Item, Reaction
from agent_hud.models.ops import PutOp, RemoveOp, TOp
from tests.factories import put
from tests.strategies import boards, card_ids, item_texts, list_md, messages, ops, reactions


@st.composite
def boards_and_ops(draw: st.DrawFn) -> tuple[Board, list[TOp]]:
    """A board and ops that share one pool of generated ids, so that ops hit cards that exist and cards that do not."""
    ids = st.sampled_from(draw(st.lists(card_ids(), min_size=1)))
    return draw(boards(ids)), draw(st.lists(ops(ids)))


def dict_semantics(cards: dict[str, Card], ops: list[TOp]) -> dict[str, Card]:
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
def test_apply_follows_dict_semantics_all_or_nothing(case: tuple[Board, list[TOp]]) -> None:
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


@given(boards(card_ids()), card_ids(), st.text(min_size=1), reactions())
def test_react_sets_the_reaction_on_that_card_only(
    board: Board, card_id: str, md: str, reaction: Reaction | None
) -> None:
    """Assemble: any board with a card put on it.
    Act: react to the card.
    Assert: the card has the reaction, and the other cards are unchanged."""
    board.apply([put(card_id, md)])
    before = dict(board.cards)
    board.react(card_id, reaction)
    assert board.cards == {**before, card_id: Card(md=md, reaction=reaction)}


@given(boards(card_ids()), card_ids(), st.text(min_size=1), st.lists(messages(), min_size=1))
def test_comments_add_to_that_card_only_in_order(board: Board, card_id: str, md: str, texts: list[str]) -> None:
    """Assemble: any board with a card put on it.
    Act: comment on the card with each text.
    Assert: the card has the comments in order with distinct ids, and the other cards are unchanged."""
    board.apply([put(card_id, md)])
    before = dict(board.cards)
    for text in texts:
        board.comment(card_id, text)
    comments = board.cards[card_id].comments
    assert [comment.text for comment in comments] == texts
    assert len({comment.id for comment in comments}) == len(texts)
    assert {**board.cards, card_id: before[card_id]} == before


@given(boards(card_ids()), card_ids(), st.text(min_size=1), st.integers(min_value=1), reactions())
def test_react_to_item_sets_the_reaction_on_that_item_only(
    board: Board, card_id: str, md: str, number: int, reaction: Reaction | None
) -> None:
    """Assemble: any board with a card put on it.
    Act: react to one list item of the card.
    Assert: that item has the reaction, and the other cards are unchanged."""
    board.apply([put(card_id, md)])
    before = dict(board.cards)
    board.react_to_item(card_id, number, reaction)
    assert board.cards == {**before, card_id: Card(md=md, items={number: Item(reaction=reaction)})}


@given(boards(card_ids()), card_ids(), st.text(min_size=1), st.integers(min_value=1), st.lists(messages(), min_size=1))
def test_comments_on_an_item_add_to_that_item_only_in_order(
    board: Board, card_id: str, md: str, number: int, texts: list[str]
) -> None:
    """Assemble: any board with a card put on it.
    Act: comment on one list item of the card with each text.
    Assert: that item has the comments in order with distinct ids, and the other cards are unchanged."""
    board.apply([put(card_id, md)])
    before = dict(board.cards)
    for text in texts:
        board.comment_on_item(card_id, number, text)
    comments = board.cards[card_id].items[number].comments
    assert [comment.text for comment in comments] == texts
    assert len({comment.id for comment in comments}) == len(texts)
    assert board.cards == {**before, card_id: Card(md=md, items={number: Item(comments=comments)})}


@pytest.mark.parametrize("marker", ["- ", "1. "])
@given(st.lists(item_texts(), min_size=1))
def test_list_item_count_counts_each_item_of_a_list(marker: str, texts: list[str]) -> None:
    """Assemble: a bulleted or numbered list of texts.
    Act: count its list items.
    Assert: one per text."""
    assert list_item_count(list_md(marker, texts)) == len(texts)


@given(st.lists(item_texts(), min_size=1))
def test_list_item_count_of_lines_is_zero(texts: list[str]) -> None:
    """Assemble: lines of texts, which markdown reads as one paragraph.
    Act: count its list items.
    Assert: zero."""
    assert list_item_count(list_md("", texts)) == 0
