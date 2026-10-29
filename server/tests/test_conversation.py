from collections.abc import AsyncIterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import pytest_asyncio
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_hud.database import open_database
from agent_hud.models.actions import ActionKind, Author, TBody
from agent_hud.models.board import Arrow, Board, Point, Version
from agent_hud.models.events import Accepted, AgentState, Edit, EventKind, Rejected
from tests.conversation import Agent, User, open_agent, open_page, serve
from tests.factories import BOARD, as_json, comment, create_exchange, link, move, put, read_board, remove, say
from tests.strategies import bodies, card_ids

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(loop_scope="module")
async def agent(address: tuple[str, int]) -> AsyncIterator[Agent]:
    async with open_agent(address) as agent:
        yield agent


@pytest_asyncio.fixture(loop_scope="module")
async def user(address: tuple[str, int]) -> AsyncIterator[User]:
    async with open_page(address) as user:
        yield user


def kinds(answers: list[Accepted | Rejected]) -> list[EventKind]:
    return [answer.kind for answer in answers]


def feedback(board: Board | Version) -> dict[str, list[tuple[Author, str]]]:
    """The comments, by author and text, of each thread, by the words it is on."""
    return {thread.quote: [(said.author, said.text) for said in thread.comments] for thread in board.threads.values()}


async def test_the_agent_revises_a_plan_from_the_users_feedback(agent: Agent, user: User) -> None:
    """Assemble: the agent puts a plan of three steps and asks the user to review it.
    Act: the user comments on the words of two steps and sends; the agent answers a question, puts a new plan, and the user approves it with a message.
    Assert: after each turn the agent hears the user's actions in order and reads the board that the page shows, the chat has the messages and comments in order, the thread on the unchanged step stays, and the old plan has the rest in its history."""
    await agent.write(put("plan", "1. parse\n2. rewrite the cache\n3. render"), say("Review the plan"))
    board = await read_board(agent.tools, history=True)
    assert await user.sees(board) == board

    review = [
        comment("plan", "which parser?", "parse"),
        comment("plan", "the cache is shared", "rewrite the cache"),
        comment("plan", "render where?", "render"),
    ]
    assert kinds([await user.act(body) for body in review]) == [EventKind.accepted] * len(review)
    await user.send()
    assert await agent.hear() == review
    board = await read_board(agent.tools, history=True)
    assert feedback(board) == {
        "parse": [(Author.user, "which parser?")],
        "rewrite the cache": [(Author.user, "the cache is shared")],
        "render": [(Author.user, "render where?")],
    }

    await agent.write(comment("plan", "in the browser", "render"))
    board = board_before = await read_board(agent.tools, history=True)
    assert await user.sees(board) == board
    assert feedback(board)["render"] == [(Author.user, "render where?"), (Author.agent, "in the browser")]

    await agent.write(put("plan", "1. parse\n2. keep the cache\n3. show it"), say("I kept the cache"))
    board = await read_board(agent.tools, history=True)
    assert await user.sees(board) == board
    assert (feedback(board), [said.text for said in board.messages]) == (
        {"parse": [(Author.user, "which parser?")]},
        [
            "Review the plan",
            "which parser?",
            "the cache is shared",
            "render where?",
            "in the browser",
            "I kept the cache",
        ],
    )
    old = board.history["plan"][-1]
    assert (old.card.md, feedback(old)) == (
        "1. parse\n2. rewrite the cache\n3. render",
        {quote: found for quote, found in feedback(board_before).items() if quote != "parse"},
    )

    approval = [comment("plan", "looks good"), say("go ahead")]
    assert kinds([await user.act(body) for body in approval]) == [EventKind.accepted] * len(approval)
    assert await agent.hear() == approval
    assert feedback(await read_board(agent.tools, history=True)) == {
        "parse": [(Author.user, "which parser?")],
        "": [(Author.user, "looks good")],
    }


async def test_the_agent_hears_a_checked_box_as_an_edit(agent: Agent, user: User) -> None:
    """Assemble: the agent puts a table of tasks with a column of boxes.
    Act: the user checks the box of a task, as the page does, by a put of the markdown with the box checked.
    Assert: the agent hears the change as a diff of the markdown, and reads the card with the box checked."""
    table = "| | Task |\n|---|---|\n| [ ] | parse |\n| [ ] | render |"
    await agent.write(put("tasks", table))
    checked = table.replace("| [ ] | render |", "| [x] | render |")
    assert (await user.act(put("tasks", checked, 0))).kind is EventKind.accepted
    await user.send()
    diff = "@@ -3,2 +3,2 @@\n | [ ] | parse |\n-| [ ] | render |\n+| [x] | render |"
    assert await agent.hear() == [Edit(kind="edit", id="tasks", diff=diff)]
    board = await read_board(agent.tools, history=True)
    assert await user.sees(board) == board
    assert board.cards["tasks"].md == checked


