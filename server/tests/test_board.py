import re
from contextlib import suppress

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from agent_hud.models.actions import Action, Author, Reaction, TBody, TValue
from agent_hud.models.base import Model
from agent_hud.models.board import Arrow, Board, Card, Point, Said, Thread, Version
from agent_hud.models.columns import Column, ColumnKind
from agent_hud.outline import Outline
from tests.factories import (
    clear,
    comment,
    fill,
    link,
    move,
    place,
    put,
    react,
    remove,
    resize,
    restore,
    say,
    unlink,
    unreact,
)
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
    widths,
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


def retired(board: Board, card_id: str) -> tuple[Version, ...]:
    """The history of the card after a put or remove of it on the board."""
    on_card = {ref for ref in [*board.threads, *board.values] if ref.partition("/")[0] == card_id}
    version = Version(
        card=board.cards[card_id],
        threads={ref: thread for ref, thread in board.threads.items() if ref in on_card},
        values={ref: value for ref, value in board.values.items() if ref in on_card},
    )
    return (*board.history.get(card_id, ()), version)


def text_of(board: Board, ref: str) -> str:
    """The text of the part, or the markdown of the card when the ref is a card id."""
    card_id, _, path = ref.partition("/")
    return board.texts_of(card_id)[path] if path else board.cards[card_id].md


@given(boards(), card_ids(), mds(), st.from_type(Author))
def test_put_sets_the_card_and_keeps_the_feedback_whose_part_text_is_unchanged(
    board: Board, card_id: str, md: str, author: Author
) -> None:
    """Assemble: any board.
    Act: put a card.
    Assert: the card has the markdown; it has the author, or keeps the author of the card it replaces and counts as edited when that author differs; the rest of the board is unchanged, and each thread that was on the card is on a part of the new card with the same text, or else in the version the put added to the card's history."""
    after = act(board, put(card_id, md), author)
    old = board.cards.get(card_id)
    expected = (
        Card(md=md, author=author) if old is None else Card(md=md, author=old.author, edited=author != old.author)
    )
    assert after.cards[card_id] == expected
    assert outside(after, card_id) == outside(board, card_id)
    if card_id not in board.cards:
        assert after.history.get(card_id, ()) == board.history.get(card_id, ())
        return
    assert after.history[card_id][:-1] == board.history.get(card_id, ())
    version = after.history[card_id][-1]
    assert version.card == board.cards[card_id]
    on_card = {ref: thread for ref, thread in board.threads.items() if ref.partition("/")[0] == card_id}
    kept = {ref: thread for ref, thread in after.threads.items() if ref.partition("/")[0] == card_id}
    assert sorted(on_card.values(), key=str) == sorted([*kept.values(), *version.threads.values()], key=str)
    texts = [text_of(board, ref) for ref in on_card]
    assert all(text_of(after, ref) in texts for ref in kept)


@given(boards(), card_ids(), mds(), st.integers(min_value=0, max_value=3))
def test_put_with_a_version_replaces_the_card_at_that_version_or_raises(
    board: Board, card_id: str, md: str, version: int
) -> None:
    """Assemble: any board.
    Act: put a card with the number of earlier versions it is expected to have, as the page's editor does.
    Assert: the same board as a put without the number when the card is on the board with that many earlier versions, or ValueError that names the card."""
    earlier = len(board.history.get(card_id, ()))
    if card_id in board.cards and earlier == version:
        assert act(board, put(card_id, md, version)) == act(board, put(card_id, md))
    else:
        with pytest.raises(ValueError, match=f"card '{card_id}'"):
            act(board, put(card_id, md, version))


@given(boards(), card_ids())
def test_restore_puts_the_last_version_of_a_removed_card_back_or_raises(board: Board, card_id: str) -> None:
    """Assemble: any board.
    Act: restore a card.
    Assert: a removed card is back as its last version was, with the history as it was, or ValueError when the card is on the board or was never there."""
    if card_id not in board.cards and board.history.get(card_id):
        after = act(board, restore(card_id))
        assert after.cards[card_id] == board.history[card_id][-1].card
        assert after.history == board.history
        assert outside(after, card_id) == outside(board, card_id)
    else:
        with pytest.raises(ValueError, match=f"card '{card_id}'"):
            act(board, restore(card_id))


