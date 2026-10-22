from contextlib import suppress

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.models.actions import Action, Author, Reaction, TBody, TValue
from agent_hud.models.board import Arrow, Board, Card, Point, Said, Thread
from agent_hud.models.columns import Column, ColumnKind
from agent_hud.outline import Outline
from tests.factories import comment, fill, link, move, put, react, remove, say, unlink, unreact
from tests.strategies import (
    action_ids,
    actions,
    card_ids,
    coordinates,
    item_texts,
    list_md,
    mds,
    messages,
    table_md,
    tables,
)


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
    Assert: the rest of the board is unchanged and the card and its position are gone, or ValueError when there was no card."""
    if card_id in board.cards:
        after = act(board, remove(card_id))
        assert (after.cards, after.threads) == outside(board, card_id)
        assert after.positions == {k: v for k, v in board.positions.items() if k != card_id}
    else:
        with pytest.raises(ValueError):
            act(board, remove(card_id))


@given(boards(), card_ids(), coordinates(), coordinates())
def test_move_places_the_card_or_raises(board: Board, card_id: str, x: float, y: float) -> None:
    """Assemble: any board.
    Act: move a card.
    Assert: the card has the new position and the rest of the board is unchanged, or ValueError when there was no card."""
    if card_id in board.cards:
        after = act(board, move(card_id, x, y))
        assert after == board.model_copy(update={"positions": {**board.positions, card_id: Point(x=x, y=y)}})
    else:
        with pytest.raises(ValueError):
            act(board, move(card_id, x, y))


@given(card_ids(), mds(), mds(), coordinates(), coordinates())
def test_put_keeps_the_position_of_the_card(card_id: str, md: str, again: str, x: float, y: float) -> None:
    """Assemble: a board with a card that the user moved.
    Act: put the card again.
    Assert: the card keeps its position."""
    board = act(act(Board(), put(card_id, md)), move(card_id, x, y))
    assert act(board, put(card_id, again)).positions == {card_id: Point(x=x, y=y)}


@given(card_ids(), mds(), coordinates(), coordinates())
def test_remove_drops_the_position_of_the_card(card_id: str, md: str, x: float, y: float) -> None:
    """Assemble: a board with a card that the user moved.
    Act: remove the card.
    Assert: the board has no position for it."""
    board = act(act(Board(), put(card_id, md)), move(card_id, x, y))
    assert act(board, remove(card_id)).positions == {}


@given(card_ids(), st.lists(item_texts(), min_size=1), st.from_type(Reaction), messages(), st.data())
def test_feedback_fits_the_card_and_each_list_item_only(
    card_id: str, texts: list[str], reaction: Reaction, text: str, data: st.DataObject
) -> None:
    """Assemble: a board with a card of a list.
    Act: react, unreact and comment on the card or a list item, and on an item after the last or another card.
    Assert: the card and its items take the feedback, and the others raise ValueError."""
    board = act(Board(), put(card_id, list_md("1. ", texts)))
    fits = data.draw(st.sampled_from([card_id, *(f"{card_id}/{n}" for n in range(1, len(texts) + 1))]))
    other = data.draw(card_ids().filter(lambda other: other != card_id))
    misses = data.draw(st.sampled_from([f"{card_id}/{len(texts) + 1}", other, f"{other}/1"]))
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


@given(boards(), st.lists(st.tuples(action_ids(), st.from_type(Author), messages())))
def test_say_adds_each_message_to_the_board(board: Board, messages: list[tuple[str, Author, str]]) -> None:
    """Assemble: any board.
    Act: say each message.
    Assert: the board has the messages in order, with the id of its action and its author, and is otherwise unchanged."""
    said = board
    for action_id, author, text in messages:
        said = act(said, say(text), author, action_id)
    added = tuple(Said(id=i, author=a, text=t) for i, a, t in messages)
    assert said == board.model_copy(update={"messages": (*board.messages, *added)})


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


@given(tables())
def test_outline_has_a_path_for_each_table_body_row(rows: list[list[str]]) -> None:
    """Assemble: a table with a header row and body rows.
    Act: outline it.
    Assert: the paths are the numbers of the body rows."""
    assert Outline(table_md(rows)).paths == {str(n) for n in range(1, len(rows) + 1)}


@given(st.lists(item_texts(), min_size=1), tables())
def test_outline_numbers_list_items_and_table_rows_together(texts: list[str], rows: list[list[str]]) -> None:
    """Assemble: a list, then a table.
    Act: outline them.
    Assert: one path for each list item and each body row."""
    md = list_md("1. ", texts) + "\n\n" + table_md(rows)
    assert Outline(md).paths == {str(n) for n in range(1, len(texts) + len(rows) + 1)}


@given(st.lists(item_texts(), min_size=1), st.lists(st.one_of(item_texts(), st.just("")), min_size=1))
def test_outline_numbers_list_items_and_code_lines_together(texts: list[str], lines: list[str]) -> None:
    """Assemble: a list, then a fenced code block of lines, some of them empty.
    Act: outline them.
    Assert: one path for each list item and each code line."""
    md = list_md("1. ", texts) + "\n\n```python\n" + "\n".join(lines) + "\n```"
    assert Outline(md).paths == {str(n) for n in range(1, len(texts) + len(lines) + 1)}


@pytest.mark.parametrize(
    ("header", "column"),
    [
        ("cost", Column(kind=ColumnKind.static)),
        ("note {text}", Column(kind=ColumnKind.text)),
        ("done { check }", Column(kind=ColumnKind.check)),
        ("cost {number}", Column(kind=ColumnKind.number)),
        ("size {S, M,L}", Column(kind=ColumnKind.select, options=("S", "M", "L"))),
    ],
)
def test_a_header_names_its_column(header: str, column: Column) -> None:
    """Assemble: a header cell.
    Act: read its column.
    Assert: the kind and options it names."""
    assert Column.from_header(header) == column


@pytest.mark.parametrize("header", ["pick {}", "pick {only}", "pick {a,}"])
def test_a_header_with_fewer_than_two_options_raises(header: str) -> None:
    """Assemble: a header cell whose braces name no kind and fewer than two options.
    Act: read its column.
    Assert: ValueError."""
    with pytest.raises(ValueError):
        Column.from_header(header)


@pytest.mark.parametrize(
    ("column", "fitting", "misfitting"),
    [
        (Column(kind=ColumnKind.text), ["", "x", None], [1.0, True]),
        (Column(kind=ColumnKind.check), [True, False, None], ["x", 1.0]),
        (Column(kind=ColumnKind.number), [0.0, 2.5, None], ["2", True]),
        (Column(kind=ColumnKind.select, options=("a", "b")), ["a", "b", None], ["c", 1.0, True]),
        (Column(kind=ColumnKind.static), [], ["x", None]),
    ],
)
def test_a_column_takes_values_of_its_kind(column: Column, fitting: list[TValue], misfitting: list[TValue]) -> None:
    """Assemble: a column of each kind.
    Act: check values against it.
    Assert: it takes the values of its kind and no others."""
    assert [column.fits(value) for value in fitting] == [True] * len(fitting)
    assert [column.fits(value) for value in misfitting] == [False] * len(misfitting)


@given(st.lists(item_texts(), min_size=1), tables())
def test_outline_has_an_input_for_each_cell_of_an_input_column(texts: list[str], rows: list[list[str]]) -> None:
    """Assemble: a list, then a table whose first column is a number input.
    Act: outline them.
    Assert: an input at each row's part number and column 1, and none in the other columns."""
    outline = Outline(list_md("1. ", texts) + "\n\n" + table_md(rows, [" {number}"]))
    numbers = range(len(texts) + 1, len(texts) + len(rows) + 1)
    assert outline.inputs == {f"{n}/1": Column(kind=ColumnKind.number) for n in numbers}


