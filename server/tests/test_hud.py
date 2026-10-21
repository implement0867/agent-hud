import asyncio
from contextlib import aclosing, suppress
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.hud import Hud
from agent_hud.models.actions import Action, Author
from agent_hud.models.board import Board
from tests.factories import say
from tests.strategies import actions, messages


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


def said(texts: list[str], author: Author) -> list[Action]:
    return [Action(id=f"{author}{n}", author=author, body=say(text)) for n, text in enumerate(texts)]


async def take(hud: Hud, count: int) -> list[Action]:
    """The first actions an agent gets from the hud. TimeoutError if fewer come in a second."""
    taken: list[Action] = []
    async with asyncio.timeout(1), aclosing(hud.user_actions()) as user_actions:
        async for action in user_actions:
            taken.append(action)
            if len(taken) == count:
                break
    return taken


@given(
    st.builds(Hud), st.lists(messages(), min_size=1), st.lists(messages(), min_size=1), st.lists(messages(), min_size=1)
)
async def test_an_agent_gets_the_user_actions_that_no_agent_had(
    hud: Hud, first: list[str], agent_texts: list[str], rest: list[str]
) -> None:
    """Assemble: a hud whose first agent got the user's first actions and stopped, then more actions by both authors.
    Act: a second agent follows the hud.
    Assert: it gets only the user's actions after the first, in order."""
    hud.act(said(first, Author.user))
    assert await take(hud, len(first)) == said(first, Author.user)
    hud.act([*said(agent_texts, Author.agent), *said(rest, Author.user)])
    assert await take(hud, len(rest)) == said(rest, Author.user)


@given(st.lists(actions(st.sampled_from(["a", "b"]))), messages())
async def test_a_hud_on_the_state_file_takes_up_where_the_last_left_off(batch: list[Action], text: str) -> None:
    """Assemble: a hud on a state file that took each action that fits.
    Act: start a new hud on the same file, and the user says a message.
    Assert: the new hud has the same board and log, and an agent gets only the new message."""
    with TemporaryDirectory() as directory:
        state_file = Path(directory) / "state.jsonl"
        hud = Hud(state_file)
        for action in batch:
            with suppress(ValueError):
                hud.act([action])
        again = Hud(state_file)
        assert (again.board, again.log.actions) == (hud.board, hud.log.actions)
        again.act(said([text], Author.user))
        assert await take(again, 1) == said([text], Author.user)
