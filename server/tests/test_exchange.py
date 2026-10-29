import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.exchange import Exchange, Monitor
from agent_hud.models.actions import Action, ActionKind, Author, Misfit, TBody
from agent_hud.models.events import AgentState, Edit, Turn
from agent_hud.models.state import BoardState
from tests.factories import BOARD, clear, comment, link, move, place, put, resize, say, send
from tests.strategies import actions, item_texts, list_md, messages


@given(st.lists(actions(st.sampled_from(["a", "b"])), min_size=1))
def test_apply_actions_takes_all_the_actions_or_none(batch: list[Action]) -> None:
    """Act: apply any batch of actions to a new state.
    Assert: the board has every action, or, on ValueError, nothing changed."""
    expected = BoardState().board
    try:
        for action in batch:
            expected = expected.apply(action)
    except ValueError:
        with pytest.raises(ValueError):
            BoardState().apply_actions(batch)
    else:
        assert BoardState().apply_actions(batch).board == expected


def test_apply_actions_names_the_action_that_does_not_fit() -> None:
    """Act: apply a put, a comment on words that the card does not show, and a say.
    Assert: Misfit with the index and kind of the second action and the board's reason, which in a batch says that no action was applied."""
    batch = [put("plan", "1. a"), comment("plan", "why?", "b"), say("hi")]
    reason = "card 'plan' does not show the words 'b': quote its text without markdown"
    with pytest.raises(Misfit, match=f"^{re.escape(reason)}$") as info:
        BoardState().apply_actions([Action(id=str(n), author=Author.agent, body=body) for n, body in enumerate(batch)])
    assert (info.value.index, info.value.kind) == (2, ActionKind.comment)
    assert info.value.in_batch() == f"action 2 (comment): {reason}; no actions were applied"


def said(texts: list[str], author: Author, batch: str = "") -> list[Action]:
    """Make a message of each text, each with an id of its own in the batch."""
    return [Action(id=f"{batch}{author}{n}", author=author, body=say(text)) for n, text in enumerate(texts)]


def by(author: Author, *bodies: TBody) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=body) for n, body in enumerate(bodies)]


def turns(actions: list[Action]) -> list[Turn]:
    """Make a turn of each of the actions, as the user's messages make them."""
    return [Turn(id=action.id, actions=(action.body,)) for action in actions]


def deliver_turns(exchange: Exchange, monitor: Monitor, state: BoardState) -> tuple[list[Turn], BoardState]:
    """
    Deliver the sent turns not yet delivered to the monitor, as the agent socket does, and return them with the state
    without the turns that every open monitor has.
    """
    delivered = [turn for turn in state.sent_turns if turn.id not in monitor.delivered]
    for turn in delivered:
        exchange.mark_delivered(monitor, turn)
    return delivered, state.remove_turns(exchange.find_turns_delivered_to_all(state))


@given(st.lists(messages(), min_size=1), st.lists(messages(), min_size=1), st.lists(messages(), min_size=1))
def test_a_monitor_gets_the_user_turns_that_no_monitor_had(
    first: list[str], agent_texts: list[str], rest: list[str]
) -> None:
    """Assemble: a state whose monitor got the user's first messages, then more messages by both authors.
    Act: the monitor takes the turns again.
    Assert: it gets a turn of each of the user's messages after the first, in order."""
    exchange = Exchange(BOARD)
    with exchange.open_monitor() as monitor:
        state = BoardState().apply_actions(said(first, Author.user))
        delivered, state = deliver_turns(exchange, monitor, state)
        assert delivered == turns(said(first, Author.user))
        state = state.apply_actions([*said(agent_texts, Author.agent), *said(rest, Author.user, "rest")])
        assert deliver_turns(exchange, monitor, state)[0] == turns(said(rest, Author.user, "rest"))


def test_each_open_monitor_gets_each_turn() -> None:
    """Assemble: an exchange with two open monitors.
    Act: the user says a message; the first monitor takes the turn, then the second.
    Assert: both get the turn, and it stays in the sent turns until the second has had it."""
    exchange = Exchange(BOARD)
    state = BoardState().apply_actions(said(["one"], Author.user))
    with exchange.open_monitor() as first, exchange.open_monitor() as second:
        [turn], state = deliver_turns(exchange, first, state)
        assert state.sent_turns == (turn,)
        delivered, state = deliver_turns(exchange, second, state)
        assert (delivered, state.sent_turns) == ([turn], ())


def test_a_turn_leaves_out_the_moves_resizes_and_places() -> None:
    """Assemble: a state with the agent's card.
    Act: in the turn, the user comments, moves, places and resizes the card, comments again, and sends.
    Assert: the open turn and the sent turn carry the comments alone, which read has the places and sizes for."""
    state = BoardState().apply_actions(by(Author.agent, put("plan", "1. a\n2. b")))
    turn = [
        Action(id="n1", author=Author.user, body=comment("plan", "why?", "a")),
        Action(id="n2", author=Author.user, body=move("plan", 5, 5)),
        Action(id="n3", author=Author.user, body=place("plan", 6, 6)),
        Action(id="n4", author=Author.user, body=resize("plan", 500, 300)),
        Action(id="n5", author=Author.user, body=comment("plan", "and?", "b")),
    ]
    state = state.apply_actions(turn)
    expected = ["n1", "n5"]
    assert [heard.id for heard in state.open_turn] == expected
    state = state.apply_actions([Action(id="e", author=Author.user, body=send())])
    assert state.sent_turns == (Turn(id="e", actions=tuple(action.body for action in turn if action.id in expected)),)


