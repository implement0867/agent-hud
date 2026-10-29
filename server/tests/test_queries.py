import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agent_hud.models.actions import Action, Author
from agent_hud.models.state import BoardState
from agent_hud.queries.boards import add_board, commit_board_state, list_board_names, load_board_state, remove_board
from tests.factories import comment, put, send


def test_the_queries_add_list_and_remove_boards(engine: Engine) -> None:
    """Act: add two boards, add one of them again, and remove the other.
    Assert: both names are listed; ValueError for the name in use; and the removed board is no longer listed."""
    with Session(engine) as session:
        add_board(session, "one")
        add_board(session, "two")
        session.commit()
        assert set(list_board_names(session)) == {"one", "two"}
        with pytest.raises(ValueError, match="a board 'one' exists"):
            add_board(session, "one")
        remove_board(session, "two")
        session.commit()
        assert list_board_names(session) == ["one"]


def test_a_committed_state_loads_again(engine: Engine) -> None:
    """Assemble: a board, and a state with a card, a sent turn and a comment the user has not sent.
    Act: commit the state, and load the board's state in a new session.
    Assert: the loaded state is the committed state."""
    with Session(engine) as session:
        add_board(session, "plan")
        session.commit()
    state = BoardState().apply_actions(
        [
            Action(id="a", author=Author.agent, body=put("plan", "1. a")),
            Action(id="s", author=Author.user, body=send()),
            Action(id="r", author=Author.user, body=comment("plan", "yes", "a")),
        ]
    )
    with Session(engine) as session:
        commit_board_state(session, "plan", state)
    with Session(engine) as session:
        assert load_board_state(session, "plan") == state


def test_a_session_keeps_only_what_it_committed(engine: Engine) -> None:
    """Assemble: a committed board.
    Act: add a second board without a commit, and close the session.
    Assert: a new session loads only the first board, with its empty state."""
    with Session(engine) as session:
        add_board(session, "plan")
        session.commit()
    with Session(engine) as session:
        add_board(session, "lost")
    with Session(engine) as session:
        assert (list_board_names(session), load_board_state(session, "plan")) == (["plan"], BoardState())