@given(card_ids(), tables(), st.from_type(Author))
def test_fill_sets_a_fitting_value_and_put_clears_it(card_id: str, rows: list[list[str]], author: Author) -> None:
    """Assemble: a card of a table with a select column, then a static column.
    Act: fill a cell of each column with an option, and fill the select cell with a value that is not an option; then put the card again.
    Assert: the select cell takes the option, the others raise ValueError, and the put clears the value."""
    md = table_md([[*row, "x"] for row in rows], [" {a, b}"])
    board = act(Board(), put(card_id, md))
    filled = act(board, fill(f"{card_id}/1/1", "a"), author)
    assert filled.values == {f"{card_id}/1/1": "a"}
    for body in fill(f"{card_id}/1/1", "c"), fill(f"{card_id}/1/{len(rows[0]) + 1}", "a"), fill(f"{card_id}/1", "a"):
        with pytest.raises(ValueError):
            act(board, body)
    assert act(filled, put(card_id, md)).values == {}


@pytest.mark.parametrize("header", ["pick {}", "pick {only}"])
def test_a_put_with_a_column_it_cannot_read_raises(header: str) -> None:
    """Assemble: an empty board.
    Act: put a card of a table whose header names fewer than two options.
    Assert: ValueError, so a write with it changes nothing."""
    with pytest.raises(ValueError):
        act(Board(), put("plan", f"| {header} |\n|---|\n| x |"))


