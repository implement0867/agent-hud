from contextlib import nullcontext as does_not_raise
from typing import Any

import pytest

from agent_hud.agent import OpError
from agent_hud.hub import Hub
from agent_hud.page import UserError
from agent_hud.primitives import LinkEl, ListEl, TableEl, TextEl
from agent_hud.report import report, show_cards
from agent_hud.state import BoardState
from tests.conftest import Act, Write, anchor

PLAN = "## Plan\n" + "\n".join(f"{n}. step {n}" for n in range(1, 7))


@pytest.mark.parametrize(
    ("md", "kind", "cls"),
    [
        ("just words", None, TextEl),
        ("1. a\n2. b", None, ListEl),
        ("| A |\n|---|\n| 1 |", None, TableEl),
        ("| A | Ok {check} |\n|---|---|\n| 1 | x |", None, TableEl),
        ("1. a\n2. b", "text", TextEl),
    ],
    ids=["text", "list", "table", "typed-table", "forced-text"],
)
def test_put_builds_the_inferred_primitive(hub: Hub, write: Write, md: str, kind: str | None, cls: type) -> None:
    write({"op": "put", "id": "x", "md": md, "kind": kind})
    assert type(hub.state.elements["x"]) is cls


@pytest.mark.parametrize(
    ("md", "title", "body"),
    [
        ("Plan\n====\nSome text\n\n- x", "Plan", "Some text\n\n- x"),
        ("## Plan\n\nSome text", "Plan", "Some text"),
        ("Some text", None, "Some text"),
    ],
    ids=["setext", "atx", "no-heading"],
)
def test_forced_text_takes_the_heading_as_title(hub: Hub, write: Write, md: str, title: str | None, body: str) -> None:
    write({"op": "put", "id": "t", "md": md, "kind": "text"})
    el = hub.state.elements["t"]
    assert isinstance(el, TextEl)
    assert (el.title, el.body) == (title, body)


def test_review_scenario_reports_one_line_per_part(hub: Hub, write: Write, act: Act) -> None:
    """The motivating case: approve 3 and 4, question the wording of 2, ask whether 6 entails 1."""
    write({"op": "put", "id": "plan", "md": PLAN})
    for label, reaction in [("plan.3", "approve"), ("plan.4", "approve"), ("plan.2", "question")]:
        el_id, key = anchor(hub, label)
        act(t="react", id=el_id, anchor=key, reaction=reaction)
    act(t="comment", id="plan", anchor=anchor(hub, "plan.2")[1], text="wording is unclear")
    act(
        t="link",
        src={"id": "plan", "anchor": anchor(hub, "plan.6")[1]},
        dst={"id": "plan", "anchor": anchor(hub, "plan.1")[1]},
        text="entails?",
    )
    act(t="submit", message="close")

    lines = report(hub.state).splitlines()

    link_id = next(el.id for el in hub.state.elements.values() if isinstance(el, LinkEl))
    assert lines == [
        f'link {link_id} plan.6 -> plan.1 "entails?" by user',
        "plan.3 approve",
        "plan.4 approve",
        'plan.2 question; "wording is unclear"',
        'submit "close"',
    ]
    assert report(hub.state) == "no changes", "a second read returns only newer changes"


def test_labels_follow_position_while_anchors_stay(hub: Hub, write: Write, act: Act) -> None:
    write({"op": "put", "id": "plan", "md": PLAN})
    el_id, key = anchor(hub, "plan.2")
    act(t="react", id=el_id, anchor=key, reaction="reject")
    report(hub.state)
    write({"op": "insert", "at": "plan.1", "value": "step 0"})
    act(t="comment", id=el_id, anchor=key, text="still no")
    assert report(hub.state) == 'plan.3 "still no"'


def test_reput_keeps_feedback_on_unchanged_items_and_flags_revisions(hub: Hub, write: Write, act: Act) -> None:
    write({"op": "put", "id": "plan", "md": "1. keep\n2. reword me\n3. drop"})
    keys = {n: anchor(hub, f"plan.{n}")[1] for n in (1, 2, 3)}
    for key in keys.values():
        act(t="react", id="plan", anchor=key, reaction="question")
    write({"op": "put", "id": "plan", "md": "1. keep\n2. reworded"})
    write({"op": "set", "at": "plan.1", "value": "keep, sharper"})
    plan = hub.state.elements["plan"]
    assert isinstance(plan, ListEl)
    assert plan.items[0].id == keys[1], "an item whose text survives keeps its anchor"
    assert plan.feedback[keys[1]].revised, "set marks the reaction as revised"
    assert keys[2] not in plan.feedback and keys[3] not in plan.feedback, "feedback on replaced items is dropped"


def test_reput_of_typed_table_keeps_user_input(hub: Hub, write: Write, act: Act) -> None:
    md = "| Option | Pick {check} |\n|---|---|\n| A | |\n| B | |"
    write({"op": "put", "id": "opts", "md": md})
    el_id, key = anchor(hub, "opts.r2.pick")
    act(t="edit", id=el_id, anchor=key, value=True)
    write({"op": "put", "id": "opts", "md": md + "\n| C | |"})
    assert show_cards(hub.state, ["opts"]).splitlines()[4] == "| r2 | B | x |"


