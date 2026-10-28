from difflib import unified_diff
from typing import Self, assert_never

from pydantic import Field

from agent_hud.models.actions import (
    Action,
    Author,
    Clear,
    Comment,
    Link,
    Move,
    Place,
    Put,
    Remove,
    Resize,
    Restore,
    Say,
    Send,
    TActionId,
    TCardId,
    Unlink,
)
from agent_hud.models.base import Model
from agent_hud.models.board import Board
from agent_hud.models.events import Edit, Heard, Turn


def make_heard(board: Board, action: Action) -> Heard:
    """Make the action as the agent hears it, given the board before it: a put that replaces a card becomes a diff."""
    match action.body:
        case Put(id=card_id, md=md) if card_id in board.cards:
            diff_lines = unified_diff(board.cards[card_id].md.splitlines(), md.splitlines(), lineterm="", n=1)
            body = Edit(kind="edit", id=card_id, diff="\n".join(list(diff_lines)[2:]))
        case (
            Put()
            | Remove()
            | Restore()
            | Comment()
            | Say()
            | Link()
            | Unlink()
            | Move()
            | Resize()
            | Place()
            | Clear()
            | Send()
        ):
            body = action.body
        case _:
            assert_never(action.body)
    return Heard(id=action.id, author=action.author, body=body)


class BoardState(Model):
    """A board, and what the agent has not had of it."""

    board: Board = Field(default_factory=Board)
    open_turn: tuple[Heard, ...] = Field(
        default=(), description="The user's actions since the last send, as the agent will hear them"
    )
    sent_turns: tuple[Turn, ...] = Field(default=(), description="The turns that the user sent and no agent has had")
    unread_cards: frozenset[TCardId] = Field(
        default=frozenset(), description="The cards that changed since the agent last read them"
    )
    read_messages: int = Field(default=0, description="The number of the board's messages that the agent has read")

    def apply_action(self, action: Action) -> Self:
        """Apply the action to the board and to what the agent has not had. ValueError when it does not fit the board."""
        board = self.board.apply(action)
        open_turn, sent_turns = self.open_turn, self.sent_turns
        match action.author, action.body:
            case Author.user, Send():
                open_turn, sent_turns = (), (*sent_turns, Turn.of(action.id, open_turn))
            case Author.user, Say():
                open_turn, sent_turns = (
                    (),
                    (*sent_turns, Turn.of(action.id, (*open_turn, make_heard(self.board, action)))),
                )
            case Author.user, Move() | Resize() | Place():
                pass
            case Author.user, Put() | Remove() | Restore() | Comment() | Link() | Unlink() | Clear():
                open_turn = (*open_turn, make_heard(self.board, action))
            case Author.agent, _:
                pass
            case unknown:
                assert_never(unknown)
        unread_cards, read_messages = self.unread_cards, self.read_messages
        match action.body:
            case Clear():
                unread_cards, read_messages = frozenset[TCardId](), 0
            case (
                Put(id=card_id)
                | Remove(id=card_id)
                | Restore(id=card_id)
                | Move(id=card_id)
                | Resize(id=card_id)
                | Place(id=card_id)
                | Comment(card=card_id)
            ):
                unread_cards = unread_cards | {card_id}
            case Link(card=card_id, dst=dst):
                unread_cards = unread_cards | {card_id, dst}
            case Say() | Unlink() | Send():
                pass
            case _:
                assert_never(action.body)
        return self.model_copy(
            update={
                "board": board,
                "open_turn": open_turn,
                "sent_turns": sent_turns,
                "unread_cards": unread_cards,
                "read_messages": read_messages,
            }
        )

    def mark_read(self, cards: frozenset[TCardId]) -> Self:
        """Mark the cards and every message as read by the agent."""
        return self.model_copy(
            update={"unread_cards": self.unread_cards - cards, "read_messages": len(self.board.messages)}
        )

    def remove_turns(self, turn_ids: set[TActionId]) -> Self:
        """Remove the sent turns with the ids, which the agents have had."""
        return self.model_copy(
            update={"sent_turns": tuple(turn for turn in self.sent_turns if turn.id not in turn_ids)}
        )
