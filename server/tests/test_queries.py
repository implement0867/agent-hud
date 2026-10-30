import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agent_hud.models.actions import Action, Author
from agent_hud.models.board import Board
from agent_hud.models.cursor import ReadCursor
from agent_hud.models.draft import Draft
from agent_hud.models.events import Turn, TurnAction
from agent_hud.queries.boards import (
    add_board,
    check_board_exists,
    count_cards_of_each_board,
    list_board_names,
    load_board,
    load_draft,
    remove_board,
    save_board,
    save_draft,
)
from agent_hud.queries.cursors import load_cursor, save_cursor
from agent_hud.queries.turns import add_turn, list_turns, remove_turns
from tests.factories import make_comment, make_post, make_put


def test_the_queries_add_list_and_remove_boards(engine: Engine) -> None:
    """Act: add two boards, add one of them again, and remove the other.
    Assert: both names are listed and exist; ValueError for the name in use; and the removed board is gone with its cursor."""
    with Session(engine) as session:
        add_board(session, "one")
        add_board(session, "two")
        session.commit()
        assert set(list_board_names(session)) == {"one", "two"}
        assert check_board_exists(session, "one") and not check_board_exists(session, "three")
        with pytest.raises(ValueError, match="a board 'one' exists"):
            add_board(session, "one")
        remove_board(session, "two")
        session.commit()
        assert (list_board_names(session), check_board_exists(session, "two")) == (["one"], False)
        assert load_cursor(session, "one") == ReadCursor()


def test_a_new_board_is_empty_and_each_saved_record_loads_again(engine: Engine) -> None:
    """Assemble: a new board.
    Act: save a board with a card, a draft with a make_comment, and a cursor, and load each in a new session.
    Assert: the new board, draft and cursor are empty, and each loads as saved."""
    board = Board().apply_action(Action(id="a", author=Author.agent, body=make_put("plan", "1. a")))
    heard = TurnAction(id="r", author=Author.user, body=make_comment("plan", "yes", "a"))
    cursor = ReadCursor(unread_cards=frozenset({"plan"}), read_message_count=2)
    with Session(engine) as session:
        add_board(session, "plan")
        session.commit()
        assert (load_board(session, "plan"), load_draft(session, "plan")) == (Board(), Draft())
        save_board(session, "plan", board)
        save_draft(session, "plan", Draft(actions=(heard,)))
        save_cursor(session, "plan", cursor)
        session.commit()
    with Session(engine) as session:
        assert (load_board(session, "plan"), load_draft(session, "plan"), load_cursor(session, "plan")) == (
            board,
            Draft(actions=(heard,)),
            cursor,
        )


def test_the_card_counts_come_from_the_database(engine: Engine) -> None:
    """Assemble: a board with two cards and an empty board.
    Act: count the cards of each board.
    Assert: two and zero, by name."""
    with Session(engine) as session:
        add_board(session, "full")
        add_board(session, "empty")
        board = Board().apply_actions([Action(id=n, author=Author.agent, body=make_put(n, "1. a")) for n in ["a", "b"]])
        save_board(session, "full", board)
        session.commit()
        assert count_cards_of_each_board(session) == {"full": 2, "empty": 0}


def test_turns_wait_in_order_until_removed_and_go_with_their_board(engine: Engine) -> None:
    """Assemble: a board with two turns.
    Act: list the turns, remove the first, then remove the board.
    Assert: both turns oldest first, then the second alone, then none."""
    turns = [Turn(id="one", actions=(make_post("one"),)), Turn(id="two", actions=(make_post("two"),))]
    with Session(engine) as session:
        add_board(session, "plan")
        add_turn(session, "plan", turns[0])
        add_turn(session, "plan", turns[1])
        session.commit()
        assert list_turns(session, "plan") == turns
        remove_turns(session, "plan", {"one"})
        assert list_turns(session, "plan") == turns[1:]
        remove_board(session, "plan")
        session.commit()
        assert list_turns(session, "plan") == []


def test_a_session_keeps_only_what_it_committed(engine: Engine) -> None:
    """Assemble: a committed board.
    Act: add a second board without a commit, and close the session.
    Assert: a new session has the first board alone."""
    with Session(engine) as session:
        add_board(session, "plan")
        session.commit()
    with Session(engine) as session:
        add_board(session, "lost")
    with Session(engine) as session:
        assert list_board_names(session) == ["plan"]