@pytest.mark.parametrize(
    ("label", "value", "expected"),
    [
        ("opts.r1.pick", "x", "| r1 | A | x | low | 0 |"),
        ("opts.r1.effort", "HIGH", "| r1 | A |  | high | 0 |"),
        ("opts.r1.cost", "1,200", "| r1 | A |  | low | 1200 |"),
        ("opts.r1", "Z | yes | med | 3", "| r1 | Z | x | med | 3 |"),
    ],
)
def test_set_coerces_typed_cells(hub: Hub, write: Write, label: str, value: str, expected: str) -> None:
    write(
        {
            "op": "put",
            "id": "opts",
            "md": "| Option | Pick {check} | Effort {low,high,med} | Cost {number} |\n|---|---|---|---|\n| A | | low | 0 |",
        }
    )
    write({"op": "set", "at": label, "value": value})
    assert show_cards(hub.state, ["opts"]).splitlines()[3] == expected


@pytest.mark.parametrize(
    ("ops", "message"),
    [
        ([{"op": "set", "at": "ghost.1", "value": "x"}], "no element 'ghost'"),
        ([{"op": "set", "at": "plan.9", "value": "x"}], "no part '9'"),
        ([{"op": "set", "at": "plan.1", "value": "ok"}, {"op": "remove", "at": "plan.7"}], "op 2"),
        ([{"op": "put", "id": "t", "md": "| A {check} |\n|---|\n| maybe |"}], "not a check value"),
        ([{"op": "put", "id": "t", "md": "plain", "kind": "table"}], "needs a markdown table"),
    ],
    ids=["unknown-element", "bad-index", "atomic", "bad-cell", "wrong-kind"],
)
def test_failed_batch_changes_nothing(hub: Hub, write: Write, ops: list[dict[str, Any]], message: str) -> None:
    write({"op": "put", "id": "plan", "md": PLAN})
    before = show_cards(hub.state, ["*"])
    with pytest.raises(OpError, match=message):
        write(*ops)
    assert show_cards(hub.state, ["*"]) == before


def test_removing_an_end_drops_the_link(hub: Hub, write: Write) -> None:
    write({"op": "put", "id": "plan", "md": PLAN}, {"op": "link", "src": "plan.6", "dst": "plan.1", "id": "dep"})
    write({"op": "remove", "at": "plan.1"})
    assert "dep" not in hub.state.elements


def test_user_edits_adds_and_removes_are_reported(hub: Hub, write: Write, act: Act) -> None:
    write({"op": "put", "id": "plan", "md": PLAN})
    act(t="edit", id="plan", anchor=anchor(hub, "plan.1")[1], value="step one, reworded")
    act(t="add", id="plan", value="step 7")
    act(t="remove", id="plan", anchor=anchor(hub, "plan.5")[1])
    act(t="note", x=0, y=0, text="also think about rollback")
    note_id = next(i for i in hub.state.elements if i.startswith("n"))
    assert report(hub.state).splitlines() == [
        f'{note_id}: note "also think about rollback"',
        'plan.1 = "step one, reworded"',
        'plan.6 added "step 7"',
        'plan.5 removed "step 5"',
    ]


@pytest.mark.parametrize(
    ("author_of", "expectation"),
    [("user", does_not_raise()), ("agent", pytest.raises(UserError, match="belongs to the agent"))],
)
def test_user_may_delete_only_their_own_elements(
    hub: Hub, write: Write, act: Act, author_of: str, expectation: Any
) -> None:
    write({"op": "put", "id": "plan", "md": PLAN})
    act(t="note", x=0, y=0, text="mine")
    target = next(i for i, el in hub.state.elements.items() if el.author == author_of)
    with expectation:
        act(t="delete", id=target)


def test_note_created_and_deleted_before_a_read_is_silent(hub: Hub, act: Act) -> None:
    act(t="note", x=0, y=0, text="oops")
    act(t="delete", id=next(iter(hub.state.elements)))
    assert report(hub.state) == "no changes"


def test_place_only_positions_unplaced_cards(hub: Hub, write: Write, act: Act) -> None:
    write({"op": "put", "id": "t", "md": "hi"})
    act(t="place", id="t", x=10, y=20)
    act(t="place", id="t", x=99, y=99)
    el = hub.state.elements["t"]
    assert isinstance(el, TextEl)
    assert (el.x, el.y) == (10, 20)


def test_listeners_receive_upserts_and_status(hub: Hub, write: Write) -> None:
    seen: list[str] = []
    hub.listen(lambda msg: seen.append(msg.t))
    write({"op": "put", "id": "t", "md": "hi"})
    assert seen == ["upsert", "status"]


def test_state_round_trips(hub: Hub, write: Write, act: Act) -> None:
    write({"op": "put", "id": "plan", "md": PLAN})
    act(t="react", id="plan", anchor="", reaction="approve")
    restored = BoardState.model_validate_json(hub.state.model_dump_json())
    assert show_cards(restored, ["*"]) == show_cards(hub.state, ["*"])
    assert report(restored) == report(hub.state)
