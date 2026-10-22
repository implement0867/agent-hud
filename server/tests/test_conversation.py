from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_hud.deps import get_hud
from agent_hud.hud import Hud
from agent_hud.models.actions import Author, Reaction, TBody
from agent_hud.models.board import Arrow, Board, Point, Thread
from agent_hud.models.events import Accepted, EventKind, Rejected
from tests.conversation import Agent, User, open_agent, open_page
from tests.factories import as_json, comment, fill, link, move, put, react, read_board, remove, say
from tests.strategies import bodies, card_ids

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture
def hud() -> Hud:
    """A new hud for each conversation. The app and the agent get the same one from get_hud."""
    get_hud.cache_clear()
    return get_hud()


@pytest_asyncio.fixture(loop_scope="module")
async def agent(address: tuple[str, int], hud: Hud) -> AsyncIterator[Agent]:
    async with open_agent(address) as agent:
        yield agent


@pytest_asyncio.fixture(loop_scope="module")
async def user(address: tuple[str, int], hud: Hud) -> AsyncIterator[User]:
    async with open_page(address) as user:
        yield user


def kinds(answers: list[Accepted | Rejected]) -> list[EventKind]:
    return [answer.kind for answer in answers]


def feedback(board: Board) -> dict[str, tuple[Reaction | None, list[tuple[Author, str]]]]:
    """The reaction and the comments, by author and text, of each thread."""
    return {
        ref: (thread.reaction, [(said.author, said.text) for said in thread.comments])
        for ref, thread in board.threads.items()
    }


async def test_the_agent_revises_a_plan_from_the_users_feedback(agent: Agent, user: User) -> None:
    """Assemble: the agent puts a plan of three steps and asks the user to review it.
    Act: the user reacts to each step and comments on two; the agent answers a question, puts a new plan, and the user approves it.
    Assert: after each turn the agent hears the user's actions in order and reads the board that the page shows, and the new plan has none of the old feedback."""
    await agent.write(put("plan", "1. parse\n2. rewrite the cache\n3. render"), say("Review the plan"))
    board = await read_board(agent.tools)
    assert await user.sees(board) == board

    review = [
        react("plan/1", Reaction.approve),
        react("plan/2", Reaction.reject),
        comment("plan/2", "the cache is shared"),
        react("plan/3", Reaction.question),
        comment("plan/3", "render where?"),
    ]
    assert kinds([await user.act(body) for body in review]) == [EventKind.accepted] * len(review)
    assert await agent.hear(len(review)) == review
    board = await read_board(agent.tools)
    assert feedback(board) == {
        "plan/1": (Reaction.approve, []),
        "plan/2": (Reaction.reject, [(Author.user, "the cache is shared")]),
        "plan/3": (Reaction.question, [(Author.user, "render where?")]),
    }

    await agent.write(comment("plan/3", "in the browser"))
    board = await read_board(agent.tools)
    assert await user.sees(board) == board
    assert feedback(board)["plan/3"] == (
        Reaction.question,
        [(Author.user, "render where?"), (Author.agent, "in the browser")],
    )

    await agent.write(put("plan", "1. parse\n2. keep the cache\n3. render in the browser"), say("I kept the cache"))
    board = await read_board(agent.tools)
    assert await user.sees(board) == board
    assert (board.threads, [said.text for said in board.messages]) == ({}, ["Review the plan", "I kept the cache"])

    approval = [react("plan", Reaction.approve), say("go ahead")]
    assert kinds([await user.act(body) for body in approval]) == [EventKind.accepted] * len(approval)
    assert await agent.hear(len(approval)) == approval
    assert (await read_board(agent.tools)).threads == {"plan": Thread(reaction=Reaction.approve)}


