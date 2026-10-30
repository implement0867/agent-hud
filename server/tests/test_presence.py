import pytest

from agent_hud.models.events import AgentState, Turn
from agent_hud.presence import Away, Monitor, Presence, Waiting, Working
from tests.factories import make_post


def make_sample_turn(turn_id: str) -> Turn:
    return Turn(id=turn_id, actions=(make_post(turn_id),))


def test_the_agent_is_away_then_waits_then_works_until_it_writes() -> None:
    """Act: open a monitor, deliver a turn, note a write, open a second monitor, and close both.
    Assert: away, waiting with the monitor, working with it, waiting again, both monitors kept, and away once both close."""
    presence = Presence()
    assert (presence.agent, presence.agent_state, presence.monitors) == (Away(), AgentState.away, [])
    with presence.open_monitor() as first:
        assert (presence.agent, presence.agent_state) == (Waiting([first]), AgentState.waiting)
        presence.mark_delivered(first, make_sample_turn("t"))
        assert (presence.agent, presence.agent_state, first.delivered) == (Working([first]), AgentState.working, {"t"})
        presence.note_agent_wrote()
        assert presence.agent == Waiting([first])
        with presence.open_monitor() as second:
            assert presence.monitors == [first, second]
        assert presence.monitors == [first]
    assert presence.agent == Away()


def test_a_turn_is_delivered_to_all_once_every_open_monitor_has_it() -> None:
    """Assemble: two open monitors and two turns.
    Act: deliver the first turn to the first monitor, then to the second.
    Assert: no turn is delivered to all after the first delivery, and the first turn after the second."""
    presence = Presence()
    turns = [make_sample_turn("one"), make_sample_turn("two")]
    with presence.open_monitor() as first, presence.open_monitor() as second:
        presence.mark_delivered(first, turns[0])
        assert presence.find_turns_delivered_to_all(turns) == set()
        presence.mark_delivered(second, turns[0])
        assert presence.find_turns_delivered_to_all(turns) == {"one"}


def test_a_delivery_needs_an_open_monitor() -> None:
    """Act: mark a turn delivered to a monitor that no presence opened.
    Assert: RuntimeError."""
    with pytest.raises(RuntimeError, match="no monitor is open"):
        Presence().mark_delivered(Monitor(), make_sample_turn("t"))


async def test_a_watcher_wakes_on_each_change() -> None:
    """Act: watch the changes, and notify one.
    Assert: the watcher yields on start and once more after the change."""
    presence = Presence()
    watcher = presence.watch_changes()
    await anext(watcher)
    presence.notify_change()
    await anext(watcher)
    await watcher.aclose()
