import asyncio
import re
import sqlite3
from contextlib import aclosing, closing, suppress
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from agent_hud.boards import exchange_on_file
from agent_hud.exchange import ChangesSince, Exchange, changes_since, to_agent_message
from agent_hud.models.actions import Action, ActionKind, Author, Misfit, TBody
from agent_hud.models.board import Board
from agent_hud.models.events import AgentState, Edit, THeardBody, Turn
from agent_hud.store import SqliteStore
from tests.factories import clear, comment, link, memory_exchange, move, place, put, resize, say, send
from tests.strategies import actions, item_texts, list_md, messages


@given(st.lists(actions(st.sampled_from(["a", "b"])), min_size=1))
async def test_act_takes_all_the_actions_or_none(batch: list[Action]) -> None:
    """Assemble: a new exchange.
    Act: act with any batch of actions.
    Assert: the board and log have every action, or, on ValueError, are as they were."""
    with closing(memory_exchange()) as exchange:
        expected = exchange.board
        try:
            for action in batch:
                expected = expected.apply(action)
        except ValueError:
            with pytest.raises(ValueError):
                exchange.act(batch)
            assert (exchange.board, exchange.actions) == (Board(), [])
        else:
            exchange.act(batch)
            assert (exchange.board, exchange.actions) == (expected, batch)


def test_act_names_the_action_that_does_not_fit() -> None:
    """Assemble: a new exchange.
    Act: act with a put, a comment on words that the card does not show, and a say.
    Assert: Misfit with the index and kind of the second action and the board's reason, which in a batch says that no action was applied."""
    batch = [put("plan", "1. a"), comment("plan", "why?", "b"), say("hi")]
    reason = "card 'plan' does not show the words 'b': quote its text without markdown"
    with pytest.raises(Misfit, match=f"^{re.escape(reason)}$") as info, closing(memory_exchange()) as exchange:
        exchange.act([Action(id=str(n), author=Author.agent, body=body) for n, body in enumerate(batch)])
    assert (info.value.index, info.value.kind) == (2, ActionKind.comment)
    assert info.value.in_batch() == f"action 2 (comment): {reason}; no actions were applied"


def said(texts: list[str], author: Author) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=say(text)) for n, text in enumerate(texts)]


def turns(actions: list[Action]) -> list[Turn]:
    """A turn of each of the actions, as the user's messages make them."""
    return [Turn(id=action.id, actions=(action.body,)) for action in actions]


async def take(exchange: Exchange, count: int, seconds: float = 1) -> list[Turn]:
    """The first turns an agent gets from the exchange. TimeoutError if fewer come in the seconds."""
    taken: list[Turn] = []
    async with aclosing(exchange.user_turns()) as user_turns:
        async with asyncio.timeout(seconds):
            while len(taken) < count:
                taken.append(await anext(user_turns))
        # A turn counts as had once the agent asks for the next, so ask for the turns that are there now.
        with suppress(TimeoutError):
            async with asyncio.timeout(0):
                while True:
                    taken.append(await anext(user_turns))
    return taken


@given(st.lists(messages(), min_size=1), st.lists(messages(), min_size=1), st.lists(messages(), min_size=1))
async def test_an_agent_gets_the_user_actions_that_no_agent_had(
    first: list[str], agent_texts: list[str], rest: list[str]
) -> None:
    """Assemble: an exchange whose first agent got the user's first messages and stopped, then more messages by both authors.
    Act: a second agent follows the exchange.
    Assert: it gets a turn of each of the user's messages after the first, in order."""
    with closing(memory_exchange()) as exchange:
        exchange.act(said(first, Author.user))
        assert await take(exchange, len(first)) == turns(said(first, Author.user))
        exchange.act([*said(agent_texts, Author.agent), *said(rest, Author.user)])
        assert await take(exchange, len(rest)) == turns(said(rest, Author.user))


def plain(action: Action) -> bool:
    """Whether a turn carries the action as it is: not a clear, which compacts the state file, nor a kind a turn leaves out."""
    nets = (ActionKind.clear, ActionKind.move, ActionKind.resize, ActionKind.place)
    return action.body.kind not in nets


