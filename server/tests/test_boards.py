import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from sqlalchemy import Engine

from agent_hud.boards import BoardSummary
from agent_hud.exchange import Exchange
from agent_hud.models.actions import Action, Author
from agent_hud.models.events import AgentState
from agent_hud.queries.boards import add_board, remove_board, select_board_names
from agent_hud.store import SqlStore
from tests.factories import put


@given(st.from_regex(r"[A-Za-z0-9_-]{1,64}", fullmatch=True))
def test_a_slug_is_a_board_name(name: str) -> None:
    """Act: a board summary with a name of 1 to 64 letters, digits, _ or -.
    Assert: the summary keeps the name."""
    assert BoardSummary(name=name, card_count=0, agent=AgentState.away).name == name


@pytest.mark.parametrize("text", ["", "a/b", "has space", "x" * 65, "../shared"])
def test_a_board_name_rejects_other_text(text: str) -> None:
    """Act: a board summary with a name that is not 1 to 64 letters, digits, _ or -.
    Assert: ValidationError."""
    with pytest.raises(ValidationError, match="String should match pattern"):
        BoardSummary.model_validate({"name": text, "card_count": 0, "agent": AgentState.away})


def test_the_boards_are_the_rows_of_the_database(engine: Engine) -> None:
    """Assemble: two boards added out of order, one with a card.
    Act: list the board names, add a board whose name is in use, remove the board with the card, and add it again.
    Assert: the names; ValueError for the name in use; and the board added again has no actions."""
    add_board(engine, "two")
    add_board(engine, "one")
    Exchange(SqlStore(engine, "one")).act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    assert set(select_board_names(engine)) == {"one", "two"}
    with pytest.raises(ValueError, match="a board 'one' exists"):
        add_board(engine, "one")
    remove_board(engine, "one")
    assert select_board_names(engine) == ["two"]
    add_board(engine, "one")
    assert Exchange(SqlStore(engine, "one")).actions == []
