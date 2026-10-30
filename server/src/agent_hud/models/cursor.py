from typing import Self, assert_never

from pydantic import Field

from agent_hud.models.actions import (
    Action,
    Clear,
    Comment,
    Link,
    Move,
    Place,
    Post,
    Put,
    Remove,
    Resize,
    Restore,
    Send,
    TCardId,
    Unlink,
)
from agent_hud.models.base import Model


class ReadCursor(Model):
    """What the agent has not read of its board."""

    unread_cards: frozenset[TCardId] = Field(
        default=frozenset(), description="The cards that changed since the agent last read them"
    )
    read_message_count: int = Field(default=0, description="How many of the board's messages the agent has read")

    def note_action(self, action: Action) -> Self:
        """The cursor with the cards that the action changed unread; a clear starts the board again."""
        match action.body:
            case Clear():
                return self.model_copy(update={"unread_cards": frozenset[TCardId](), "read_message_count": 0})
            case (
                Put(id=card_id)
                | Remove(id=card_id)
                | Restore(id=card_id)
                | Move(id=card_id)
                | Resize(id=card_id)
                | Place(id=card_id)
                | Comment(card=card_id)
            ):
                return self.model_copy(update={"unread_cards": self.unread_cards | {card_id}})
            case Link(card=card_id, dst=dst):
                return self.model_copy(update={"unread_cards": self.unread_cards | {card_id, dst}})
            case Post() | Unlink() | Send():
                return self
            case _:
                assert_never(action.body)

    def mark_read(self, cards: frozenset[TCardId], message_count: int) -> Self:
        """The cursor after the agent read the cards and the board's messages, of which there are message_count."""
        return self.model_copy(update={"unread_cards": self.unread_cards - cards, "read_message_count": message_count})
