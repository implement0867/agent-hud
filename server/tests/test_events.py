import pytest
from hypothesis import given
from pydantic import ValidationError

from agent_hud.models.events import EventKind, MessageSent
from tests.strategies import blanks


@given(blanks())
def test_a_sent_message_needs_a_character_that_is_not_white_space(blank: str) -> None:
    """Assemble: text of white space only, or no text.
    Act: make a MessageSent event of it.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        MessageSent(kind=EventKind.message_sent, message=blank)
