import re
from contextlib import suppress

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from agent_hud.models.actions import Action, Author, TBody
from agent_hud.models.base import Model
from agent_hud.models.board import Arrow, Board, Card, Point, Said, Size, Thread, Version
from agent_hud.text import places, squeeze, text_of
from tests.factories import clear, comment, link, move, place, put, remove, resize, restore, say, unlink
from tests.strategies import (
    action_ids,
    actions,
    card_ids,
    coordinates,
    item_texts,
    list_md,
    mds,
    messages,
    sizes,
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
    threads = {k: v for k, v in board.threads.items() if v.card != card_id}
    return cards, threads


def retired(board: Board, card_id: str) -> tuple[Version, ...]:
    """The history of the card after a remove of it on the board."""
    version = Version(card=board.cards[card_id], threads={k: v for k, v in board.threads.items() if v.card == card_id})
    return (*board.history.get(card_id, ()), version)


@given(boards(), card_ids(), mds(), st.from_type(Author))
def test_put_sets_the_card_and_keeps_the_threads_whose_words_it_keeps(
    board: Board, card_id: str, md: str, author: Author
) -> None:
    """Assemble: any board.
    Act: put a card.
    Assert: the card has the markdown; it has the author, or keeps the author of the card it replaces and counts as edited when that author differs; the rest of the board is unchanged, and each thread that was on the card is on the new card at words its text shows, or else in the version the put added to the card's history."""
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
    on_card = {k for k, v in board.threads.items() if v.card == card_id}
    kept = {k: v for k, v in after.threads.items() if v.card == card_id}
    assert on_card == {*kept, *version.threads}
    assert not set(kept) & set(version.threads)
    for thread in kept.values():
        assert thread.occurrence < len(places(md, thread.quote))


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
    Assert: no cards, threads, arrows, positions, sizes or messages; each card is the last version in its
    history, with the threads it had; and the history of the other cards is as it was."""
    cleared = board.apply(Action(id="c", author=Author.user, body=clear()))
    assert (cleared.cards, cleared.threads, cleared.arrows, cleared.positions, cleared.sizes, cleared.messages) == (
        {},
        {},
        {},
        {},
        {},
        (),
    )
    assert set(cleared.history) == {*board.history, *board.cards}
    for card_id, card in board.cards.items():
        version = cleared.history[card_id][-1]
        assert version.card == card
        assert version.threads == {k: v for k, v in board.threads.items() if v.card == card_id}
        assert cleared.history[card_id][:-1] == board.history.get(card_id, ())
    for card_id in board.history:
        if card_id not in board.cards:
            assert cleared.history[card_id] == board.history[card_id]


@given(boards(), card_ids())
def test_remove_drops_the_card_and_its_threads_or_raises(board: Board, card_id: str) -> None:
    """Assemble: any board.
    Act: remove a card.
    Assert: the rest of the board is unchanged and the card, its position, its size and the arrows at it are gone, or ValueError when there was no card."""
    if card_id in board.cards:
        after = act(board, remove(card_id))
        assert (after.cards, after.threads) == outside(board, card_id)
        assert after.positions == {k: v for k, v in board.positions.items() if k != card_id}
        assert after.sizes == {k: v for k, v in board.sizes.items() if k != card_id}
        assert after.arrows == {k: v for k, v in board.arrows.items() if card_id not in (v.card, v.dst)}
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


@given(boards(), card_ids(), sizes())
def test_resize_sets_the_dimensions_it_gives_or_raises(
    board: Board, card_id: str, size: tuple[float | None, float | None]
) -> None:
    """Assemble: any board.
    Act: resize a card by a width, a height or both.
    Assert: the card has each dimension given and keeps the other, and the rest of the board is unchanged, or ValueError when there was no card."""
    width, height = size
    if card_id in board.cards:
        after = act(board, resize(card_id, width, height))
        old = board.sizes.get(card_id, Size())
        expected = Size(width=old.width if width is None else width, height=old.height if height is None else height)
        assert after == board.model_copy(update={"sizes": {**board.sizes, card_id: expected}})
    else:
        with pytest.raises(ValueError):
            act(board, resize(card_id, width, height))


def test_resize_keeps_the_dimension_it_leaves_out() -> None:
    """Assemble: a card resized to a width.
    Act: resize it to a height, then to another width.
    Assert: each resize keeps the other dimension."""
    board = act(act(Board(), put("a", "x")), resize("a", width=300))
    tall = act(board, resize("a", height=200))
    assert tall.sizes == {"a": Size(width=300, height=200)}
    assert act(tall, resize("a", width=400)).sizes == {"a": Size(width=400, height=200)}


@given(card_ids(), mds(), mds(), widths(), widths())
def test_put_keeps_the_size_of_the_card(card_id: str, md: str, again: str, width: float, height: float) -> None:
    """Assemble: a board with a card that the user resized.
    Act: put the card again.
    Assert: the card keeps its size."""
    board = act(act(Board(), put(card_id, md)), resize(card_id, width, height))
    assert act(board, put(card_id, again)).sizes == {card_id: Size(width=width, height=height)}


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_resize_takes_positive_dimensions_only(value: float) -> None:
    """Assemble: nothing.
    Act: make a resize with a width or a height that is not a positive number, and one with neither.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        resize("a", width=value)
    with pytest.raises(ValidationError):
        resize("a", height=value)
    with pytest.raises(ValidationError):
        resize("a")


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


@given(card_ids(), st.lists(item_texts(), min_size=1, unique=True), messages(), st.data())
def test_a_comment_fits_the_words_the_card_shows_and_the_card(
    card_id: str, texts: list[str], text: str, data: st.DataObject
) -> None:
    """Assemble: a board with a card of a list of distinct words.
    Act: comment on the card, on an item's words, on words the card does not show, and on another card.
    Assert: the card and its words take the comment, and the others raise ValueError."""
    board = act(Board(), put(card_id, list_md("1. ", texts)))
    quote = data.draw(st.sampled_from(["", *texts]))
    other = data.draw(card_ids().filter(lambda other: other != card_id))
    if len(places(board.cards[card_id].md, quote)) == 1:
        act(board, comment(card_id, text, quote))
    with pytest.raises(ValueError):
        act(board, comment(card_id, text, "zz not on the card zz"))
    with pytest.raises(ValueError):
        act(board, comment(other, text, quote))


@given(card_ids(), mds(), st.lists(st.tuples(action_ids(), st.from_type(Author), messages()), min_size=1))
def test_comments_on_the_card_add_in_order_to_one_thread(
    card_id: str, md: str, comments: list[tuple[str, Author, str]]
) -> None:
    """Assemble: a board with a card.
    Act: comment on the card as a whole with each text.
    Assert: one thread, under the id of the first comment, and the chat have each comment in order, with the id of its action, its author and the thread."""
    board = act(Board(), put(card_id, md))
    for action_id, author, text in comments:
        board = act(board, comment(card_id, text), author, action_id)
    first = comments[0][0]
    said = tuple(Said(id=i, author=a, text=t, thread=first) for i, a, t in comments)
    assert board.threads == {first: Thread(card=card_id, comments=said)}
    assert board.messages == said


def test_a_comment_on_the_same_words_joins_their_thread() -> None:
    """Assemble: a card with a thread of the user on its words "tag the release".
    Act: the agent comments on the same words, with other spacing; then on other words.
    Assert: the agent's first comment joins the user's thread, and the second starts a thread of its own."""
    board = act(Board(), put("plan", "1. write the changelog\n2. tag the release"))
    board = act(board, comment("plan", "after the smoke test?", "tag the release"), action_id="u1")
    board = act(board, comment("plan", "Agreed.", "tag  the\nrelease"), Author.agent, "a1")
    board = act(board, comment("plan", "Which file?", "changelog"), Author.agent, "a2")
    assert list(board.threads) == ["u1", "a2"]
    assert [said.id for said in board.threads["u1"].comments] == ["u1", "a1"]
    assert board.threads["a2"] == Thread(
        card="plan",
        quote="changelog",
        comments=(Said(id="a2", author=Author.agent, text="Which file?", thread="a2"),),
    )
    assert [said.thread for said in board.messages] == ["u1", "u1", "a2"]


def test_a_comment_at_an_occurrence_starts_a_thread_there() -> None:
    """Assemble: a card that shows "parse" at two places.
    Act: comment on the second place, then again on the first and the second.
    Assert: two threads, at occurrences 1 and 0, and the last comment joins the thread at occurrence 1."""
    board = act(Board(), put("plan", "1. parse\n2. render\n3. parse again"))
    board = act(board, comment("plan", "this one", "parse", 1), action_id="c1")
    board = act(board, comment("plan", "that one", "parse", 0), action_id="c2")
    board = act(board, comment("plan", "still this one", "parse", 1), action_id="c3")
    assert {k: (v.occurrence, [said.id for said in v.comments]) for k, v in board.threads.items()} == {
        "c1": (1, ["c1", "c3"]),
        "c2": (0, ["c2"]),
    }


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


def test_text_of_has_the_words_the_page_shows() -> None:
    """Assemble: markdown with a heading, emphasis, struck words, an entity, task items, a table with a column of boxes, an image, raw HTML and a code block with a file.
    Act: get its text.
    Assert: the words without markdown, without the boxes, the image and the HTML, and each line of code as it is."""
    md = (
        "# Plan\n\nShip **the** board ~~soon~~ &amp; more ![logo](a.png) <b>x</b>\n\n"
        "- [ ] task one\n- [x] task two\n- plain [ ] item\n\n"
        "| | Step |\n|---|---|\n| [x] | parse |\n| [ ] | render |\n\n"
        "```py file=src/app.py start=40\nx = 1\n\ny = 2\n```"
    )
    assert text_of(md).split("\n") == [
        "Plan",
        "Ship the board soon & more  x",
        "task one",
        "task two",
        "plain [ ] item",
        "",
        "Step",
        "",
        "parse",
        "",
        "render",
        "x = 1",
        "",
        "y = 2",
    ]


@pytest.mark.parametrize(
    ("md", "quote", "found"),
    [
        ("1. parse\n2. render", "render", [5]),
        ("1. parse\n2. parse", "parse", [0, 5]),
        ("1. parse\n2. render", "parse render", [0]),
        ("1. parse\n2. render", "  parse\nrender ", [0]),
        ("aaa", "aa", [0, 1]),
        ("1. parse", "nowhere", []),
        ("1. parse", "", [0]),
        ("**bold** words", "bold words", [0]),
    ],
)
def test_places_finds_each_place_of_the_quote_without_white_space(md: str, quote: str, found: list[int]) -> None:
    """Assemble: markdown and a quote of its words.
    Act: find the places of the quote.
    Assert: each start in the text without white space, across blocks and markdown, overlapping too; one place for an empty quote."""
    assert places(md, quote) == found


@given(st.lists(item_texts(), min_size=1))
def test_each_list_item_is_a_place_in_the_text(texts: list[str]) -> None:
    """Assemble: a list of words.
    Act: find each item's words.
    Assert: the card shows each item's words."""
    md = list_md("- ", texts)
    assert all(places(md, text) for text in texts)
    assert squeeze(text_of(md)) == squeeze("".join(texts))


def test_a_thread_follows_its_words_to_the_nearest_place_and_goes_to_the_history_when_they_go() -> None:
    """Assemble: a card with threads on "the cache" at its second place, on "render", on the card as a whole, and an arrow from "render" to another card.
    Act: put the card with a new first line, and with "render" gone; then put it again with "the cache" gone too.
    Assert: the thread on "the cache" is at the place nearest to where it was, the card's thread stays, the thread on "render" and its arrow go to the history and drop; then the thread on "the cache" goes too, and the card's thread still stays."""
    board = act(act(Board(), put("plan", "1. read the cache\n2. write the cache\n3. render")), put("log", "x"))
    board = act(board, comment("plan", "shared?", "the cache", 1), action_id="c1")
    board = act(board, comment("plan", "fast?", "render"), action_id="c2")
    board = act(board, comment("plan", "looks ok"), action_id="c3")
    board = act(board, link("why", "plan", "log", quote="render"))
    board = act(board, link("all", "plan", "log"))
    after = act(board, put("plan", "1. start\n2. read the cache\n3. write the cache\n4. show"))
    assert {k: v.occurrence for k, v in after.threads.items()} == {"c1": 1, "c3": 0}
    assert list(after.arrows) == ["all"]
    assert after.history["plan"][-1] == Version(card=board.cards["plan"], threads={"c2": board.threads["c2"]})
    later = act(after, put("plan", "1. start\n2. show"))
    assert list(later.threads) == ["c3"]
    assert list(later.history["plan"][-1].threads) == ["c1"]


def test_an_arrow_follows_its_words_across_a_put() -> None:
    """Assemble: a card that shows "parse" at two places, with an arrow from the second to another card.
    Act: put the card with a line before the second "parse" and the first gone.
    Assert: the arrow stays, at the only place left."""
    board = act(act(Board(), put("a", "1. parse\n2. parse fast")), put("b", "x"))
    board = act(board, link("why", "a", "b", quote="parse", occurrence=1))
    after = act(board, put("a", "1. read\n2. parse fast"))
    assert after.arrows == {"why": Arrow(card="a", quote="parse", occurrence=0, dst="b", text="", author=Author.user)}


def test_a_put_of_the_same_markdown_keeps_all_the_threads() -> None:
    """Assemble: a card with a thread on it and on its words.
    Act: put the card with the same markdown.
    Assert: the threads are unchanged, and the version in the history has none."""
    board = act(act(Board(), put("a", "1. x")), comment("a", "hi"), action_id="c1")
    board = act(board, comment("a", "why", "x"), action_id="c2")
    after = act(board, put("a", "1. x"))
    assert after.threads == board.threads
    assert after.history["a"] == (Version(card=board.cards["a"]),)


@given(card_ids(), card_ids(), st.lists(item_texts(), min_size=1, unique=True), st.from_type(Author), st.data())
def test_link_draws_an_arrow_from_words_to_a_card_and_unlink_removes_it(
    card_id: str, arrow_id: str, texts: list[str], author: Author, data: st.DataObject
) -> None:
    """Assemble: a board with a card of a list.
    Act: link from its words or the card to itself, then unlink the arrow.
    Assert: the board has the arrow, then none."""
    board = act(Board(), put(card_id, list_md("1. ", texts)))
    quote = data.draw(st.sampled_from(["", *texts]).filter(lambda q: len(places(board.cards[card_id].md, q)) == 1))
    linked = act(board, link(arrow_id, card_id, card_id, quote=quote), author)
    assert linked.arrows == {arrow_id: Arrow(card=card_id, quote=quote, dst=card_id, text="", author=author)}
    assert act(linked, unlink(arrow_id)).arrows == {}


def test_a_relabel_keeps_the_place_of_the_arrow() -> None:
    """Assemble: an arrow from the second place of "x".
    Act: link it again with new text and no occurrence.
    Assert: the arrow keeps its place."""
    board = act(Board(), put("a", "1. x\n2. x"))
    board = act(board, link("why", "a", "a", quote="x", occurrence=1))
    assert act(board, link("why", "a", "a", "blocks", quote="x")).arrows["why"].occurrence == 1


@given(card_ids())
def test_unlink_of_no_arrow_raises(arrow_id: str) -> None:
    """Assemble: an empty board.
    Act: unlink an arrow.
    Assert: ValueError."""
    with pytest.raises(ValueError):
        act(Board(), unlink(arrow_id))


@pytest.mark.parametrize(
    ("body", "stay"), [(put("a", "1. y"), ["ba", "bb"]), (remove("a"), ["bb"])], ids=["put", "remove"]
)
def test_put_or_remove_drops_the_arrows_at_the_words_it_changes(body: TBody, stay: list[str]) -> None:
    """Assemble: a board with arrows from words of card a to card b, within b, and from b to card a.
    Act: put card a with the words changed, or remove card a.
    Assert: the put keeps the arrow within b and the one to card a; the remove keeps only the one within b."""
    board = act(act(Board(), put("a", "1. x")), put("b", "1. x"))
    for arrow_id, card_id, quote, dst in ("ab", "a", "x", "b"), ("ba", "b", "x", "a"), ("bb", "b", "", "b"):
        board = act(board, link(arrow_id, card_id, dst, quote=quote))
    assert list(act(board, body).arrows) == stay


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (remove("risk"), "no card 'risk': the cards are plan"),
        (comment("risk", "why?", "parse"), "no card 'risk': the cards are plan"),
        (
            comment("plan", "why?", "cache"),
            "card 'plan' does not show the words 'cache': quote its text without markdown",
        ),
        (
            comment("plan", "why?", "parse"),
            "card 'plan' shows 'parse' at 2 places: give the occurrence, from 0, or quote more words",
        ),
        (comment("plan", "why?", "parse", 2), "card 'plan' shows 'parse' at 2 places, so occurrence is 0 to 1"),
        (link("why", "plan", "risk", quote="render"), "no card 'risk': the cards are plan"),
        (
            link("why", "plan", "plan", quote="nope"),
            "card 'plan' does not show the words 'nope': quote its text without markdown",
        ),
        (unlink("why"), "no arrow 'why'"),
    ],
    ids=lambda value: value.kind if isinstance(value, Model) else "",
)
def test_an_action_that_does_not_fit_raises_with_the_valid_choices(body: TBody, reason: str) -> None:
    """Assemble: a board with card plan, which shows "parse" at two places.
    Act: apply an action that names a card, words or a place that the board does not have.
    Assert: ValueError whose message names what the board has instead, in one line."""
    board = act(Board(), put("plan", "1. parse\n2. render\n3. parse again"))
    with pytest.raises(ValueError, match=f"^{re.escape(reason)}$"):
        act(board, body)


def test_an_action_on_an_empty_board_says_it_has_no_cards() -> None:
    """Assemble: an empty board.
    Act: remove a card.
    Assert: ValueError says that the board has no cards."""
    with pytest.raises(ValueError, match=r"^no card 'a': the board has no cards$"):
        act(Board(), remove("a"))
