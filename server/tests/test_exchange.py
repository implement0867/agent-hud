import asyncio
import re
from contextlib import aclosing

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
async def test_act_takes_all_the_actions_or_none(batch: list[Action]) -> None:
    """Assemble: a new exchange.
    Act: act with any batch of actions.
    Assert: the board has every action, or, on ValueError, the state is as it was."""
    exchange = Exchange(BOARD, BoardState())
    expected = exchange.board
    try:
        for action in batch:
            expected = expected.apply(action)
    except ValueError:
        with pytest.raises(ValueError):
            exchange.act(batch)
        assert exchange.state == BoardState()
    else:
        exchange.act(batch)
        assert exchange.board == expected


def test_act_names_the_action_that_does_not_fit() -> None:
    """Assemble: a new exchange.
    Act: act with a put, a comment on words that the card does not show, and a say.
    Assert: Misfit with the index and kind of the second action and the board's reason, which in a batch says that no action was applied."""
    batch = [put("plan", "1. a"), comment("plan", "why?", "b"), say("hi")]
    reason = "card 'plan' does not show the words 'b': quote its text without markdown"
    exchange = Exchange(BOARD, BoardState())
    with pytest.raises(Misfit, match=f"^{re.escape(reason)}$") as info:
        exchange.act([Action(id=str(n), author=Author.agent, body=body) for n, body in enumerate(batch)])
    assert (info.value.index, info.value.kind) == (2, ActionKind.comment)
    assert info.value.in_batch() == f"action 2 (comment): {reason}; no actions were applied"


def said(texts: list[str], author: Author) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=say(text)) for n, text in enumerate(texts)]


def turns(actions: list[Action]) -> list[Turn]:
    """A turn of each of the actions, as the user's messages make them."""
    return [Turn(id=action.id, actions=(action.body,)) for action in actions]


async def take(exchange: Exchange, count: int, seconds: float = 1) -> list[Turn]:
    """Take the first turns through a new monitor on the exchange. TimeoutError if fewer come in the seconds."""
    with exchange.open_monitor() as monitor:
        return await take_through(exchange, monitor, count, seconds)


async def take_through(exchange: Exchange, monitor: Monitor, count: int, seconds: float = 1) -> list[Turn]:
    """
    Take the first turns as the monitor does: wait for each, then mark it had.
    TimeoutError if fewer come in the seconds.
    """
    taken: list[Turn] = []
    async with aclosing(exchange.wait_for_turns(monitor)) as turns, asyncio.timeout(seconds):
        while len(taken) < count:
            taken.append(await anext(turns))
            exchange.mark_delivered(monitor, taken[-1])
    return taken


@given(st.lists(messages(), min_size=1), st.lists(messages(), min_size=1), st.lists(messages(), min_size=1))
async def test_an_agent_gets_the_user_actions_that_no_agent_had(
    first: list[str], agent_texts: list[str], rest: list[str]
) -> None:
    """Assemble: an exchange whose first agent got the user's first messages, then more messages by both authors.
    Act: an agent takes the turns again.
    Assert: it gets a turn of each of the user's messages after the first, in order."""
    exchange = Exchange(BOARD, BoardState())
    exchange.act(said(first, Author.user))
    assert await take(exchange, len(first)) == turns(said(first, Author.user))
    exchange.act([*said(agent_texts, Author.agent), *said(rest, Author.user)])
    assert await take(exchange, len(rest)) == turns(said(rest, Author.user))


async def test_a_turn_comes_again_until_a_monitor_has_had_it(exchange: Exchange) -> None:
    """Assemble: an exchange where the user sent a turn.
    Act: a monitor gets the turn and ends before it marks it had; then another monitor takes the turns.
    Assert: the second monitor gets the same turn, and the turn is then gone from the sent turns."""
    exchange.act(said(["one"], Author.user))
    with exchange.open_monitor() as monitor:
        async with aclosing(exchange.wait_for_turns(monitor)) as waiting:
            first = await anext(waiting)
    assert await take(exchange, 1) == [first]
    assert exchange.state.sent_turns == ()


async def test_each_open_monitor_gets_each_turn(exchange: Exchange) -> None:
    """Assemble: an exchange with two open monitors.
    Act: the user says a message; the first monitor takes the turn, then the second.
    Assert: both get the turn, and it stays in the sent turns until the second has had it."""
    with exchange.open_monitor() as first, exchange.open_monitor() as second:
        exchange.act(said(["one"], Author.user))
        [turn] = await take_through(exchange, first, 1)
        assert exchange.state.sent_turns == (turn,)
        assert await take_through(exchange, second, 1) == [turn]
        assert exchange.state.sent_turns == ()


async def test_a_turn_leaves_out_the_moves_resizes_and_places(exchange: Exchange) -> None:
    """Assemble: an exchange with the agent's card,
    Act: in the turn, the user comments, moves, places and resizes the card, comments again, and sends.
    Assert: the pending list and the turn carry the comments alone, which read has the places and sizes for."""
    exchange.act(by(Author.agent, put("plan", "1. a\n2. b")))
    turn = [
        Action(id="n1", author=Author.user, body=comment("plan", "why?", "a")),
        Action(id="n2", author=Author.user, body=move("plan", 5, 5)),
        Action(id="n3", author=Author.user, body=place("plan", 6, 6)),
        Action(id="n4", author=Author.user, body=resize("plan", 500, 300)),
        Action(id="n5", author=Author.user, body=comment("plan", "and?", "b")),
    ]
    exchange.act(turn)
    expected = ["n1", "n5"]
    assert [heard.id for heard in exchange.take_snapshot().pending] == expected
    assert exchange.take_snapshot().unsent == len(expected)
    exchange.act([Action(id="e", author=Author.user, body=send())])
    [heard] = await take(exchange, 1)
    assert heard.actions == tuple(action.body for action in turn if action.id in expected)


