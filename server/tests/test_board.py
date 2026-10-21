from typing import assert_never

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.models.board import Board
from agent_hud.models.card import Card, Reaction
from agent_hud.models.ops import PutOp, RemoveOp, TOp
from tests.factories import put, without_item_ids
from tests.strategies import boards, card_ids, item_texts, messages, numbered_list, ops, reactions


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
                result[card_id] = Card.from_md(md)
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
        assert without_item_ids(board) == without_item_ids(Board(cards=expected))


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
    assert board.cards == {**before, card_id: before[card_id].model_copy(update={"reaction": reaction})}


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


@given(card_ids(), st.lists(item_texts(), min_size=1))
def test_a_card_of_one_numbered_list_has_its_items(card_id: str, texts: list[str]) -> None:
    """Assemble: a numbered list of texts.
    Act: put a card of it.
    Assert: the card's items are the texts in order."""
    board = Board()
    board.apply([put(card_id, numbered_list(texts))])
    assert [item.md for item in board.cards[card_id].items] == texts


@given(boards(card_ids()), card_ids(), st.lists(item_texts(), min_size=1), reactions(), st.data())
def test_react_to_item_sets_the_reaction_on_that_item_only(
    board: Board, card_id: str, texts: list[str], reaction: Reaction | None, data: st.DataObject
) -> None:
    """Assemble: any board with a card of a numbered list put on it.
    Act: react to one item of the card.
    Assert: that item has the reaction, and the other items and cards are unchanged."""
    board.apply([put(card_id, numbered_list(texts))])
    before = board.model_copy(deep=True)
    number = data.draw(st.integers(1, len(texts)))
    board.react_to_item(card_id, number, reaction)
    items = before.cards[card_id].items
    items[number - 1] = items[number - 1].model_copy(update={"reaction": reaction})
    assert board == before


@given(boards(card_ids()), card_ids(), st.lists(item_texts(), min_size=1), st.lists(messages(), min_size=1), st.data())
def test_comments_on_an_item_add_to_that_item_only_in_order(
    board: Board, card_id: str, texts: list[str], comments: list[str], data: st.DataObject
) -> None:
    """Assemble: any board with a card of a numbered list put on it.
    Act: comment on one item of the card with each text.
    Assert: that item has the comments in order with distinct ids, and the other items and cards are unchanged."""
    board.apply([put(card_id, numbered_list(texts))])
    before = board.model_copy(deep=True)
    number = data.draw(st.integers(1, len(texts)))
    for comment in comments:
        board.comment_on_item(card_id, number, comment)
    added = board.cards[card_id].items[number - 1].comments
    assert [comment.text for comment in added] == comments
    assert len({comment.id for comment in added}) == len(comments)
    items = before.cards[card_id].items
    items[number - 1] = items[number - 1].model_copy(update={"comments": added})
    assert board == before


@given(card_ids(), st.lists(st.tuples(item_texts(), item_texts()), min_size=1))
def test_an_item_keeps_its_other_paragraphs(card_id: str, paragraphs: list[tuple[str, str]]) -> None:
    """Assemble: a numbered list whose items each have two paragraphs.
    Act: put a card of it.
    Assert: each item's markdown is its two paragraphs, without the indent."""
    board = Board()
    markers = [f"{n}. " for n in range(1, len(paragraphs) + 1)]
    md = "\n".join(
        f"{m}{first}\n\n{' ' * len(m)}{second}\n" for m, (first, second) in zip(markers, paragraphs, strict=True)
    )
    board.apply([put(card_id, md)])
    assert [item.md for item in board.cards[card_id].items] == [f"{first}\n\n{second}" for first, second in paragraphs]


@given(card_ids(), st.lists(item_texts(), min_size=1), st.data())
def test_a_numbered_list_with_an_item_that_starts_with_a_heading_has_no_items(
    card_id: str, texts: list[str], data: st.DataObject
) -> None:
    """Assemble: a numbered list of texts, one of which is a heading.
    Act: put a card of it.
    Assert: the card has no items."""
    heading = data.draw(st.integers(0, len(texts) - 1))
    board = Board()
    lines = [f"{n + 1}. {'# ' if n == heading else ''}{text}" for n, text in enumerate(texts)]
    board.apply([put(card_id, "\n".join(lines))])
    assert board.cards[card_id].items == []


@pytest.mark.parametrize("marker", ["", "- "])
@given(card_ids(), st.lists(item_texts(), min_size=1))
def test_a_card_of_lines_or_bullets_has_no_items(marker: str, card_id: str, texts: list[str]) -> None:
    """Assemble: lines of texts, as a paragraph or a bulleted list.
    Act: put a card of them.
    Assert: the card has no items."""
    board = Board()
    board.apply([put(card_id, "\n".join(f"{marker}{text}" for text in texts))])
    assert board.cards[card_id].items == []