async def test_the_user_and_the_agent_discuss_code_with_arrows(agent: Agent, user: User) -> None:
    """Assemble: the agent puts a code card, a card of options and a card of questions side by side, with an arrow from an option to the questions.
    Act: the user comments on an option, draws an arrow from a line of the code to the options and answers the question; then the agent removes the options.
    Assert: the agent hears and reads the user's arrow beside its own, and the page shows no arrow or thread on the options once they are gone."""
    await agent.write(
        put("code", "```python\ndef render(md: str) -> str:\n    return md\n```"),
        put("options", "1. highlight on the server\n2. highlight in the browser"),
        put("questions", "1. Which languages?"),
        link("decides", "options", "questions", quote="highlight in the browser"),
        move("code", 0, 0),
        move("options", 420, 0),
        move("questions", 840, 0),
    )
    board = await read_board(agent.tools, history=True)
    assert await user.sees(board) == board

    answer = [
        comment("options", "this one", "in the browser"),
        link("mine", "code", "options", quote="return md"),
        comment("questions", "all", "Which languages?"),
    ]
    assert kinds([await user.act(body) for body in answer]) == [EventKind.accepted] * len(answer)
    await user.send()
    assert await agent.hear() == answer
    board = await read_board(agent.tools, history=True)
    assert board.arrows == {
        "decides": Arrow(
            card="options", quote="highlight in the browser", dst="questions", text="", author=Author.agent
        ),
        "mine": Arrow(card="code", quote="return md", dst="options", text="", author=Author.user),
    }

    await agent.write(remove("options"), say("Highlighting goes in the browser"))
    board = await read_board(agent.tools, history=True)
    seen = await user.sees(board)
    assert seen == board
    assert (seen.arrows, list(feedback(seen))) == ({}, ["Which languages?"])


async def test_the_agent_hears_the_notes_and_edits_of_the_user(agent: Agent, user: User) -> None:
    """Assemble: a board with an agent's plan card and an arrow from it to the user's note.
    Act: the user writes a note, places it, edits the agent's card and then removes the note.
    Assert: the agent hears each action but the move, with the edit as a diff, and reads the user as the author of the note and the edited card as the agent's, edited, with its arrow gone."""
    note = [put("note", "Also check the docs"), move("note", 40, 300), say("see my note")]
    assert kinds([await user.act(body) for body in note]) == [EventKind.accepted] * len(note)
    assert await agent.hear() == [note[0], note[2]]
    board = await read_board(agent.tools, history=True)
    assert (board.cards["note"].author, board.positions) == (Author.user, {"note": Point(x=40, y=300)})

    await agent.write(put("plan", "1. read the docs\n2. write the code"), link("from", "plan", "note", quote="docs"))
    edits = [put("plan", "1. read the docs\n2. write the tests\n3. write the code"), remove("note")]
    assert kinds([await user.act(body) for body in edits]) == [EventKind.accepted] * len(edits)
    await user.send()
    diff = "@@ -1,2 +1,3 @@\n 1. read the docs\n-2. write the code\n+2. write the tests\n+3. write the code"
    assert await agent.hear() == [Edit(kind="edit", id="plan", diff=diff), remove("note")]
    board = await read_board(agent.tools, history=True)
    assert await user.sees(board) == board
    assert ({k: (v.author, v.edited) for k, v in board.cards.items()}, board.arrows) == (
        {"plan": (Author.agent, True)},
        {},
    )


async def test_a_comment_on_words_that_the_agent_just_removed_is_rejected(agent: Agent, user: User) -> None:
    """Assemble: the page shows a plan of three steps.
    Act: the agent puts a plan without step b, and the user comments on b, then on c.
    Assert: the board rejects the comment on b, the agent hears only the comment on c, and the page shows the new plan."""
    await agent.write(put("plan", "1. a\n2. b\n3. c"))
    assert "plan" in (await user.sees(await read_board(agent.tools, history=True))).cards

    await agent.write(put("plan", "1. a\n2. c"))
    stale = await user.act(comment("plan", "why?", "b"))
    assert stale == Rejected(
        kind=EventKind.rejected,
        id=stale.id,
        reason="card 'plan' does not show the words 'b': quote its text without markdown",
    )
    assert (await user.act(comment("plan", "why?", "c"))).kind is EventKind.accepted
    await user.send()
    assert await agent.hear() == [comment("plan", "why?", "c")]
    board = await read_board(agent.tools, history=True)
    assert await user.sees(board) == board