@given(boards())
def test_clear_moves_each_card_to_its_history_and_empties_the_rest(board: Board) -> None:
    """Assemble: any board.
    Act: clear.
    Assert: no cards, threads, values, arrows, positions, widths or messages; each card is the last version in its
    history, with the feedback it had; and the history of the other cards is as it was."""
    cleared = board.apply(Action(id="c", author=Author.user, body=clear()))
    assert (
        cleared.cards,
        cleared.threads,
        cleared.values,
        cleared.arrows,
        cleared.positions,
        cleared.widths,
        cleared.messages,
    ) == ({}, {}, {}, {}, {}, {}, ())
    assert set(cleared.history) == {*board.history, *board.cards}
    for card_id, card in board.cards.items():
        version = cleared.history[card_id][-1]
        assert version.card == card
        assert version.threads == {ref: thread for ref, thread in board.threads.items() if ref.split("/")[0] == card_id}
        assert cleared.history[card_id][:-1] == board.history.get(card_id, ())
    for card_id in board.history:
        if card_id not in board.cards:
            assert cleared.history[card_id] == board.history[card_id]


@given(boards(), card_ids())
def test_remove_drops_the_card_and_its_threads_or_raises(board: Board, card_id: str) -> None:
    """Assemble: any board.
    Act: remove a card.
    Assert: the rest of the board is unchanged and the card, its position and its width are gone, or ValueError when there
    was no card."""
    if card_id in board.cards:
        after = act(board, remove(card_id))
        assert (after.cards, after.threads) == outside(board, card_id)
        assert after.positions == {k: v for k, v in board.positions.items() if k != card_id}
        assert after.widths == {k: v for k, v in board.widths.items() if k != card_id}
        assert after.history[card_id] == retired(board, card_id)
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


@given(boards(), card_ids(), widths())
def test_resize_sets_the_width_of_the_card_or_raises(board: Board, card_id: str, width: float) -> None:
    """Assemble: any board.
    Act: resize a card.
    Assert: the card has the new width and the rest of the board is unchanged, or ValueError when there was no card."""
    if card_id in board.cards:
        after = act(board, resize(card_id, width))
        assert after == board.model_copy(update={"widths": {**board.widths, card_id: width}})
    else:
        with pytest.raises(ValueError):
            act(board, resize(card_id, width))


@given(card_ids(), mds(), mds(), widths())
def test_put_keeps_the_width_of_the_card(card_id: str, md: str, again: str, width: float) -> None:
    """Assemble: a board with a card that the user resized.
    Act: put the card again.
    Assert: the card keeps its width."""
    board = act(act(Board(), put(card_id, md)), resize(card_id, width))
    assert act(board, put(card_id, again)).widths == {card_id: width}


@pytest.mark.parametrize("width", [0, -1, float("inf"), float("nan")])
def test_resize_takes_a_positive_width_only(width: float) -> None:
    """Assemble: nothing.
    Act: make a resize with a width that is not a positive number.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        resize("a", width)


@given(boards(), card_ids(), coordinates(), coordinates())
def test_place_gives_the_card_a_position_once_or_raises(board: Board, card_id: str, x: float, y: float) -> None:
    """Assemble: any board.
    Act: place a card, as the page does once it has the card's size.
    Assert: the card has the position when it had none, the board is unchanged when it had one, or ValueError when there was no card."""
    if card_id in board.cards:
        after = act(board, place(card_id, x, y))
        expected = board.positions.get(card_id, Point(x=x, y=y))
        assert after == board.model_copy(update={"positions": {**board.positions, card_id: expected}})
    else:
        with pytest.raises(ValueError):
            act(board, place(card_id, x, y))


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
    assert reacted.threads == {card_id: Thread(reactions={author: reaction})}
    assert act(reacted, unreact(card_id), author).threads == {card_id: Thread()}


@given(card_ids(), mds(), st.from_type(Reaction), st.from_type(Reaction))
def test_each_author_has_their_own_reaction(card_id: str, md: str, users: Reaction, agents: Reaction) -> None:
    """Assemble: a board with a card that the user reacted to.
    Act: the agent reacts to it, then unreacts.
    Assert: the thread has both reactions by author, then the user's alone."""
    board = act(act(Board(), put(card_id, md)), react(card_id, users), Author.user)
    both = act(board, react(card_id, agents), Author.agent)
    assert both.threads == {card_id: Thread(reactions={Author.user: users, Author.agent: agents})}
    assert act(both, unreact(card_id), Author.agent).threads == {card_id: Thread(reactions={Author.user: users})}


