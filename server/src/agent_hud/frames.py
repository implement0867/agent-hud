import json
from collections.abc import Sequence
from typing import Any

from pydantic import Field

from agent_hud.models.actions import TActionId
from agent_hud.models.base import Model
from agent_hud.models.events import HeardBodyAdapter, THeardBody, Turn


class Head(Model):
    """The first line of a frame of a turn on the agent's monitor."""

    turn: TActionId = Field(description="The id of the turn, the same in each of its frames")
    actions: int = Field(description="The number of actions in the turn")
    frame: int | None = Field(default=None, description="Which frame of the turn this is, from 1, when it has several")
    of: int | None = Field(default=None, description="How many frames the turn has, when it has several")


def lines(turn: Turn) -> list[str]:
    """The lines of the turn after its head: one action each, as JSON with the action's fields."""
    # A field that is none, such as the version of a note or the occurrence of a quote at one place, stays out.
    return [
        json.dumps(action.model_dump(mode="json", exclude_none=True), separators=(",", ":"), ensure_ascii=False)
        for action in turn.actions
    ]


def frames(turn: Turn, chars: int) -> list[str]:
    """
    The turn as the text frames that the monitor gets: a head line, then the lines of the actions, in one frame of at
    most the chars where the lines allow; a turn with more lines than fit comes in several frames, each at most the
    chars unless one line is longer, with a head that says which frame it is and how many there are.
    """
    head = Head(turn=turn.id, actions=len(turn.actions))
    whole = "\n".join([head.model_dump_json(exclude_none=True), *lines(turn)])
    room = chars - len(head.model_copy(update={"frame": 99, "of": 99}).model_dump_json())
    chunks: list[list[str]] = [[]]
    for line in lines(turn):
        if chunks[-1] and sum(len(kept) + 1 for kept in chunks[-1]) + len(line) + 1 > room:
            chunks.append([])
        chunks[-1].append(line)
    if len(chunks) == 1:
        return [whole]
    return [
        "\n".join([head.model_copy(update={"frame": n, "of": len(chunks)}).model_dump_json(), *chunk])
        for n, chunk in enumerate(chunks, start=1)
    ]


def head_of(frame: str) -> Head:
    """The head of the frame."""
    return Head.model_validate_json(frame.partition("\n")[0])


def turn_of(frames: Sequence[str]) -> Turn:
    """
    The turn from its frames, in order. ValueError when the frames are not all the frames of one turn.
    """
    heads = [head_of(frame) for frame in frames]
    if len({head.turn for head in heads}) != 1 or [head.frame for head in heads] != (
        [None] if len(heads) == 1 else list(range(1, len(heads) + 1))
    ):
        raise ValueError(
            f"not the frames of one turn, in order: {[(head.turn, head.frame, head.of) for head in heads]}"
        )
    actions: list[THeardBody] = []
    for frame in frames:
        for line in frame.split("\n")[1:]:
            data: dict[str, Any] = json.loads(line)
            actions.append(HeardBodyAdapter.validate_python(data))
    if len(actions) != heads[0].actions:
        raise ValueError(f"the head counts {heads[0].actions} actions, the frames hold {len(actions)}")
    return Turn(id=heads[0].turn, actions=tuple(actions))
