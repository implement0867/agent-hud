from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import assert_never

from sqlalchemy.orm import Session

from agent_hud.boards import BoardSummary, TBoardName
from agent_hud.models.actions import Action
from agent_hud.models.board import Board
from agent_hud.models.draft import Draft
from agent_hud.models.events import Turn
from agent_hud.presence import Presence
from agent_hud.queries.boards import count_cards_of_each_board, load_board, load_draft, save_board, save_draft
from agent_hud.queries.cursors import load_cursor, save_cursor
from agent_hud.queries.turns import add_turn


@dataclass(frozen=True)
class BoardChange:
    """The board before a write and after it."""

    before: Board
    after: Board


def apply_user_action(session: Session, name: TBoardName, action: Action) -> Draft | Turn:
    """
    Apply the user's action to the board, to the draft of the next turn and to the agent's cursor, and commit.
    ValueError when the action does not fit the board. The draft with the action, or the turn that the action ended.
    """
    board = load_board(session, name)
    save_board(session, name, board.apply_action(action))
    taken = load_draft(session, name).take_action(board, action)
    match taken:
        case Draft() as draft:
            save_draft(session, name, draft)
        case Turn() as turn:
            add_turn(session, name, turn)
            save_draft(session, name, Draft())
        case _:
            assert_never(taken)
    save_cursor(session, name, load_cursor(session, name).note_action(action))
    session.commit()
    return taken


def apply_agent_actions(session: Session, name: TBoardName, actions: Sequence[Action]) -> BoardChange:
    """
    Apply the agent's actions to the board, in order, all or nothing, and to its cursor, and commit.
    Misfit, with the index of the action, when one does not fit the board.
    """
    before = load_board(session, name)
    after = before.apply_actions(actions)
    cursor = load_cursor(session, name)
    for action in actions:
        cursor = cursor.note_action(action)
    save_board(session, name, after)
    save_cursor(session, name, cursor)
    session.commit()
    return BoardChange(before, after)


def list_board_summaries(session: Session, presences: defaultdict[TBoardName, Presence]) -> list[BoardSummary]:
    """Each board in the database with its card count, and the state of its agent from its presence."""
    return [
        BoardSummary(name=name, card_count=card_count, agent=presences[name].agent_state)
        for name, card_count in count_cards_of_each_board(session).items()
    ]