@given(card_ids(), mds(), st.lists(st.tuples(action_ids(), st.from_type(Author), messages()), min_size=1))
def test_comments_add_in_order_with_their_action_and_author(
    card_id: str, md: str, comments: list[tuple[str, Author, str]]
) -> None:
    """Assemble: a board with a card.
    Act: comment on the card with each text.
    Assert: the thread and the chat have each comment in order, with the id of its action, its author and the card's ref."""
    board = act(Board(), put(card_id, md))
    for action_id, author, text in comments:
        board = act(board, comment(card_id, text), author, action_id)
    said = tuple(Said(id=i, author=a, text=t, ref=card_id) for i, a, t in comments)
    assert (board.threads[card_id].comments, board.messages) == (said, said)


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


@given(card_ids().filter(lambda card_id: card_id != "t"), st.lists(item_texts(), min_size=2), st.from_type(Reaction))
def test_part_texts_name_the_text_of_each_part_an_action_names(
    card_id: str, texts: list[str], reaction: Reaction
) -> None:
    """Assemble: a board with a list card and a table card.
    Act: get the part texts of a reaction, a link, a fill and a put.
    Assert: the text of the list item, of both ends of the link, of the row of the cell, and none for the put."""
    board = act(Board(), put(card_id, list_md("1. ", texts)))
    board = act(board, put("t", "| a | b {number} |\n|---|---|\n| x | |"))
    assert board.part_texts(react(f"{card_id}/2", reaction)) == {f"{card_id}/2": texts[1]}
    assert board.part_texts(link("l", f"{card_id}/1", card_id)) == {f"{card_id}/1": texts[0]}
    assert board.part_texts(fill("t/1/2", 3)) == {"t/1": "x | "}
    assert board.part_texts(put(card_id, "x")) == {}


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
def test_outline_of_lines_is_one_paragraph(texts: list[str]) -> None:
    """Assemble: lines of texts, which markdown reads as one paragraph.
    Act: outline it.
    Assert: one path, whose text is the lines."""
    assert Outline(list_md("", texts)).texts == {"1": "\n".join(texts)}


@given(st.lists(item_texts(), min_size=1), item_texts(), item_texts())
def test_outline_numbers_headings_paragraphs_and_list_items_together(texts: list[str], title: str, prose: str) -> None:
    """Assemble: a heading, a paragraph, a list whose items are loose, so that each holds a paragraph, and a quoted paragraph.
    Act: outline it.
    Assert: the heading, the paragraph, each item and the quote are parts in document order; the items' own paragraphs are not."""
    md = f"# {title}\n\n{prose}\n\n" + "\n\n".join(f"- {text}" for text in texts) + f"\n\n> {prose}"
    assert list(Outline(md).texts.values()) == [title, prose, *texts, prose]


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


@given(st.lists(item_texts(), min_size=1), st.integers(1, 999))
def test_a_code_line_names_its_file_and_line_when_its_block_has_a_file(lines: list[str], start: int) -> None:
    """Assemble: a fenced code block with a file and a first line number, and one with neither.
    Act: outline them.
    Assert: the text of each line of the first starts with the file and its number, and the second has the plain lines."""
    code = "\n".join(lines)
    outline = Outline(f"```python file=src/app.py start={start}\n{code}\n```\n\n```\n{code}\n```")
    assert list(outline.texts.values()) == [
        *(f"src/app.py:{n}: {line}" for n, line in enumerate(lines, start=start)),
        *lines,
    ]


@pytest.mark.parametrize(
    ("header", "column"),
    [
        ("cost", Column(kind=ColumnKind.static, name="cost")),
        ("note {text}", Column(kind=ColumnKind.text, name="note")),
        ("done { check }", Column(kind=ColumnKind.check, name="done")),
        ("cost {number}", Column(kind=ColumnKind.number, name="cost")),
        ("{number}", Column(kind=ColumnKind.number)),
        ("size {S, M,L}", Column(kind=ColumnKind.select, name="size", options=("S", "M", "L"))),
    ],
)
def test_a_header_names_its_column(header: str, column: Column) -> None:
    """Assemble: a header cell.
    Act: read its column.
    Assert: the name, kind and options it names."""
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
    assert outline.inputs == {f"{n}/1": Column(kind=ColumnKind.number, name="h") for n in numbers}


