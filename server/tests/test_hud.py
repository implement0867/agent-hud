import asyncio
import re
from contextlib import aclosing, suppress
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_hud.hud import Hud
from agent_hud.models.actions import Action, ActionKind, Author, Misfit, Reaction, TBody
from agent_hud.models.board import Board
from agent_hud.models.events import AgentState, Edit, Heard, Turn
from agent_hud.store import Store
from tests.factories import clear, comment, fill, move, place, put, react, say, send, unreact
from tests.strategies import actions, item_texts, list_md, messages, table_md


@given(st.builds(Hud), st.lists(actions(st.sampled_from(["a", "b"])), min_size=1))
async def test_act_takes_all_the_actions_or_none(hud: Hud, batch: list[Action]) -> None:
    """Assemble: a new hud.
    Act: act with any batch of actions.
    Assert: the board and log have every action, or, on ValueError, are as they were."""
    expected = hud.board
    try:
        for action in batch:
            expected = expected.apply(action)
    except ValueError:
        with pytest.raises(ValueError):
            hud.act(batch)
        assert (hud.board, hud.log.actions) == (Board(), [])
    else:
        hud.act(batch)
        assert (hud.board, hud.log.actions) == (expected, batch)


def test_act_names_the_action_that_does_not_fit() -> None:
    """Assemble: a new hud.
    Act: act with a put, a react to a part that the card does not have, and a say.
    Assert: Misfit with the index and kind of the second action and the board's reason, which in a batch says that no action was applied."""
    batch = [put("plan", "1. a"), react("plan/2", Reaction.approve), say("hi")]
    reason = "no part 'plan/2': card 'plan' has parts 1 to 1"
    with pytest.raises(Misfit, match=f"^{re.escape(reason)}$") as info:
        Hud().act([Action(id=str(n), author=Author.agent, body=body) for n, body in enumerate(batch)])
    assert (info.value.index, info.value.kind) == (2, ActionKind.react)
    assert info.value.in_batch() == f"action 2 (react): {reason}; no actions were applied"


def said(texts: list[str], author: Author) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=say(text)) for n, text in enumerate(texts)]


def turns(actions: list[Action]) -> list[Turn]:
    """A turn of each of the actions, as the user's messages make them."""
    return [Turn(actions=(Heard(**action.model_dump(), parts={}),)) for action in actions]


async def take(hud: Hud, count: int, seconds: float = 1) -> list[Turn]:
    """The first turns an agent gets from the hud. TimeoutError if fewer come in the seconds."""
    taken: list[Turn] = []
    async with aclosing(hud.user_turns()) as user_turns:
        async with asyncio.timeout(seconds):
            while len(taken) < count:
                taken.append(await anext(user_turns))
        # A turn counts as had once the agent asks for the next, so ask for the turns that are there now.
        with suppress(TimeoutError):
            async with asyncio.timeout(0):
                while True:
                    taken.append(await anext(user_turns))
    return taken


@given(
    st.builds(Hud), st.lists(messages(), min_size=1), st.lists(messages(), min_size=1), st.lists(messages(), min_size=1)
)
async def test_an_agent_gets_the_user_actions_that_no_agent_had(
    hud: Hud, first: list[str], agent_texts: list[str], rest: list[str]
) -> None:
    """Assemble: a hud whose first agent got the user's first messages and stopped, then more messages by both authors.
    Act: a second agent follows the hud.
    Assert: it gets a turn of each of the user's messages after the first, in order."""
    hud.act(said(first, Author.user))
    assert await take(hud, len(first)) == turns(said(first, Author.user))
    hud.act([*said(agent_texts, Author.agent), *said(rest, Author.user)])
    assert await take(hud, len(rest)) == turns(said(rest, Author.user))


def plain(action: Action) -> bool:
    """Whether a turn carries the action as it is: not a clear, which compacts the state file, nor a kind a turn nets."""
    nets = (ActionKind.clear, ActionKind.move, ActionKind.place, ActionKind.react, ActionKind.unreact, ActionKind.fill)
    return action.body.kind not in nets


def turn_ids(actions: list[Action]) -> list[list[str]]:
    """The ids of the user's actions in each turn of the actions, without the sends; the last turn only if it is sent."""
    turns: list[list[str]] = [[]]
    for action in actions:
        if action.author is Author.user and action.body.kind is not ActionKind.send:
            turns[-1].append(action.id)
        if action.ends_turn:
            turns.append([])
    return turns[:-1]


