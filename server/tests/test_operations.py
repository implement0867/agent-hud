import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from agent_hud.models.actions import Action, Author, Misfit
from agent_hud.models.board import Board
from agent_hud.models.draft import Draft
from agent_hud.models.events import Turn, TurnAction
from agent_hud.operations import BoardChange, apply_agent_actions, apply_user_action
from agent_hud.queries.boards import load_board, load_draft
from agent_hud.queries.cursors import load_cursor
from agent_hud.queries.turns import list_turns
from tests.factories import BOARD, StoredBoard, make_comment, make_put, make_send


def test_a_user_action_joins_the_draft_until_a_send_makes_it_a_turn(engine: Engine, board: StoredBoard) -> None:
    """Assemble: a board with the agent's card.
    Act: the user comments, then sends.
    Assert: the comment is in the draft and the card is unread; the send empties the draft and the turn waits in the database."""
    board.apply_actions([Action(id="a", author=Author.agent, body=make_put("plan", "1. a"))])
    with Session(engine) as session:
        remark = Action(id="r", author=Author.user, body=make_comment("plan", "yes", "a"))
        heard = TurnAction(id="r", author=Author.user, body=remark.body)
        assert apply_user_action(session, BOARD, remark) == Draft(actions=(heard,))
        assert (load_draft(session, BOARD), load_cursor(session, BOARD).unread_cards) == (
            Draft(actions=(heard,)),
            {"plan"},
        )
        assert apply_user_action(session, BOARD, Action(id="s", author=Author.user, body=make_send())) == Turn(
            id="s", actions=(remark.body,)
        )
        assert (load_draft(session, BOARD), list_turns(session, BOARD)) == (
            Draft(),
            [Turn(id="s", actions=(remark.body,))],
        )
        assert len(load_board(session, BOARD).threads) == 1


def test_a_user_action_that_does_not_fit_changes_nothing(engine: Engine, board: StoredBoard) -> None:
    """Act: the user comments on a card that is not on the board.
    Assert: ValueError, and the board, the draft and the cursor are as they were."""
    with Session(engine) as session, pytest.raises(ValueError, match="plan"):
        apply_user_action(session, BOARD, Action(id="r", author=Author.user, body=make_comment("plan", "yes")))
    with Session(engine) as session:
        assert (load_board(session, BOARD), load_draft(session, BOARD), load_cursor(session, BOARD).unread_cards) == (
            Board(),
            Draft(),
            frozenset(),
        )


def test_the_agents_actions_are_applied_all_or_none(engine: Engine, board: StoredBoard) -> None:
    """Act: the agent puts a card and comments on it in one write, then writes a put and a comment that does not fit.
    Assert: the first write returns the board before and after, both cards unread; the second raises Misfit for its second action and changes nothing."""
    with Session(engine) as session:
        first = [
            Action(id="a", author=Author.agent, body=make_put("plan", "1. a")),
            Action(id="c", author=Author.agent, body=make_comment("plan", "note", "a")),
        ]
        change = apply_agent_actions(session, BOARD, first)
        assert change == BoardChange(Board(), Board().apply_actions(first))
        assert load_cursor(session, BOARD).unread_cards == {"plan"}
        second = [
            Action(id="b", author=Author.agent, body=make_put("b", "1. b")),
            Action(id="d", author=Author.agent, body=make_comment("b", "x", "zzz")),
        ]
        with pytest.raises(Misfit) as info:
            apply_agent_actions(session, BOARD, second)
        assert info.value.index == 2
    with Session(engine) as session:
        assert (load_board(session, BOARD), load_cursor(session, BOARD).unread_cards) == (change.after, {"plan"})