@given(card_ids(), tables(), st.from_type(Author))
def test_fill_sets_a_fitting_value_and_a_put_of_a_changed_row_clears_it(
    card_id: str, rows: list[list[str]], author: Author
) -> None:
    """Assemble: a card of a table with a select column, then a static column.
    Act: fill a cell of each column with an option, and fill the select cell with a value that is not an option; then put the card again as it is, and with another text in each row.
    Assert: the select cell takes the option, the others raise ValueError, the put as it is keeps the value, and the put of the changed rows moves it to the history."""
    md = table_md([[*row, "x"] for row in rows], [" {a, b}"])
    board = act(Board(), put(card_id, md))
    filled = act(board, fill(f"{card_id}/1/1", "a"), author)
    assert filled.values == {f"{card_id}/1/1": "a"}
    for body in fill(f"{card_id}/1/1", "c"), fill(f"{card_id}/1/{len(rows[0]) + 1}", "a"), fill(f"{card_id}/1", "a"):
        with pytest.raises(ValueError):
            act(board, body)
    assert act(filled, put(card_id, md)).values == {f"{card_id}/1/1": "a"}
    changed = table_md([[*row, "y"] for row in rows], [" {a, b}"])
    assert act(filled, put(card_id, changed)).values == {}
    assert act(filled, put(card_id, changed)).history[card_id][-1].values == {f"{card_id}/1/1": "a"}


def test_a_value_follows_its_row_while_its_column_takes_it() -> None:
    """Assemble: a card of a table of two rows with a number column, with a value in the second row.
    Act: put the table with the rows swapped, then with the number column as a check column.
    Assert: the value is on the first row, then gone to the history."""
    board = act(Board(), put("t", "| task | hours {number} |\n|---|---|\n| parse | |\n| render | |"))
    filled = act(board, fill("t/2/2", 3))
    swapped = act(filled, put("t", "| task | hours {number} |\n|---|---|\n| render | |\n| parse | |"))
    assert swapped.values == {"t/1/2": 3}
    checks = act(swapped, put("t", "| task | done {check} |\n|---|---|\n| render | |\n| parse | |"))
    assert (checks.values, checks.history["t"][-1].values) == ({}, {"t/1/2": 3})


def test_a_put_keeps_the_feedback_on_the_parts_whose_text_it_keeps() -> None:
    """Assemble: a card of three items with a reaction on each, a comment on the first and on the card, and an arrow from the first to the third.
    Act: put the card with the second item changed and the first and third swapped.
    Assert: the feedback on the first and third items follows them to their new numbers, with the comment's ref in the thread and in the chat, the arrow follows them, and the second item's reaction and the card's comment go to the history."""
    board = act(Board(), put("plan", "1. parse\n2. rewrite the cache\n3. render"))
    for n, reaction in enumerate([Reaction.approve, Reaction.reject, Reaction.question], start=1):
        board = act(board, react(f"plan/{n}", reaction))
    board = act(board, comment("plan/1", "fast?"), action_id="c1")
    board = act(board, comment("plan", "looks ok"), action_id="c2")
    board = act(board, link("why", "plan/1", "plan/3"))
    after = act(board, put("plan", "1. render\n2. keep the cache\n3. parse"))
    assert after.threads == {
        "plan/3": Thread(
            reactions={Author.user: Reaction.approve},
            comments=(Said(id="c1", author=Author.user, text="fast?", ref="plan/3"),),
        ),
        "plan/1": Thread(reactions={Author.user: Reaction.question}),
    }
    assert [said.ref for said in after.messages] == ["plan/3", "plan"]
    assert after.arrows == {"why": Arrow(src="plan/3", dst="plan/1", text="", author=Author.user)}
    assert after.history["plan"][-1] == Version(
        card=board.cards["plan"],
        threads={
            "plan/2": Thread(reactions={Author.user: Reaction.reject}),
            "plan": Thread(comments=(Said(id="c2", author=Author.user, text="looks ok", ref="plan"),)),
        },
    )


