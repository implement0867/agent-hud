import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.frames import FrameHead, action_lines, join_frames, split_into_frames
from agent_hud.models.events import Edit, THeardBody, Turn
from tests.factories import comment, link, put, say
from tests.strategies import action_ids, agent_bodies, card_ids


@st.composite
def turns(draw: st.DrawFn) -> Turn:
    """A turn of any of the agent's kinds of action and edits."""
    edits = st.builds(Edit, kind=st.just("edit"), id=card_ids(), diff=st.text())
    actions: list[THeardBody] = draw(st.lists(st.one_of(agent_bodies(card_ids()), edits)))
    return Turn(id=draw(action_ids()), actions=tuple(actions))


def a_turn() -> Turn:
    """A turn like the live test's: comments, an edit, a note, an arrow and a message."""
    actions: list[THeardBody] = [
        comment("risks", "why?", "The UI build is stale"),
        comment("risks", "and this?", "stale", 1),
        comment("risks", "fine"),
        Edit(kind="edit", id="checklist", diff="@@ -3 +3 @@\n-| [ ] | Bump |\n+| [x] | Bump |"),
        put("note-1", "# A note\n\nwith text"),
        link("a1", "risks", "checklist", "before", "The UI build"),
        say("done"),
    ]
    return Turn(id="end", actions=tuple(actions))


def test_each_line_is_one_action_with_its_fields() -> None:
    """Assemble: a turn of comments, an edit, a note, an arrow and a message.
    Act: take its lines.
    Assert: one JSON line per action with its fields, and no version on the note or occurrence on a quote at one place."""
    assert action_lines(a_turn()) == [
        '{"kind":"comment","card":"risks","quote":"The UI build is stale","text":"why?"}',
        '{"kind":"comment","card":"risks","quote":"stale","occurrence":1,"text":"and this?"}',
        '{"kind":"comment","card":"risks","quote":"","text":"fine"}',
        '{"kind":"edit","id":"checklist","diff":"@@ -3 +3 @@\\n-| [ ] | Bump |\\n+| [x] | Bump |"}',
        '{"kind":"put","id":"note-1","md":"# A note\\n\\nwith text"}',
        '{"kind":"link","id":"a1","card":"risks","quote":"The UI build","dst":"checklist","text":"before"}',
        '{"kind":"say","text":"done"}',
    ]


def test_a_turn_that_fits_is_one_frame_with_a_head_that_names_it_and_counts_its_actions() -> None:
    """Assemble: a turn of seven actions.
    Act: take its frames with room for it.
    Assert: one frame, whose first line is the head with the turn's id and count, and whose rest are the lines."""
    turn = a_turn()
    [frame] = split_into_frames(turn, 3000)
    assert frame.split("\n") == ['{"turn":"end","actions":7}', *action_lines(turn)]
    assert FrameHead.model_validate_json(frame.partition("\n")[0]).model_dump() == {
        "turn": "end",
        "actions": 7,
        "frame": None,
        "of": None,
    }


def test_a_turn_that_does_not_fit_comes_in_frames_of_the_size_with_numbered_heads() -> None:
    """Assemble: a turn of seven actions.
    Act: take its frames with room for 200 characters each.
    Assert: several frames of at most 200 characters, each a numbered head then whole lines, which together are all the lines."""
    turn = a_turn()
    taken = split_into_frames(turn, 200)
    assert len(taken) > 1
    assert all(len(frame) <= 200 for frame in taken)
    heads = [json.loads(frame.partition("\n")[0]) for frame in taken]
    assert heads == [{"turn": "end", "actions": 7, "frame": n, "of": len(taken)} for n in range(1, len(taken) + 1)]
    assert [line for frame in taken for line in frame.split("\n")[1:]] == action_lines(turn)


@given(turns(), st.integers(min_value=100, max_value=400))
def test_the_frames_of_any_turn_give_it_back_and_fit_the_size_unless_one_line_is_longer(turn: Turn, chars: int) -> None:
    """Assemble: any turn, and a frame size.
    Act: take its frames and the turn of them.
    Assert: the turn comes back whole, and each frame fits the size or is one line that does not."""
    taken = split_into_frames(turn, chars)
    assert join_frames(taken) == turn
    assert all(len(frame) <= chars or frame.count("\n") == 1 for frame in taken)


def test_the_turn_of_frames_needs_all_the_frames_of_one_turn_in_order() -> None:
    """Assemble: the frames of a turn, and a frame of another turn.
    Act: take the turn of the frames with one missing, out of order, or with the other's.
    Assert: ValueError each time, which names the heads."""
    first, second, *rest = split_into_frames(a_turn(), 200)
    other = split_into_frames(Turn(id="other", actions=(say("hi"),)), 200)
    for wrong in ([first, *rest], [second, first, *rest], [*other, second]):
        with pytest.raises(ValueError, match="frames of one turn"):
            join_frames(wrong)
    [whole] = split_into_frames(a_turn(), 3000)
    with pytest.raises(ValueError, match="counts 7 actions"):
        join_frames([whole.rpartition("\n")[0]])
