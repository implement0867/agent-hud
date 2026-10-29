import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agent_hud.exchange import Exchange
from agent_hud.models.actions import Action, Author
from agent_hud.models.state import BoardState
from agent_hud.queries.boards import add_board, list_board_names, load_board_state, remove_board, save_exchange
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


def test_a_saved_exchange_loads_again(engine: Engine) -> None:
    """Assemble: a board whose exchange has a card, a sent turn and a comment the user has not sent.
    Act: save the exchange, and load the board's state in a new session.
    Assert: the loaded state is the exchange's state."""
    with Session(engine) as session:
        add_board(session, "plan")
        session.commit()
        exchange = Exchange("plan", load_board_state(session, "plan"))
    exchange.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    exchange.act([Action(id="s", author=Author.user, body=send())])
    exchange.act([Action(id="r", author=Author.user, body=comment("plan", "yes", "a"))])
    with Session(engine) as session:
        save_exchange(session, exchange)
    with Session(engine) as session:
        assert load_board_state(session, "plan") == exchange.state


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