def test_a_put_of_the_same_markdown_keeps_all_the_feedback() -> None:
    """Assemble: a card with a reaction on it and on an item.
    Act: put the card with the same markdown.
    Assert: the threads are unchanged, and the version in the history has none."""
    board = act(act(act(Board(), put("a", "1. x")), react("a", Reaction.approve)), react("a/1", Reaction.reject))
    after = act(board, put("a", "1. x"))
    assert after.threads == board.threads
    assert after.history["a"] == (Version(card=board.cards["a"]),)


def test_parts_with_the_same_text_match_in_order() -> None:
    """Assemble: a card of two items of the same text, with a reaction on the second.
    Act: put the card with a new first item and the two items after it.
    Assert: the reaction is on the third item, which is the second of the same text."""
    board = act(act(Board(), put("a", "1. x\n2. x")), react("a/2", Reaction.approve))
    assert list(act(board, put("a", "1. y\n2. x\n3. x")).threads) == ["a/3"]


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


@pytest.mark.parametrize(
    ("body", "stay"), [(put("a", "1. y"), ["bb", "ba"]), (remove("a"), ["bb"])], ids=["put", "remove"]
)
def test_put_or_remove_drops_the_arrows_at_the_parts_it_changes(body: TBody, stay: list[str]) -> None:
    """Assemble: a board with arrows from a part of card a to card b, within b, and from b to card a.
    Act: put card a with the part changed, or remove card a.
    Assert: the put keeps the arrow within b and the one to card a; the remove keeps only the one within b."""
    board = act(act(Board(), put("a", "1. x")), put("b", "1. x"))
    for arrow_id, src, dst in ("ab", "a/1", "b"), ("bb", "b", "b/1"), ("ba", "b/1", "a"):
        board = act(board, link(arrow_id, src, dst))
    assert list(act(board, body).arrows) == stay


TABLE = "1. a\n2. b\n\n| task | size {S, M, L} | done {check} |\n|---|---|---|\n| x | | |"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (remove("risk"), "no card 'risk': the cards are plan"),
        (react("plan/9", Reaction.approve), "no part 'plan/9': card 'plan' has parts 1 to 3"),
        (comment("plan/3/1", "why?"), "'plan/3/1' is a cell, not a part: card 'plan' has parts 1 to 3"),
        (link("why", "plan", "risk/1"), "no card 'risk': the cards are plan"),
        (fill("plan/3/2", "XL"), "input 'plan/3/2' (size) takes one of S, M, L"),
        (fill("plan/3/3", "yes"), "input 'plan/3/3' (done) takes true or false"),
        (fill("plan/3/1", "x"), "no input 'plan/3/1': the input columns of row 'plan/3' are 2 (size), 3 (done)"),
        (fill("plan/1/1", "x"), "part 'plan/1' is not a table row with input columns"),
        (fill("plan/9/1", "x"), "no part 'plan/9': card 'plan' has parts 1 to 3"),
        (fill("plan/1", "x"), "'plan/1' is not a cell: fill takes a card id, row and column such as plan/2/3"),
        (
            put("t", "| a {X} |\n|---|\n| x |"),
            "card 't': column 'a {X}' takes text, check, number or two or more options",
        ),
        (unlink("why"), "no arrow 'why'"),
    ],
    ids=lambda value: value.kind if isinstance(value, Model) else "",
)
def test_an_action_that_does_not_fit_raises_with_the_valid_choices(body: TBody, reason: str) -> None:
    """Assemble: a board with card plan of two list items and a table row with two input columns.
    Act: apply an action that names a card, part, cell or value that the board does not have.
    Assert: ValueError whose message names what the board has instead, in one line."""
    with pytest.raises(ValueError, match=f"^{re.escape(reason)}$"):
        act(act(Board(), put("plan", TABLE)), body)


def test_a_part_on_a_card_with_no_parts_raises_so() -> None:
    """Assemble: an empty board.
    Act: react to a part of a card of a rule alone, and remove a card.
    Assert: ValueError says that the card has no parts, and that the board has no cards."""
    with pytest.raises(ValueError, match=r"^no part 'a/1': card 'a' has no parts$"):
        act(act(Board(), put("a", "---")), react("a/1", Reaction.approve))
    with pytest.raises(ValueError, match=r"^no card 'a': the board has no cards$"):
        act(Board(), remove("a"))