# Each example writes and reads a state file, so its time varies more than the default deadline allows.
@given(st.lists(actions(st.sampled_from(["a", "b"])).filter(plain)), messages())
@settings(deadline=None)
async def test_an_exchange_on_the_state_file_takes_up_where_the_last_left_off(batch: list[Action], text: str) -> None:
    """Assemble: an exchange on a state file that took each action that fits, with no agent to take the turns.
    Act: start a new exchange on the same file, and the user says a message.
    Assert: the new exchange has the same board and log, and an agent gets each turn that no agent had, then the message's."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        exchange = exchange_on_file(state_file)
        # The user's actions of each turn as the agent hears them, without the sends; the last turn once it is sent.
        expected: list[list[THeardBody]] = [[]]
        for action in batch:
            heard = to_agent_message(exchange.board, action).body
            with suppress(ValueError):
                exchange.act([action])
                if action.author is Author.user and action.body.kind is not ActionKind.send:
                    expected[-1].append(heard)
                if action.ends_turn:
                    expected.append([])
        exchange.close()
        again = exchange_on_file(state_file)
        assert (again.board, again.actions) == (exchange.board, exchange.actions)
        again.act(said([text], Author.user))
        expected[-1].append(say(text))
        taken = await take(again, len(expected))
        assert [list(turn.actions) for turn in taken] == expected
        again.close()


async def test_the_read_position_survives_a_restart() -> None:
    """Assemble: an exchange on a state file where the user sent two turns with no agent, then acted on.
    Act: start a new exchange on the file, and an agent takes the turns; then start another, and compact.
    Assert: the first new exchange's agent gets both turns, the second's gets none, and the compacted file holds the user's turn alone."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        exchange = exchange_on_file(state_file)
        exchange.act(by(Author.agent, put("plan", "1. a")))
        exchange.act([Action(id="one", author=Author.user, body=say("one"))])
        exchange.act(
            [
                Action(id="r", author=Author.user, body=comment("plan", "yes", "a")),
                Action(id="two", author=Author.user, body=say("two")),
            ]
        )
        exchange.act([Action(id="late", author=Author.user, body=comment("plan", "and", "a"))])
        exchange.close()
        again = exchange_on_file(state_file)
        assert again.snapshot().waiting == 2
        assert [list(turn.actions) for turn in await take(again, 2)] == [
            [say("one")],
            [comment("plan", "yes", "a"), say("two")],
        ]
        assert again.snapshot().waiting == 0
        again.close()
        third = exchange_on_file(state_file)
        assert third.snapshot().waiting == 0
        with pytest.raises(TimeoutError):
            await take(third, 1, seconds=0.01)
        third.compact()
        third.close()
        fourth = exchange_on_file(state_file)
        assert [action.id for action in fourth.actions] == ["late"]
        assert fourth.board == exchange.board
        fourth.close()


def test_one_process_holds_the_state_file() -> None:
    """Assemble: an exchange on a state file.
    Act: start another exchange on the same file, as a second uvicorn worker would; then close the first and start another.
    Assert: the second raises RuntimeError that names the file and says one process, and the third starts."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        exchange = exchange_on_file(state_file)
        with pytest.raises(RuntimeError, match=f"{re.escape(str(state_file))}.*one process"):
            exchange_on_file(state_file)
        exchange.close()
        exchange_on_file(state_file).close()


async def test_a_turn_counts_as_had_once_the_agent_asks_for_the_next(exchange: Exchange) -> None:
    """Assemble: an exchange where the user sent a turn.
    Act: an agent gets the turn and its monitor ends before it asks for the next; then another agent follows.
    Assert: the second agent gets the same turn."""
    exchange.act(said(["one"], Author.user))
    async with aclosing(exchange.user_turns()) as user_turns:
        first = await anext(user_turns)
    assert await take(exchange, 1) == [first]


async def test_a_turn_leaves_out_the_moves_resizes_and_places(exchange: Exchange) -> None:
    """Assemble: an exchange with the agent's card, whose last turn an agent took.
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
    assert [heard.id for heard in exchange.snapshot().pending] == expected
    assert exchange.snapshot().unsent == len(expected)
    exchange.act([Action(id="e", author=Author.user, body=send())])
    [heard] = await take(exchange, 1)
    assert heard.actions == tuple(action.body for action in turn if action.id in expected)


@given(batch=st.lists(actions(st.sampled_from(["a", "b"]))), on_clear=st.booleans())
@settings(deadline=None)
async def test_an_exchange_on_a_compacted_state_file_takes_up_where_the_last_left_off(
    *, batch: list[Action], on_clear: bool
) -> None:
    """Assemble: an exchange on a state file that took each action that fits, whose turns an agent took, compacted by the user's clear or by compact.
    Act: start a new exchange on the same file.
    Assert: the checkpoint holds the board at the start of the user's turn, the file holds the turn alone, and the
    new exchange has the same board and the same unsent actions."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        exchange = exchange_on_file(state_file)
        for action in batch:
            with suppress(ValueError):
                exchange.act([action])
        if sent := sum(action.ends_turn for action in exchange.actions):
            await take(exchange, sent)
        if on_clear:
            exchange.act([Action(id="c", author=Author.user, body=clear())])
        else:
            exchange.compact()
        start = max((n + 1 for n, action in enumerate(exchange.actions) if action.ends_turn), default=0)
        at_start = Board()
        for action in exchange.actions[:start]:
            at_start = at_start.apply(action)
        exchange.close()
        store = SqliteStore(state_file)
        _, checkpoint, kept, _ = store.load()
        store.close()
        assert (checkpoint, kept) == (at_start, exchange.actions[start:])
        turn = exchange_on_file(state_file)
        assert turn.actions == exchange.actions[start:]
        assert turn.board == exchange.board
        assert turn.snapshot().unsent == exchange.snapshot().unsent
        turn.close()


def by(author: Author, *bodies: TBody) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=body) for n, body in enumerate(bodies)]


@given(st.lists(item_texts(), min_size=2, unique=True), messages())
async def test_the_agent_gets_the_users_actions_when_the_user_sends(texts: list[str], text: str) -> None:
    """Assemble: an exchange with the agent's list.
    Act: the user comments on the card and on an item, and moves the card, the agent puts a new list, then the user sends.
    Assert: the agent gets nothing before the send, then one turn of the user's actions but the move."""
    with closing(memory_exchange()) as exchange:
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
    assert (exchange.snapshot().agent, exchange.snapshot().unsent) == (AgentState.away, 0)
    with exchange.monitor():
        assert exchange.snapshot().agent is AgentState.waiting
        exchange.act(by(Author.user, comment("plan", "ok", "a"), move("plan", 1, 1)))
        assert exchange.snapshot().unsent == 1
        exchange.act([Action(id="end", author=Author.user, body=send())])
        assert (exchange.snapshot().agent, exchange.snapshot().unsent) == (AgentState.waiting, 0)
        assert exchange.snapshot().waiting == 1
        await take(exchange, 1)
        assert (exchange.snapshot().agent, exchange.snapshot().waiting) == (AgentState.working, 0)
        exchange.act(by(Author.agent, say("done")))
        assert exchange.snapshot().agent is AgentState.waiting
    assert exchange.snapshot().agent is AgentState.away