# Each example writes and reads a state file, so its time varies more than the default deadline allows.
@given(st.lists(actions(st.sampled_from(["a", "b"])).filter(plain)), messages())
@settings(deadline=None)
async def test_a_hud_on_the_state_file_takes_up_where_the_last_left_off(batch: list[Action], text: str) -> None:
    """Assemble: a hud on a state file that took each action that fits, with no agent to take the turns.
    Act: start a new hud on the same file, and the user says a message.
    Assert: the new hud has the same board and log, and an agent gets each turn that no agent had, then the message's."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        hud = Hud(state_file)
        for action in batch:
            with suppress(ValueError):
                hud.act([action])
        hud.close()
        again = Hud(state_file)
        assert (again.board, again.log.actions) == (hud.board, hud.log.actions)
        again.act(said([text], Author.user))
        expected = turn_ids([*hud.log.actions, *said([text], Author.user)])
        taken = await take(again, len(expected))
        assert [[heard.id for heard in turn.actions] for turn in taken] == expected
        again.close()


async def test_the_read_position_survives_a_restart() -> None:
    """Assemble: a hud on a state file where the user sent two turns with no agent, then acted on.
    Act: start a new hud on the file, and an agent takes the turns; then start another, and compact.
    Assert: the first new hud's agent gets both turns, the second's gets none, and the compacted file holds the user's turn alone."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        hud = Hud(state_file)
        hud.act(by(Author.agent, put("plan", "1. a")))
        hud.act([Action(id="one", author=Author.user, body=say("one"))])
        hud.act(
            [
                Action(id="r", author=Author.user, body=react("plan/1", Reaction.approve)),
                Action(id="two", author=Author.user, body=say("two")),
            ]
        )
        hud.act([Action(id="late", author=Author.user, body=comment("plan/1", "and"))])
        hud.close()
        again = Hud(state_file)
        assert again.snapshot().waiting == 2
        assert [[heard.id for heard in turn.actions] for turn in await take(again, 2)] == [["one"], ["r", "two"]]
        assert again.snapshot().waiting == 0
        again.close()
        third = Hud(state_file)
        assert third.snapshot().waiting == 0
        with pytest.raises(TimeoutError):
            await take(third, 1, seconds=0.01)
        third.compact()
        third.close()
        fourth = Hud(state_file)
        assert [action.id for action in fourth.log.actions] == ["late"]
        assert fourth.board == hud.board
        fourth.close()


def test_one_process_holds_the_state_file() -> None:
    """Assemble: a hud on a state file.
    Act: start another hud on the same file, as a second uvicorn worker would; then close the first and start another.
    Assert: the second raises RuntimeError that names the file and says one process, and the third starts."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        hud = Hud(state_file)
        with pytest.raises(RuntimeError, match=f"{re.escape(str(state_file))}.*one process"):
            Hud(state_file)
        hud.close()
        Hud(state_file).close()


async def test_a_turn_counts_as_had_once_the_agent_asks_for_the_next() -> None:
    """Assemble: a hud where the user sent a turn.
    Act: an agent gets the turn and its monitor ends before it asks for the next; then another agent follows.
    Assert: the second agent gets the same turn."""
    hud = Hud()
    hud.act(said(["one"], Author.user))
    async with aclosing(hud.user_turns()) as user_turns:
        first = await anext(user_turns)
    assert await take(hud, 1) == [first]


@given(st.from_type(Reaction), st.from_type(Reaction))
async def test_a_turn_carries_the_net_of_the_users_actions(before: Reaction, after: Reaction) -> None:
    """Assemble: a hud with a card of a list and a table, where the user reacted to a part and filled a cell before their turn.
    Act: in the turn, the user reacts and unreacts, reacts twice, fills a cell twice, fills a cell back as it was, moves and places the card, and sends.
    Assert: the pending list and the turn carry the last reaction on a part when it differs from the start, the last fill of a cell when it differs, and no move or place."""
    hud = Hud()
    table = table_md([["x", "y"]], [" {number}", " {number}"])
    hud.act(by(Author.agent, put("plan", f"1. a\n2. b\n3. c\n\n{table}")))
    hud.act(
        [
            *by(Author.user, react("plan/1", before), fill("plan/4/1", 1)),
            Action(id="s", author=Author.user, body=send()),
        ]
    )
    await take(hud, 1)
    turn = [
        Action(id="n1", author=Author.user, body=react("plan/2", after)),
        Action(id="n2", author=Author.user, body=unreact("plan/2")),
        Action(id="n3", author=Author.user, body=react("plan/1", after)),
        Action(id="n4", author=Author.user, body=react("plan/3", before)),
        Action(id="n5", author=Author.user, body=react("plan/3", after)),
        Action(id="n6", author=Author.user, body=fill("plan/4/2", 2)),
        Action(id="n7", author=Author.user, body=fill("plan/4/2", 3)),
        Action(id="n8", author=Author.user, body=fill("plan/4/1", 2)),
        Action(id="n9", author=Author.user, body=fill("plan/4/1", 1)),
        Action(id="n10", author=Author.user, body=move("plan", 5, 5)),
        Action(id="n11", author=Author.user, body=place("plan", 6, 6)),
    ]
    hud.act(turn)
    expected = ([] if before == after else ["n3"]) + ["n5", "n7"]
    assert [heard.id for heard in hud.snapshot().pending] == expected
    assert hud.snapshot().unsent == len(expected)
    hud.act([Action(id="e", author=Author.user, body=send())])
    [heard] = await take(hud, 1)
    assert [action.id for action in heard.actions] == expected


@given(batch=st.lists(actions(st.sampled_from(["a", "b"]))), on_clear=st.booleans())
@settings(deadline=None)
async def test_a_hud_on_a_compacted_state_file_takes_up_where_the_last_left_off(
    *, batch: list[Action], on_clear: bool
) -> None:
    """Assemble: a hud on a state file that took each action that fits, whose turns an agent took, compacted by the user's clear or by compact.
    Act: start a new hud on the same file.
    Assert: the checkpoint holds the board at the start of the user's turn, the file holds the turn alone, and the
    new hud has the same board and the same unsent actions."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "board.db"
        hud = Hud(state_file)
        for action in batch:
            with suppress(ValueError):
                hud.act([action])
        if sent := sum(action.ends_turn for action in hud.log.actions):
            await take(hud, sent)
        if on_clear:
            hud.act([Action(id="c", author=Author.user, body=clear())])
        else:
            hud.compact()
        start = max((n + 1 for n, action in enumerate(hud.log.actions) if action.ends_turn), default=0)
        at_start = Board()
        for action in hud.log.actions[:start]:
            at_start = at_start.apply(action)
        hud.close()
        store = Store(state_file)
        _, checkpoint, kept, _ = store.load()
        store.close()
        assert (checkpoint, kept) == (at_start, hud.log.actions[start:])
        turn = Hud(state_file)
        assert turn.log.actions == hud.log.actions[start:]
        assert turn.board == hud.board
        assert turn.snapshot().unsent == hud.snapshot().unsent
        turn.close()