@given(st.lists(item_texts(), min_size=2, unique=True), messages())
def test_a_turn_is_sent_when_the_user_sends(texts: list[str], text: str) -> None:
    """Assemble: a state with the agent's list.
    Act: the user comments on the card and on an item, and moves the card, the agent puts a new list, then the user sends.
    Assert: no turn before the send, then one turn of the user's actions but the move."""
    state = BoardState().apply_actions(by(Author.agent, put("plan", list_md("1. ", ["first-item", *texts]))))
    feedback = by(Author.user, comment("plan", text), comment("plan", text, "first-item"), move("plan", 0, 0))
    state = state.apply_actions(feedback).apply_actions(by(Author.agent, put("plan", "1. new")))
    assert state.sent_turns == ()
    state = state.apply_actions([Action(id="end", author=Author.user, body=send())])
    assert state.sent_turns == (Turn(id="end", actions=tuple(action.body for action in feedback[:2])),)


def test_the_snapshot_tells_the_page_the_agents_state_and_the_unsent_actions() -> None:
    """Assemble: a new exchange.
    Act: open a monitor, the user comments and moves, the user sends and the monitor gets the turn, the agent writes, then the monitor ends.
    Assert: the state goes away, waiting, working until the agent writes, waiting, away; the unsent count leaves out moves and goes to 0 on the send."""
    exchange = Exchange(BOARD)
    state = BoardState().apply_actions(by(Author.agent, put("plan", "1. a")))
    assert (exchange.take_snapshot(state).agent, exchange.take_snapshot(state).unsent) == (AgentState.away, 0)
    with exchange.open_monitor() as monitor:
        assert exchange.take_snapshot(state).agent is AgentState.waiting
        state = state.apply_actions(by(Author.user, comment("plan", "ok", "a"), move("plan", 1, 1)))
        assert exchange.take_snapshot(state).unsent == 1
        state = state.apply_actions([Action(id="end", author=Author.user, body=send())])
        assert (exchange.take_snapshot(state).agent, exchange.take_snapshot(state).unsent) == (AgentState.waiting, 0)
        assert exchange.take_snapshot(state).waiting == 1
        _, state = deliver_turns(exchange, monitor, state)
        assert (exchange.take_snapshot(state).agent, exchange.take_snapshot(state).waiting) == (AgentState.working, 0)
        exchange.working = False
        assert exchange.take_snapshot(state).agent is AgentState.waiting
    assert exchange.take_snapshot(state).agent is AgentState.away


@given(st.lists(item_texts(), min_size=4, max_size=4, unique=True))
def test_the_turn_carries_an_edit_of_a_card_as_a_diff(texts: list[str]) -> None:
    """Assemble: a state with the agent's list of three items.
    Act: the user puts the list with a new second item, puts a new note, and sends.
    Assert: the turn has the edit as a diff of the changed line with one line around it, and the new note in full."""
    first, second, third, new = texts
    state = BoardState().apply_actions(by(Author.agent, put("plan", list_md("1. ", [first, second, third]))))
    state = state.apply_actions(
        by(Author.user, put("plan", list_md("1. ", [first, new, third])), put("note", new), send())
    )
    [turn] = state.sent_turns
    diff = "\n".join(["@@ -1,3 +1,3 @@", f" 1. {first}", f"-1. {second}", f"+1. {new}", f" 1. {third}"])
    assert list(turn.actions) == [Edit(kind="edit", id="plan", diff=diff), put("note", new)]


def test_the_unread_cards_are_the_cards_changed_since_the_last_read() -> None:
    """Assemble: a state with four cards that the agent read, where the agent then puts one, the user comments on another, links the third to it and moves the fourth, and says a message.
    Act: mark the first two cards read; then clear the board.
    Assert: all four cards are unread before the mark, the last two after it, and none after the clear; each mark reads every message, and the clear starts the messages again."""
    state = BoardState().apply_actions(
        by(Author.agent, put("a", "1. a"), put("b", "1. b"), put("c", "1. c"), put("d", "1. d"))
    )
    state = state.mark_read(frozenset(state.board.cards))
    state = state.apply_actions([Action(id="p", author=Author.agent, body=put("a", "1. a2"))])
    state = state.apply_actions(
        [
            Action(id="f", author=Author.user, body=comment("b", "why?", "b")),
            Action(id="l", author=Author.user, body=link("arrow", "c", "b", quote="c")),
            Action(id="m", author=Author.user, body=move("d", 1, 1)),
            Action(id="s", author=Author.user, body=say("look")),
        ]
    )
    assert state.unread_cards == {"a", "b", "c", "d"}
    state = state.mark_read(frozenset({"a", "b"}))
    assert (state.unread_cards, state.read_message_count) == ({"c", "d"}, len(state.board.messages))
    state = state.apply_actions([Action(id="clear", author=Author.agent, body=clear())])
    assert (state.unread_cards, state.read_message_count) == (frozenset(), 0)