async def test_the_agent_hears_only_the_values_that_fit_their_columns(agent: Agent, user: User) -> None:
    """Assemble: the agent puts a table of tasks with a size, hours and done column.
    Act: the user fills cells with values that fit and values that do not, and clears one; then the agent adds a row.
    Assert: the board rejects each value that does not fit, the agent hears and reads only the others, and the new card has no values."""
    table = "| Task | Size {S, M, L} | Hours {number} | Done {check} |\n|---|---|---|---|\n| parse | | | |\n| render | | | |"
    await agent.write(put("tasks", table))

    fits = [fill("tasks/1/2", "M"), fill("tasks/1/3", 4), fill("tasks/2/4", value=True), fill("tasks/1/3", None)]
    misfits = [fill("tasks/2/2", "XL"), fill("tasks/2/3", "four"), fill("tasks/1/1", "lex")]
    answers = [
        await user.act(body) for body in [fits[0], misfits[0], fits[1], misfits[1], fits[2], misfits[2], fits[3]]
    ]
    assert kinds(answers) == [EventKind.accepted, EventKind.rejected] * 3 + [EventKind.accepted]
    assert [answer.reason for answer in answers if isinstance(answer, Rejected)] == [
        "input 'tasks/2/2' takes select values",
        "input 'tasks/2/3' takes number values",
        "no input 'tasks/1/1'",
    ]
    assert await agent.hear(len(fits)) == fits
    board = await read_board(agent.tools)
    assert await user.sees(board) == board
    assert board.values == {"tasks/1/2": "M", "tasks/1/3": None, "tasks/2/4": True}

    await agent.write(put("tasks", f"{table}\n| test | | | |"))
    board = await read_board(agent.tools)
    assert (await user.sees(board)).values == {}


async def test_the_user_and_the_agent_discuss_code_with_arrows(agent: Agent, user: User) -> None:
    """Assemble: the agent puts a code card, a card of options and a card of questions side by side, with an arrow from an option to a question.
    Act: the user approves an option, draws an arrow from the code to it and answers the question; then the agent removes the options.
    Assert: the agent hears and reads the user's arrow beside its own, and the page shows no arrow or feedback on the options once they are gone."""
    await agent.write(
        put("code", "```python\ndef render(md: str) -> str:\n    return md\n```"),
        put("options", "1. highlight on the server\n2. highlight in the browser"),
        put("questions", "1. Which languages?"),
        link("decides", "options/2", "questions/1"),
        move("code", 0, 0),
        move("options", 420, 0),
        move("questions", 840, 0),
    )
    board = await read_board(agent.tools)
    assert await user.sees(board) == board

    answer = [react("options/2", Reaction.approve), link("mine", "code", "options/2"), comment("questions/1", "all")]
    assert kinds([await user.act(body) for body in answer]) == [EventKind.accepted] * len(answer)
    assert await agent.hear(len(answer)) == answer
    board = await read_board(agent.tools)
    assert board.arrows == {
        "decides": Arrow(src="options/2", dst="questions/1", text="", author=Author.agent),
        "mine": Arrow(src="code", dst="options/2", text="", author=Author.user),
    }

    await agent.write(remove("options"), say("Highlighting goes in the browser"))
    board = await read_board(agent.tools)
    seen = await user.sees(board)
    assert seen == board
    assert (seen.arrows, list(feedback(seen))) == ({}, ["questions/1"])


async def test_the_agent_hears_the_notes_and_edits_of_the_user(agent: Agent, user: User) -> None:
    """Assemble: a board with an agent's plan card and an arrow from it to the user's note.
    Act: the user writes a note, places it, edits the agent's card and then removes the note.
    Assert: the agent hears each action, and reads the user as the author of the note and of the edited card, whose arrow is gone."""
    note = [put("note", "Also check the docs"), move("note", 40, 300), say("see my note")]
    assert kinds([await user.act(body) for body in note]) == [EventKind.accepted] * len(note)
    assert await agent.hear(len(note)) == note
    board = await read_board(agent.tools)
    assert (board.cards["note"].author, board.positions) == (Author.user, {"note": Point(x=40, y=300)})

    await agent.write(put("plan", "1. read the docs\n2. write the code"), link("from", "plan/1", "note"))
    edits = [put("plan", "1. read the docs\n2. write the tests\n3. write the code"), remove("note")]
    assert kinds([await user.act(body) for body in edits]) == [EventKind.accepted] * len(edits)
    assert await agent.hear(len(edits)) == edits
    board = await read_board(agent.tools)
    assert await user.sees(board) == board
    assert ({k: v.author for k, v in board.cards.items()}, board.arrows) == ({"plan": Author.user}, {})


