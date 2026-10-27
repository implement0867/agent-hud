from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from agent_hud.boards import BoardSummary, open_boards
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, Author
from agent_hud.models.events import AgentState
from tests.factories import put


@given(st.from_regex(r"[A-Za-z0-9_-]{1,64}", fullmatch=True))
def test_a_slug_is_a_board_name(name: str) -> None:
    """Act: a board summary with a name of 1 to 64 letters, digits, _ or -.
    Assert: the summary keeps the name."""
    assert BoardSummary(name=name, cards=0, agent=AgentState.away).name == name


@pytest.mark.parametrize("text", ["", "a/b", "has space", "x" * 65, "../shared"])
def test_a_board_name_rejects_other_text(text: str) -> None:
    """Act: a board summary with a name that is not 1 to 64 letters, digits, _ or -.
    Assert: ValidationError."""
    with pytest.raises(ValidationError, match="String should match pattern"):
        BoardSummary.model_validate({"name": text, "cards": 0, "agent": AgentState.away})


def test_open_boards_opens_each_state_file_of_the_directory_by_its_name(tmp_path: Path) -> None:
    """Assemble: two boards' state files in a directory, one with a card.
    Act: open the boards of the directory.
    Assert: a hud for each file, by its stem, and the card on its board."""
    one = Hud(tmp_path / "one.db")
    one.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    one.close()
    Hud(tmp_path / "two.db").close()
    boards = open_boards(tmp_path)
    assert list(boards) == ["one", "two"] and list(boards["one"].board.cards) == ["plan"]
    for hud in boards.values():
        hud.close()


def test_open_boards_refuses_a_file_whose_stem_is_not_a_board_name(tmp_path: Path) -> None:
    """Assemble: a state file whose stem has a space.
    Act: open the boards of the directory.
    Assert: ValidationError, so that no board is left out without a word."""
    Hud(tmp_path / "has space.db").close()
    with pytest.raises(ValidationError):
        open_boards(tmp_path)
