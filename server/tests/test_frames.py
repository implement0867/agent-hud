import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.frames import frames, head_of, lines, turn_of
from agent_hud.models.actions import Reaction, TBody
from agent_hud.models.events import Edit, THeardBody, Turn
from agent_hud.models.refs import named_refs
from tests.factories import comment, fill, link, put, react, say
from tests.strategies import action_ids, agent_bodies, card_ids, item_texts


@st.composite
def turns(draw: st.DrawFn) -> Turn:
    """A turn of any of the agent's kinds of action and edits, with a text for some of the parts the actions name."""
    edits = st.builds(Edit, kind=st.just("edit"), id=card_ids(), diff=st.text())
    actions: list[THeardBody] = draw(st.lists(st.one_of(agent_bodies(card_ids()), edits)))
    named = {ref for action in actions if not isinstance(action, Edit) for ref in named_refs(action)}
    parts = {ref: draw(item_texts()) for ref in sorted(named) if draw(st.booleans())}
    return Turn(id=draw(action_ids()), actions=tuple(actions), parts=parts)


def a_turn() -> Turn:
    """A turn like the live test's: reactions, a comment, fills on one row, a note, an arrow and a message."""
    actions: list[TBody] = [
        react("risks/2", Reaction.approve),
        comment("risks/2", "why?"),
        fill("checklist/2/2", "agent"),
        fill("checklist/2/3", 1),
        put("note-1", "# A note\n\nwith text"),
        link("a1", "risks/2", "checklist/2", "before"),
        say("done"),
    ]
    parts = {"risks/2": "The UI build is stale", "checklist/2": "Bump the version |  |  | "}
    return Turn(id="end", actions=tuple(actions), parts=parts)


def test_each_line_is_one_action_with_the_text_of_the_parts_it_is_the_first_to_name() -> None:
    """Assemble: a turn of reactions, a comment, fills, a note, an arrow and a message.
    Act: take its lines.
    Assert: one JSON line per action with its fields, the parts in the first line that names each, and no version on the note."""
    assert lines(a_turn()) == [
        '{"kind":"react","ref":"risks/2","reaction":"approve","parts":{"risks/2":"The UI build is stale"}}',
        '{"kind":"comment","ref":"risks/2","text":"why?"}',
        '{"kind":"fill","ref":"checklist/2/2","value":"agent","parts":{"checklist/2":"Bump the version |  |  | "}}',
        '{"kind":"fill","ref":"checklist/2/3","value":1.0}',
        '{"kind":"put","id":"note-1","md":"# A note\\n\\nwith text"}',
        '{"kind":"link","id":"a1","src":"risks/2","dst":"checklist/2","text":"before"}',
        '{"kind":"say","text":"done"}',
    ]


def test_a_turn_that_fits_is_one_frame_with_a_head_that_names_it_and_counts_its_actions() -> None:
    """Assemble: a turn of seven actions.
    Act: take its frames with room for it.
    Assert: one frame, whose first line is the head with the turn's id and count, and whose rest are the lines."""
    turn = a_turn()
    [frame] = frames(turn, 3000)
    assert frame.split("\n") == ['{"turn":"end","actions":7}', *lines(turn)]
    assert head_of(frame).model_dump() == {"turn": "end", "actions": 7, "frame": None, "of": None}


def test_a_turn_that_does_not_fit_comes_in_frames_of_the_size_with_numbered_heads() -> None:
    """Assemble: a turn of seven actions.
    Act: take its frames with room for 200 characters each.
    Assert: several frames of at most 200 characters, each a numbered head then whole lines, which together are all the lines."""
    turn = a_turn()
    taken = frames(turn, 200)
    assert len(taken) > 1
    assert all(len(frame) <= 200 for frame in taken)
    heads = [json.loads(frame.partition("\n")[0]) for frame in taken]
    assert heads == [{"turn": "end", "actions": 7, "frame": n, "of": len(taken)} for n in range(1, len(taken) + 1)]
    assert [line for frame in taken for line in frame.split("\n")[1:]] == lines(turn)


@given(turns(), st.integers(min_value=100, max_value=400))
def test_the_frames_of_any_turn_give_it_back_and_fit_the_size_unless_one_line_is_longer(turn: Turn, chars: int) -> None:
    """Assemble: any turn, and a frame size.
    Act: take its frames and the turn of them.
    Assert: the turn comes back whole, and each frame fits the size or is one line that does not."""
    taken = frames(turn, chars)
    assert turn_of(taken) == turn
    assert all(len(frame) <= chars or frame.count("\n") == 1 for frame in taken)


def test_the_turn_of_frames_needs_all_the_frames_of_one_turn_in_order() -> None:
    """Assemble: the frames of a turn, and a frame of another turn.
    Act: take the turn of the frames with one missing, out of order, or with the other's.
    Assert: ValueError each time, which names the heads."""
    first, second, *rest = frames(a_turn(), 200)
    other = frames(Turn(id="other", actions=(say("hi"),), parts={}), 200)
    for wrong in ([first, *rest], [second, first, *rest], [*other, second]):
        with pytest.raises(ValueError, match="frames of one turn"):
            turn_of(wrong)
    [whole] = frames(a_turn(), 3000)
    with pytest.raises(ValueError, match="counts 7 actions"):
        turn_of([whole.rpartition("\n")[0]])
