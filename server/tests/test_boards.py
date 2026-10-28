import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from agent_hud.boards import BoardSummary
from agent_hud.models.events import AgentState


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