async def test_a_click_on_a_part_that_the_agent_just_removed_is_rejected(agent: Agent, user: User) -> None:
    """Assemble: the page shows a plan of three steps.
    Act: the agent puts a plan of two steps, and the user reacts to step 3 of the old plan, then to step 2.
    Assert: the board rejects the reaction to step 3, the agent hears only the reaction to step 2, and the page shows the new plan."""
    await agent.write(put("plan", "1. a\n2. b\n3. c"))
    assert "plan" in (await user.sees(await read_board(agent.tools))).cards

    await agent.write(put("plan", "1. a\n2. c"))
    stale = await user.act(react("plan/3", Reaction.reject))
    assert stale == Rejected(kind=EventKind.rejected, id=stale.id, reason="no part 'plan/3'")
    assert (await user.act(react("plan/2", Reaction.reject))).kind is EventKind.accepted
    assert await agent.hear(1) == [react("plan/2", Reaction.reject)]
    board = await read_board(agent.tools)
    assert await user.sees(board) == board


async def test_an_agent_monitor_gets_what_the_user_did_while_no_monitor_was_open(
    agent: Agent, user: User, address: tuple[str, int]
) -> None:
    """Assemble: the agent puts a plan, and its monitor ends.
    Act: the user reacts and comments, reloads the page, and the agent opens a new monitor.
    Assert: the new monitor gets the user's actions in order, and the new page shows the board that the agent reads."""
    await agent.write(put("plan", "1. a\n2. b"))
    await agent.monitor.close()

    missed = [react("plan/1", Reaction.question), comment("plan/1", "why a?")]
    assert kinds([await user.act(body) for body in missed]) == [EventKind.accepted] * len(missed)
    async with open_page(address) as reloaded, agent.listen():
        assert await agent.hear(len(missed)) == missed
        assert reloaded.board == await read_board(agent.tools)


@st.composite
def turns(draw: st.DrawFn) -> list[tuple[Author, list[TBody]]]:
    """Turns of the user and the agent on one pool of card ids, each of one to three actions, so that some fit the board and some do not."""
    ids = st.sampled_from(draw(st.lists(card_ids(), min_size=1, max_size=3)))
    return draw(st.lists(st.tuples(st.from_type(Author), st.lists(bodies(ids), min_size=1, max_size=3)), max_size=8))


# Examples go over sockets, so their time varies more than the default deadline allows.
@given(turns())
@settings(deadline=None, max_examples=50)
async def test_the_page_and_the_agent_agree_after_each_turn(
    address: tuple[str, int], turns: list[tuple[Author, list[TBody]]]
) -> None:
    """Assemble: a new board, a page and an agent with a monitor.
    Act: the user and the agent take turns; the page sends each of the user's actions alone, and the agent writes each turn in one call.
    Assert: after each turn the page shows the board that the agent reads, and at the end the agent has heard each action that the board took from the user, in order."""
    get_hud.cache_clear()
    taken: list[TBody] = []
    async with open_agent(address) as agent, open_page(address) as user:
        for author, batch in turns:
            match author:
                case Author.user:
                    taken += [body for body in batch if isinstance(await user.act(body), Accepted)]
                case Author.agent:
                    await agent.tools.call_tool("write", {"actions": as_json(*batch)}, raise_on_error=False)
            board = await read_board(agent.tools)
            assert await user.sees(board) == board
        assert await agent.hear(len(taken)) == taken