@given(st.lists(item_texts(), min_size=4, max_size=4, unique=True))
async def test_the_agent_hears_an_edit_of_a_card_as_a_diff(texts: list[str]) -> None:
    """Assemble: an exchange with the agent's list of three items.
    Act: the user puts the list with a new second item, puts a new note, and sends.
    Assert: the agent hears the edit as a diff of the changed line with one line around it, and the new note in full."""
    first, second, third, new = texts
    with closing(memory_exchange()) as exchange:
        exchange.act(by(Author.agent, put("plan", list_md("1. ", [first, second, third]))))
        exchange.act(by(Author.user, put("plan", list_md("1. ", [first, new, third])), put("note", new), send()))
        [turn] = await take(exchange, 1)
        diff = "\n".join(["@@ -1,3 +1,3 @@", f" 1. {first}", f"-1. {second}", f"+1. {new}", f" 1. {third}"])
        assert list(turn.actions) == [Edit(kind="edit", id="plan", diff=diff), put("note", new)]


def test_changes_since_names_the_cards_the_later_actions_touched_and_their_ids(exchange: Exchange) -> None:
    """Assemble: an exchange with four cards, where after the user's send the agent puts one, the user comments on another and links the third to it, and the user moves a card.
    Act: ask what changed since the send, since an id the log does not have, and since the send after a clear.
    Assert: the cards put, commented on, linked and moved with the ids of those actions; None for the unknown id; and no cards, which means all, after the clear."""
    exchange.act(by(Author.agent, put("a", "1. a"), put("b", "1. b"), put("c", "1. c"), put("d", "1. d")))
    exchange.act([Action(id="turn", author=Author.user, body=send())])
    exchange.act([Action(id="p", author=Author.agent, body=put("a", "1. a2"))])
    exchange.act(
        [
            Action(id="f", author=Author.user, body=comment("b", "why?", "b")),
            Action(id="l", author=Author.user, body=link("arrow", "c", "b", quote="c")),
            Action(id="m", author=Author.user, body=move("d", 1, 1)),
        ]
    )
    assert changes_since(exchange.actions, "turn") == ChangesSince({"a", "b", "c", "d"}, {"p", "f", "l", "m"})
    assert changes_since(exchange.actions, "f") == ChangesSince({"c", "b", "d"}, {"l", "m"})
    assert changes_since(exchange.actions, "nope") is None
    exchange.act(
        [Action(id="clear", author=Author.agent, body=clear()), Action(id="s", author=Author.agent, body=say("hi"))]
    )
    assert changes_since(exchange.actions, "turn") == ChangesSince(None, {"p", "f", "l", "m", "clear", "s"})


def test_an_exchange_on_a_state_file_of_an_earlier_version_does_not_start() -> None:
    """Assemble: a state file whose checkpoint and actions are of an earlier agent-hud, with values, widths and reactions.
    Act: start an exchange on it.
    Assert: ValidationError, and the file is as it was and free for another process."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        SqliteStore(state_file).close()
        old_board = '{"cards": {"plan": {"md": "1. a", "author": "agent"}}, "values": {"plan/1/2": 3}, "widths": {}}'
        old_action = '{"id": "r", "author": "user", "body": {"kind": "react", "ref": "plan/1", "reaction": "approve"}}'
        with sqlite3.connect(state_file) as db:
            db.execute("UPDATE checkpoint SET board = ?", (old_board,))
            db.execute("INSERT INTO actions (seq, action) VALUES (0, ?)", (old_action,))
        db.close()
        with pytest.raises(ValidationError):
            exchange_on_file(state_file)
        with closing(sqlite3.connect(state_file)) as db:
            assert db.execute("SELECT board FROM checkpoint").fetchone() == (old_board,)
