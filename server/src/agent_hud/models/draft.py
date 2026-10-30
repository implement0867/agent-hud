from difflib import unified_diff
from typing import Self, assert_never

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
    Unlink,
)
from agent_hud.models.base import Model
from agent_hud.models.board import Board
from agent_hud.models.events import Edit, Turn, TurnAction, make_turn


class Draft(Model):
    """The user's turn so far: the actions since the last send, as the agent's monitor will get them."""

    actions: tuple[TurnAction, ...] = ()

    def take_action(self, board: Board, action: Action) -> Self | Turn:
        """
        The draft with the user's action, or the turn that the action ends. A move, a resize or a place changes nothing,
        since read has the layout; a put on a card of the board, which is the board before the action, is a diff.
        """
        match action.body:
            case Send():
                return make_turn(action.id, self.actions)
            case Post():
                return make_turn(
                    action.id, (*self.actions, TurnAction(id=action.id, author=action.author, body=action.body))
                )
            case Move() | Resize() | Place():
                return self
            case Put(id=card_id, md=md) if card_id in board.cards:
                lines = unified_diff(board.cards[card_id].md.splitlines(), md.splitlines(), lineterm="", n=1)
                edit = Edit(kind="edit", id=card_id, diff="\n".join(list(lines)[2:]))
                return self.model_copy(
                    update={"actions": (*self.actions, TurnAction(id=action.id, author=action.author, body=edit))}
                )
            case Put() | Remove() | Restore() | Comment() | Link() | Unlink() | Clear():
                heard = TurnAction(id=action.id, author=action.author, body=action.body)
                return self.model_copy(update={"actions": (*self.actions, heard)})
            case _:
                assert_never(action.body)
