from contextlib import suppress

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.models.actions import Action, Author, Reaction, TBody
from agent_hud.models.board import Board, Card, Said, Thread
from agent_hud.outline import Outline
from tests.factories import comment, put, react, remove, say, unreact
from tests.strategies import action_ids, actions, card_ids, item_texts, list_md, mds, messages


@st.composite
def boards(draw: st.DrawFn) -> Board:
    """A board after any actions on a pool of ids, skipping those that do not fit."""
    board = Board()
    for action in draw(st.lists(actions(st.sampled_from(draw(st.lists(card_ids(), min_size=1)))))):
        with suppress(ValueError):
            board = board.apply(action)
    return board


def act(board: Board, body: TBody, author: Author = Author.user, action_id: str = "a") -> Board:
    return board.apply(Action(id=action_id, author=author, body=body))


def outside(board: Board, card_id: str) -> tuple[dict[str, Card], dict[str, Thread]]:
    """The cards and threads of the board that are not on the card."""
    cards = {k: v for k, v in board.cards.items() if k != card_id}
    threads = {ref: thread for ref, thread in board.threads.items() if ref.partition("/")[0] != card_id}
    return cards, threads


@given(boards(), card_ids(), mds(), st.from_type(Author))
def test_put_sets_the_card_and_clears_its_threads(board: Board, card_id: str, md: str, author: Author) -> None:
    """Assemble: any board.
    Act: put a card.
    Assert: the card has the markdown and author, it has no threads, and the rest of the board is unchanged."""
    after = act(board, put(card_id, md), author)
    assert after.cards[card_id] == Card(md=md, author=author)
    assert outside(after, card_id) == outside(board, card_id)
    assert not any(ref.partition("/")[0] == card_id for ref in after.threads)


@given(boards(), card_ids())
def test_remove_drops_the_card_and_its_threads_or_raises(board: Board, card_id: str) -> None:
    """Assemble: any board.
    Act: remove a card.
    Assert: the rest of the board is unchanged and the card is gone, or ValueError when there was no card."""
    if card_id in board.cards:
        after = act(board, remove(card_id))
        assert (after.cards, after.threads) == outside(board, card_id)
    else:
        with pytest.raises(ValueError):
            act(board, remove(card_id))


@given(card_ids(), st.lists(item_texts(), min_size=1), st.from_type(Reaction), messages(), st.data())
def test_feedback_fits_the_card_and_each_list_item_only(
    card_id: str, texts: list[str], reaction: Reaction, text: str, data: st.DataObject
) -> None:
    """Assemble: a board with a card of a list.
    Act: react, unreact and comment on the card or a list item, and on an item after the last or another card.
    Assert: the card and its items take the feedback, and the others raise ValueError."""
    board = act(Board(), put(card_id, list_md("1. ", texts)))
    fits = data.draw(st.sampled_from([card_id, *(f"{card_id}/{n}" for n in range(1, len(texts) + 1))]))
    misses = data.draw(st.sampled_from([f"{card_id}/{len(texts) + 1}", f"{card_id}x", f"{card_id}x/1"]))
    for body in react(fits, reaction), unreact(fits), comment(fits, text):
        act(board, body)
    for body in react(misses, reaction), unreact(misses), comment(misses, text):
        with pytest.raises(ValueError):
            act(board, body)


@given(card_ids(), mds(), st.from_type(Reaction), st.from_type(Author))
def test_react_then_unreact_sets_then_clears_the_reaction(
    card_id: str, md: str, reaction: Reaction, author: Author
) -> None:
    """Assemble: a board with a card.
    Act: react to the card, then unreact.
    Assert: the thread has the reaction, then none."""
    board = act(Board(), put(card_id, md))
    reacted = act(board, react(card_id, reaction), author)
    assert reacted.threads == {card_id: Thread(reaction=reaction)}
    assert act(reacted, unreact(card_id), author).threads == {card_id: Thread()}


@given(card_ids(), mds(), st.lists(st.tuples(action_ids(), st.from_type(Author), messages()), min_size=1))
def test_comments_add_in_order_with_their_action_and_author(
    card_id: str, md: str, comments: list[tuple[str, Author, str]]
) -> None:
    """Assemble: a board with a card.
    Act: comment on the card with each text.
    Assert: the thread has each comment in order, with the id of its action and its author."""
    board = act(Board(), put(card_id, md))
    for action_id, author, text in comments:
        board = act(board, comment(card_id, text), author, action_id)
    assert board.threads[card_id].comments == tuple(Said(id=i, author=a, text=t) for i, a, t in comments)


@given(boards(), messages())
def test_say_leaves_the_board_as_it_is(board: Board, text: str) -> None:
    """Assemble: any board.
    Act: say a message.
    Assert: the board is unchanged."""
    assert act(board, say(text)) == board


@pytest.mark.parametrize("marker", ["- ", "1. "])
@given(st.lists(item_texts(), min_size=1))
def test_outline_has_a_path_for_each_list_item(marker: str, texts: list[str]) -> None:
    """Assemble: a bulleted or numbered list of texts.
    Act: outline it.
    Assert: the paths are the numbers of the items."""
    assert Outline(list_md(marker, texts)).paths == {str(n) for n in range(1, len(texts) + 1)}


@given(st.lists(item_texts(), min_size=1), st.lists(item_texts(), min_size=1))
def test_outline_numbers_nested_items_in_document_order(outer: list[str], inner: list[str]) -> None:
    """Assemble: a list whose first item holds a list.
    Act: outline it.
    Assert: there is a path for each item of both lists."""
    md = list_md("- ", outer[:1]) + "\n" + list_md("  - ", inner) + "\n" + list_md("- ", outer[1:])
    assert Outline(md).paths == {str(n) for n in range(1, len(outer) + len(inner) + 1)}


@given(st.lists(item_texts(), min_size=1))
def test_outline_of_lines_has_no_paths(texts: list[str]) -> None:
    """Assemble: lines of texts, which markdown reads as one paragraph.
    Act: outline it.
    Assert: no paths."""
    assert Outline(list_md("", texts)).paths == frozenset()
