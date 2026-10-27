from contextlib import closing
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from agent_hud.boards import BoardSummary, board_names, exchange_on_file, open_exchange
from agent_hud.exchange import Exchange
from agent_hud.models.actions import Action, Author
from agent_hud.models.events import AgentState
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


def test_the_boards_are_the_state_files_of_the_directory(tmp_path: Path) -> None:
    """Assemble: two boards' state files in a directory, one with a card.
    Act: list the board names, and open one board twice.
    Assert: the stem of each file, in order; one exchange for the board, with its card; and ValueError for a name that has
    no file."""
    one = exchange_on_file(tmp_path / "one.db")
    one.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    one.close()
    exchange_on_file(tmp_path / "two.db").close()
    assert board_names(tmp_path) == ["one", "two"]
    exchanges: dict[str, Exchange] = {}
    with closing(open_exchange(exchanges, tmp_path, "one")) as exchange:
        assert open_exchange(exchanges, tmp_path, "one") is exchange and list(exchange.board.cards) == ["plan"]
    with pytest.raises(ValueError, match="no board 'three': the boards are one, two"):
        open_exchange(exchanges, tmp_path, "three")


def test_a_file_whose_stem_is_not_a_board_name_is_an_error(tmp_path: Path) -> None:
    """Assemble: a state file whose stem has a space.
    Act: list the board names.
    Assert: ValidationError, so that no board is left out without a word."""
    exchange_on_file(tmp_path / "has space.db").close()
    with pytest.raises(ValidationError):
        board_names(tmp_path)
