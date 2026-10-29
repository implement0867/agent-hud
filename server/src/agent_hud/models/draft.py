from difflib import unified_diff
from typing import Self, assert_never

from agent_hud.models.actions import (
    Action,
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
    Unlink,
)
from agent_hud.models.base import Model
from agent_hud.models.board import Board
from agent_hud.models.events import Edit, Heard, Turn


class Draft(Model):
    """The user's turn so far: the actions since the last send, as the agent's monitor will get them."""

    heard: tuple[Heard, ...] = ()

    def take(self, board: Board, action: Action) -> Self | Turn:
        """
        The draft with the user's action, or the turn that the action ends. A move, a resize or a place changes nothing,
        since read has the layout; a put on a card of the board, which is the board before the action, is a diff.
        """
        match action.body:
            case Send():
                return Turn.of(action.id, self.heard)
            case Say():
                return Turn.of(action.id, (*self.heard, Heard(id=action.id, author=action.author, body=action.body)))
            case Move() | Resize() | Place():
                return self
            case Put(id=card_id, md=md) if card_id in board.cards:
                lines = unified_diff(board.cards[card_id].md.splitlines(), md.splitlines(), lineterm="", n=1)
                edit = Edit(kind="edit", id=card_id, diff="\n".join(list(lines)[2:]))
                return self.model_copy(
                    update={"heard": (*self.heard, Heard(id=action.id, author=action.author, body=edit))}
                )
            case Put() | Remove() | Restore() | Comment() | Link() | Unlink() | Clear():
                heard = Heard(id=action.id, author=action.author, body=action.body)
                return self.model_copy(update={"heard": (*self.heard, heard)})
            case _:
                assert_never(action.body)
