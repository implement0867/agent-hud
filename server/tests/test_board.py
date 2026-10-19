import string

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from agent_hud.board import Board
from agent_hud.card import Card
from agent_hud.ops import Op, PutOp, RemoveOp
from tests.factories import put, remove


@st.composite
def valid_ops(draw: st.DrawFn) -> list[Op]:
    """Puts on a few ids, so that ops often hit the same card, and removes of cards that exist at that point."""
    present: set[str] = set()
    ops: list[Op] = []
    for _ in range(draw(st.integers(min_value=0, max_value=12))):
        if present and draw(st.booleans()):
            card_id = draw(st.sampled_from(sorted(present)))
            present.remove(card_id)
            ops.append(remove(card_id))
        else:
            card_id = draw(st.sampled_from(["a", "b", "c"]))
            present.add(card_id)
            ops.append(put(card_id, draw(st.text(string.printable, min_size=1))))
    return ops


@st.composite
def ops_with_a_missing_remove(draw: st.DrawFn) -> list[Op]:
    return [*draw(valid_ops()), remove("missing"), *draw(valid_ops())]


@given(valid_ops())
def test_apply_leaves_each_card_as_its_last_op_set_it(ops: list[Op]) -> None:
    """Assemble: an empty board and ops that remove only cards that exist.
    Act: apply the ops.
    Assert: each card has the markdown of its last put, or is gone after its last remove."""
    board = Board()
    board.apply(ops)
    for card_id, op in {op.id: op for op in ops}.items():
        match op:
            case PutOp(md=md):
                assert board.cards[card_id] == Card(md=md), f"{card_id} must hold its last put"
            case RemoveOp():
                assert card_id not in board.cards, f"{card_id} was removed last"
    assert set(board.cards) <= {op.id for op in ops}, "apply must not create cards that no op names"


@given(valid_ops(), st.data())
def test_apply_in_two_parts_equals_apply_in_one(ops: list[Op], data: st.DataObject) -> None:
    """Assemble: valid ops and a point that splits them in two.
    Act: apply all ops to one board, and the two parts in turn to another.
    Assert: the two boards are equal."""
    split = data.draw(st.integers(min_value=0, max_value=len(ops)))
    whole, parts = Board(), Board()
    whole.apply(ops)
    parts.apply(ops[:split])
    parts.apply(ops[split:])
    assert parts == whole


@given(valid_ops(), ops_with_a_missing_remove())
def test_failed_apply_changes_nothing(setup: list[Op], ops: list[Op]) -> None:
    """Assemble: a board built from valid ops.
    Act: apply ops that include a remove of a card that does not exist.
    Assert: ValueError, and the board is equal to before."""
    board = Board()
    board.apply(setup)
    before = board.model_copy(deep=True)
    with pytest.raises(ValueError):
        board.apply(ops)
    assert board == before, "a failed apply must not change the board"


@pytest.mark.parametrize(
    "raw",
    [
        {"op": "move", "id": "a"},
        {"op": "put", "id": "a", "md": ""},
        {"op": "put", "id": "1a", "md": "x"},
        {"op": "put", "id": "a", "md": "x", "title": "T"},
    ],
    ids=["unknown-op", "empty-md", "bad-id", "unknown-field"],
)
def test_invalid_op_is_rejected(raw: dict[str, str]) -> None:
    """Assemble: an op as a client could send it, which breaks the schema.
    Act: validate it as an Op.
    Assert: ValidationError."""
    with pytest.raises(ValidationError):
        TypeAdapter(Op).validate_python(raw)
