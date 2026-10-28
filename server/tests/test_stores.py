from collections.abc import Iterator

import pytest
from sqlalchemy import Engine

from agent_hud.exchange import Exchange
from agent_hud.models.actions import Action, Author
from agent_hud.models.state import BoardState
from agent_hud.store import Store
from agent_hud.stores.memory import MemoryStore
from agent_hud.stores.sql import open_sql_store
from tests.factories import comment, put, send


@pytest.fixture(params=["sql", "memory"])
def each_store(request: pytest.FixtureRequest, engine: Engine) -> Iterator[Store]:
    """Each kind of store, new for each test."""
    match request.param:
        case "sql":
            with open_sql_store(engine) as store:
                yield store
        case "memory":
            yield MemoryStore()
        case other:
            raise ValueError(f"no store of the kind {other}")


def test_a_store_adds_lists_and_removes_boards(each_store: Store) -> None:
    """Act: add two boards, add one of them again, and remove the other.
    Assert: both names are listed; ValueError for the name in use; and the removed board is no longer listed."""
    each_store.add_board("one")
    each_store.add_board("two")
    each_store.commit()
    assert set(each_store.list_board_names()) == {"one", "two"}
    with pytest.raises(ValueError, match="a board 'one' exists"):
        each_store.add_board("one")
    each_store.remove_board("two")
    assert each_store.list_board_names() == ["one"]


def test_a_store_loads_the_state_that_it_saved(each_store: Store) -> None:
    """Assemble: a board whose state has a card, a sent turn and a comment the user has not sent.
    Act: save the state, commit, and load it.
    Assert: the loaded state is the saved state."""
    each_store.add_board("plan")
    exchange = Exchange(each_store.load_board_state("plan"))
    exchange.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    exchange.act([Action(id="s", author=Author.user, body=send())])
    exchange.act([Action(id="r", author=Author.user, body=comment("plan", "yes", "a"))])
    each_store.save_board_state("plan", exchange.state)
    each_store.commit()
    assert each_store.load_board_state("plan") == exchange.state


def test_the_sql_store_keeps_only_what_it_committed(engine: Engine) -> None:
    """Assemble: a committed board.
    Act: save a new state without a commit, and close the store.
    Assert: a new store loads the empty state."""
    with open_sql_store(engine) as store:
        store.add_board("plan")
        store.commit()
    with open_sql_store(engine) as store:
        exchange = Exchange(store.load_board_state("plan"))
        exchange.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
        store.save_board_state("plan", exchange.state)
    with open_sql_store(engine) as store:
        assert store.load_board_state("plan") == BoardState()