def by(author: Author, *bodies: TBody) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=body) for n, body in enumerate(bodies)]


@given(st.lists(item_texts(), min_size=2, unique=True), messages())
async def test_the_agent_gets_the_users_actions_when_the_user_sends(texts: list[str], text: str) -> None:
    """Assemble: an exchange with the agent's list.
    Act: the user comments on the card and on an item, and moves the card, the agent puts a new list, then the user sends.
    Assert: the agent gets nothing before the send, then one turn of the user's actions but the move."""
    exchange = Exchange(BOARD, BoardState())
    exchange.act(by(Author.agent, put("plan", list_md("1. ", ["first-item", *texts]))))
    feedback = by(Author.user, comment("plan", text), comment("plan", text, "first-item"), move("plan", 0, 0))
    exchange.act(feedback)
    exchange.act(by(Author.agent, put("plan", "1. new")))
    with pytest.raises(TimeoutError):
        await take(exchange, 1, seconds=0.01)
    exchange.act([Action(id="end", author=Author.user, body=send())])
    assert await take(exchange, 1) == [Turn(id="end", actions=tuple(action.body for action in feedback[:2]))]


async def test_the_snapshot_tells_the_page_the_agents_state_and_the_unsent_actions(exchange: Exchange) -> None:
    """Assemble: a new exchange.
    Act: open a monitor, the user comments and moves, the user sends and the agent gets the turn, the agent writes, then the monitor ends.
    Assert: the state goes away, waiting, working until the agent writes, waiting, away; the unsent count leaves out moves and goes to 0 on the send."""
    exchange.act(by(Author.agent, put("plan", "1. a")))
    assert (exchange.take_snapshot().agent, exchange.take_snapshot().unsent) == (AgentState.away, 0)
    with exchange.open_monitor() as monitor:
        assert exchange.take_snapshot().agent is AgentState.waiting
        exchange.act(by(Author.user, comment("plan", "ok", "a"), move("plan", 1, 1)))
        assert exchange.take_snapshot().unsent == 1
        exchange.act([Action(id="end", author=Author.user, body=send())])
        assert (exchange.take_snapshot().agent, exchange.take_snapshot().unsent) == (AgentState.waiting, 0)
        assert exchange.take_snapshot().waiting == 1
        await take_through(exchange, monitor, 1)
        assert (exchange.take_snapshot().agent, exchange.take_snapshot().waiting) == (AgentState.working, 0)
        exchange.act(by(Author.agent, say("done")))
        assert exchange.take_snapshot().agent is AgentState.waiting
    assert exchange.take_snapshot().agent is AgentState.away


@given(st.lists(item_texts(), min_size=4, max_size=4, unique=True))
async def test_the_agent_hears_an_edit_of_a_card_as_a_diff(texts: list[str]) -> None:
    """Assemble: an exchange with the agent's list of three items.
    Act: the user puts the list with a new second item, puts a new note, and sends.
    Assert: the agent hears the edit as a diff of the changed line with one line around it, and the new note in full."""
    first, second, third, new = texts
    exchange = Exchange(BOARD, BoardState())
    exchange.act(by(Author.agent, put("plan", list_md("1. ", [first, second, third]))))
    exchange.act(by(Author.user, put("plan", list_md("1. ", [first, new, third])), put("note", new), send()))
    [turn] = await take(exchange, 1)
    diff = "\n".join(["@@ -1,3 +1,3 @@", f" 1. {first}", f"-1. {second}", f"+1. {new}", f" 1. {third}"])
    assert list(turn.actions) == [Edit(kind="edit", id="plan", diff=diff), put("note", new)]


def test_the_unread_cards_are_the_cards_changed_since_the_last_read(exchange: Exchange) -> None:
    """Assemble: an exchange with four cards that the agent read, where the agent then puts one, the user comments on another, links the third to it and moves the fourth, and says a message.
    Act: mark the first two cards read; then clear the board.
    Assert: all four cards are unread before the mark, the last two after it, and none after the clear; each mark reads every message, and the clear starts the messages again."""
    exchange.act(by(Author.agent, put("a", "1. a"), put("b", "1. b"), put("c", "1. c"), put("d", "1. d")))
    exchange.mark_read(frozenset(exchange.board.cards))
    exchange.act([Action(id="p", author=Author.agent, body=put("a", "1. a2"))])
    exchange.act(
        [
            Action(id="f", author=Author.user, body=comment("b", "why?", "b")),
            Action(id="l", author=Author.user, body=link("arrow", "c", "b", quote="c")),
            Action(id="m", author=Author.user, body=move("d", 1, 1)),
            Action(id="s", author=Author.user, body=say("look")),
        ]
    )
    assert exchange.state.unread_cards == {"a", "b", "c", "d"}
    exchange.mark_read(frozenset({"a", "b"}))
    assert (exchange.state.unread_cards, exchange.state.read_messages) == ({"c", "d"}, len(exchange.board.messages))
    exchange.act([Action(id="clear", author=Author.agent, body=clear())])
    assert (exchange.state.unread_cards, exchange.state.read_messages) == (frozenset(), 0)
