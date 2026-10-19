import pytest
from pydantic import TypeAdapter, ValidationError

from agent_hud.board import Board
from agent_hud.card import Card
from agent_hud.ops import Op
from tests.factories import put, remove


@pytest.mark.parametrize(
    ("ops", "cards"),
    [
        ([put("plan", "1. a")], {"plan": "1. a"}),
        ([put("plan", "old"), put("plan", "new")], {"plan": "new"}),
        ([put("a", "x"), put("b", "y")], {"a": "x", "b": "y"}),
        ([put("a", "x"), remove("a")], {}),
    ],
    ids=["put", "replace", "two-cards", "remove"],
)
def test_apply_runs_ops_in_order(ops: list[Op], cards: dict[str, str]) -> None:
    """Assemble: an empty board.
    Act: apply the ops.
    Assert: the new board holds the expected cards."""
    board = Board().apply(ops)
    expected = {card_id: Card(md=md) for card_id, md in cards.items()}
    assert board.cards == expected, f"{ops} gave {board.cards}, not {expected}"


def test_apply_rejects_a_missing_card() -> None:
    """Assemble: a board with card a.
    Act: apply a put, then a remove of a card that does not exist.
    Assert: ValueError, and the board still holds only card a."""
    board = Board().apply([put("a", "x")])
    with pytest.raises(ValueError):
        board.apply([put("b", "y"), remove("missing")])
    assert board.cards == {"a": Card(md="x")}, "a failed apply must not change the board"


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


@pytest.mark.parametrize(
    ("ops", "text"),
    [
        ([], ""),
        ([put("a", "x"), put("b", "1. y\n2. z")], "a:\nx\n\nb:\n1. y\n2. z"),
    ],
    ids=["no-cards", "two-cards"],
)
def test_render_lists_each_card_with_its_markdown(ops: list[Op], text: str) -> None:
    """Assemble: a board with the given cards.
    Act: render it.
    Assert: each card is its id line, then its markdown, with a blank line between cards."""
    assert Board().apply(ops).render() == text