async def test_an_agent_monitor_gets_what_the_user_did_while_no_monitor_was_open(
    agent: Agent, user: User, address: tuple[str, int]
) -> None:
    """Assemble: the agent puts a plan, and its monitor ends.
    Act: the user comments and sends, reloads the page, and the agent opens a new monitor.
    Assert: the page shows that no agent listens, the new monitor gets the user's turn, and the new page shows the board that the agent reads."""
    await agent.write(put("plan", "1. a\n2. b"))
    await agent.monitor.close()
    assert (await user.notes(lambda snapshot: snapshot.agent is AgentState.away)).agent is AgentState.away

    missed = [comment("plan", "why a?", "a")]
    assert kinds([await user.act(body) for body in missed]) == [EventKind.accepted] * len(missed)
    await user.send()
    async with open_page(address) as reloaded, agent.listen():
        assert await agent.hear() == missed
        assert reloaded.board == await read_board(agent.tools, history=True)


async def test_the_page_shows_whose_turn_it_is(agent: Agent, user: User) -> None:
    """Assemble: an agent with a monitor and a plan on the board.
    Act: the user comments and sends; the agent answers; then the agent's monitor ends.
    Assert: the page shows one unsent action before the send, then the agent working, waiting after its answer, and away."""
    await agent.write(put("plan", "1. a"))
    assert (await user.notes(lambda snapshot: snapshot.agent is AgentState.waiting)).agent is AgentState.waiting
    await user.act(comment("plan", "fine", "a"))
    assert (await user.notes(lambda snapshot: snapshot.unsent == 1)).unsent == 1
    await user.send()
    await agent.hear()
    working = await user.notes(lambda snapshot: snapshot.agent is AgentState.working)
    assert (working.agent, working.unsent) == (AgentState.working, 0)
    await agent.write(say("a is fine"))
    assert (await user.notes(lambda snapshot: snapshot.agent is AgentState.waiting)).agent is AgentState.waiting
    await agent.monitor.close()
    assert (await user.notes(lambda snapshot: snapshot.agent is AgentState.away)).agent is AgentState.away


@st.composite
def turns(draw: st.DrawFn) -> list[tuple[Author, list[TBody]]]:
    """Turns of the user and the agent on one pool of card ids, each of one to three actions, so that some fit the board and some do not."""
    ids = st.sampled_from(draw(st.lists(card_ids(), min_size=1, max_size=3)))
    return draw(st.lists(st.tuples(st.from_type(Author), st.lists(bodies(ids), min_size=1, max_size=3)), max_size=8))


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(turns())
@settings(deadline=None, max_examples=50)
async def test_the_page_and_the_agent_agree_after_each_turn(
    static_dir: Path, state_dir: Path, turns: list[tuple[Author, list[TBody]]]
) -> None:
    """Assemble: a new board, a page and an agent with a monitor.
    Act: the user and the agent take turns; the page sends each of the user's actions alone, and the agent writes each turn in one call.
    Assert: after each turn the page shows the board that the agent reads, and after the user's last send the agent has heard each turn as the page listed it as pending, with the message that ended it, in order."""
    taken: list[TBody] = []
    with TemporaryDirectory() as directory:
        engine = open_database(Path(directory) / "agent-hud.db")
        exchange = create_exchange(engine)
        async with (
            serve(engine, {BOARD: exchange}, static_dir, Path(directory)) as address,
            open_agent(address) as agent,
            open_page(address) as user,
        ):
            for author, batch in turns:
                match author:
                    case Author.user:
                        for body in batch:
                            pending = [heard.body for heard in exchange.take_snapshot().pending]
                            answer = await user.act(body)
                            match answer, body.kind:
                                case Accepted(), ActionKind.say:
                                    taken += [*pending, body]
                                case Accepted(), ActionKind.send:
                                    taken += pending
                                case _:
                                    pass
                    case Author.agent:
                        await agent.tools.call_tool(
                            "write", {"name": BOARD, "actions": as_json(*batch)}, raise_on_error=False
                        )
                board = await read_board(agent.tools, history=True)
                assert await user.sees(board) == board
            taken += [heard.body for heard in exchange.take_snapshot().pending]
            await user.send()
            heard: list[TBody] = []
            while len(heard) < len(taken):
                heard += (await agent.turn()).actions
            assert heard == taken