@given(card_ids(), card_ids(), st.lists(item_texts(), min_size=1), st.from_type(Author), st.data())
def test_link_draws_an_arrow_between_parts_and_unlink_removes_it(
    card_id: str, arrow_id: str, texts: list[str], author: Author, data: st.DataObject
) -> None:
    """Assemble: a board with a card of a list.
    Act: link two of its parts, then unlink the arrow.
    Assert: the board has the arrow, then none."""
    board = act(Board(), put(card_id, list_md("1. ", texts)))
    parts = st.sampled_from([card_id, *(f"{card_id}/{n}" for n in range(1, len(texts) + 1))])
    src, dst = data.draw(parts), data.draw(parts)
    linked = act(board, link(arrow_id, src, dst), author)
    assert linked.arrows == {arrow_id: Arrow(src=src, dst=dst, text="", author=author)}
    assert act(linked, unlink(arrow_id)).arrows == {}


@pytest.mark.parametrize("ends", [("a", "a/9"), ("a/9", "a"), ("a", "b"), ("b", "a")])
def test_link_to_a_part_that_is_not_on_the_board_raises(ends: tuple[str, str]) -> None:
    """Assemble: a board with card a of one list item.
    Act: link to or from a part that is not there.
    Assert: ValueError."""
    board = act(Board(), put("a", "1. x"))
    with pytest.raises(ValueError):
        act(board, link("why", *ends))


@given(card_ids())
def test_unlink_of_no_arrow_raises(arrow_id: str) -> None:
    """Assemble: an empty board.
    Act: unlink an arrow.
    Assert: ValueError."""
    with pytest.raises(ValueError):
        act(Board(), unlink(arrow_id))


@pytest.mark.parametrize("body", [put("a", "1. y"), remove("a")])
def test_put_or_remove_drops_the_arrows_that_touch_the_card(body: TBody) -> None:
    """Assemble: a board with arrows from card a to card b, within b, and from b to a.
    Act: put or remove card a.
    Assert: only the arrow within b stays."""
    board = act(act(Board(), put("a", "1. x")), put("b", "1. x"))
    for arrow_id, src, dst in ("ab", "a/1", "b"), ("bb", "b", "b/1"), ("ba", "b/1", "a"):
        board = act(board, link(arrow_id, src, dst))
    assert list(act(board, body).arrows) == ["bb"]