def by(author: Author, *bodies: TBody) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=body) for n, body in enumerate(bodies)]


@given(st.lists(item_texts(), min_size=2), st.from_type(Reaction), messages())
async def test_the_agent_gets_the_users_actions_when_the_user_sends(
    texts: list[str], reaction: Reaction, text: str
) -> None:
    """Assemble: a hud with the agent's list.
    Act: the user reacts, comments and moves the card, the agent puts a new list, then the user sends.
    Assert: the agent gets nothing before the send, then one turn of the user's actions but the move, with the text of each part as the user saw it."""
    hud = Hud()
    hud.act(by(Author.agent, put("plan", list_md("1. ", texts))))
    feedback = by(Author.user, react("plan/2", reaction), comment("plan/1", text), move("plan", 0, 0))
    hud.act(feedback)
    hud.act(by(Author.agent, put("plan", "1. new")))
    with pytest.raises(TimeoutError):
        await take(hud, 1, seconds=0.01)
    hud.act([Action(id="end", author=Author.user, body=send())])
    parts = [{"plan/2": texts[1]}, {"plan/1": texts[0]}]
    assert await take(hud, 1) == [
        Turn(actions=tuple(Heard(**a.model_dump(), parts=p) for a, p in zip(feedback[:2], parts, strict=True)))
    ]


async def test_the_snapshot_tells_the_page_the_agents_state_and_the_unsent_actions() -> None:
    """Assemble: a new hud.
    Act: open a monitor, the user reacts and moves, the user sends and the agent gets the turn, the agent writes, then the monitor ends.
    Assert: the state goes away, waiting, working until the agent writes, waiting, away; the unsent count leaves out moves and goes to 0 on the send."""
    hud = Hud()
    hud.act(by(Author.agent, put("plan", "1. a")))
    assert (hud.snapshot().agent, hud.snapshot().unsent) == (AgentState.away, 0)
    with hud.monitor():
        assert hud.snapshot().agent is AgentState.waiting
        hud.act(by(Author.user, react("plan/1", Reaction.approve), move("plan", 1, 1)))
        assert hud.snapshot().unsent == 1
        hud.act([Action(id="end", author=Author.user, body=send())])
        assert (hud.snapshot().agent, hud.snapshot().unsent) == (AgentState.waiting, 0)
        assert hud.snapshot().waiting == 1
        await take(hud, 1)
        assert (hud.snapshot().agent, hud.snapshot().waiting) == (AgentState.working, 0)
        hud.act(by(Author.agent, say("done")))
        assert hud.snapshot().agent is AgentState.waiting
    assert hud.snapshot().agent is AgentState.away


@given(st.lists(item_texts(), min_size=4, max_size=4, unique=True))
async def test_the_agent_hears_an_edit_of_a_card_as_a_diff(texts: list[str]) -> None:
    """Assemble: a hud with the agent's list of three items.
    Act: the user puts the list with a new second item, puts a new note, and sends.
    Assert: the agent hears the edit as a diff of the changed line with one line around it, and the new note in full."""
    first, second, third, new = texts
    hud = Hud()
    hud.act(by(Author.agent, put("plan", list_md("1. ", [first, second, third]))))
    hud.act(by(Author.user, put("plan", list_md("1. ", [first, new, third])), put("note", new), send()))
    [turn] = await take(hud, 1)
    diff = "\n".join(["@@ -1,3 +1,3 @@", f" 1. {first}", f"-1. {second}", f"+1. {new}", f" 1. {third}"])
    assert [heard.body for heard in turn.actions] == [Edit(kind="edit", id="plan", diff=diff), put("note", new)]
