from hypothesis import given
from hypothesis import strategies as st

from agent_hud.models.actions import Action, Author, TBody
from agent_hud.models.board import Board
from agent_hud.models.draft import Draft
from agent_hud.models.events import Edit, Turn, TurnAction
from tests.factories import make_comment, make_move, make_place, make_post, make_put, make_resize, make_send
from tests.strategies import item_texts, make_list_md, messages


def make_user_actions(*bodies: TBody) -> list[Action]:
    return [Action(id=f"u{n}", author=Author.user, body=body) for n, body in enumerate(bodies)]


def take_all_actions(board: Board, actions: list[Action]) -> tuple[Board, Draft, list[Turn]]:
    """Take the user's actions one by one, as the page sends them: the board, the draft and the turns they ended."""
    draft, turns = Draft(), []
    for action in actions:
        match draft.take_action(board, action):
            case Draft() as draft:
                pass
            case Turn() as turn:
                draft, turns = Draft(), [*turns, turn]
        board = board.apply_action(action)
    return board, draft, turns


def test_a_draft_leaves_out_the_moves_resizes_and_places() -> None:
    """Assemble: a board with the agent's card.
    Act: the user comments, moves, places and resizes the card, comments again, and sends.
    Assert: the draft and the turn carry the comments alone, which read has the places and sizes for."""
    board = Board().apply_action(Action(id="a", author=Author.agent, body=make_put("plan", "1. a\n2. b")))
    feedback = make_user_actions(
        make_comment("plan", "why?", "a"),
        make_move("plan", 5, 5),
        make_place("plan", 6, 6),
        make_resize("plan", 500, 300),
        make_comment("plan", "and?", "b"),
    )
    _, draft, turns = take_all_actions(board, feedback)
    assert ([heard.id for heard in draft.actions], turns) == (["u0", "u4"], [])
    _, draft, turns = take_all_actions(board, [*feedback, Action(id="e", author=Author.user, body=make_send())])
    assert (draft, turns) == (Draft(), [Turn(id="e", actions=(feedback[0].body, feedback[4].body))])


@given(st.lists(item_texts(), min_size=2, unique=True), messages())
def test_a_turn_ends_on_a_send_or_a_message(texts: list[str], text: str) -> None:
    """Assemble: a board with the agent's list.
    Act: the user comments on the card and on an item, moves the card and sends, then says a message.
    Assert: one turn of the comments, ended by the make_send, then one turn of the message alone, ended by it."""
    board = Board().apply_action(
        Action(id="a", author=Author.agent, body=make_put("plan", make_list_md("1. ", ["first-item", *texts])))
    )
    feedback = make_user_actions(
        make_comment("plan", text),
        make_comment("plan", text, "first-item"),
        make_move("plan", 0, 0),
        make_send(),
        make_post(text),
    )
    _, draft, turns = take_all_actions(board, feedback)
    assert draft == Draft()
    assert turns == [
        Turn(id="u3", actions=(feedback[0].body, feedback[1].body)),
        Turn(id="u4", actions=(feedback[4].body,)),
    ]


@given(st.lists(item_texts(), min_size=4, max_size=4, unique=True))
def test_a_put_on_a_card_of_the_board_is_heard_as_a_diff(texts: list[str]) -> None:
    """Assemble: a board with the agent's list of three items.
    Act: the user puts the list with a new second item, and puts a new card.
    Assert: the draft has the edit as a diff of the changed line with one line around it, and the new card in full."""
    first, second, third, new = texts
    board = Board().apply_action(
        Action(id="a", author=Author.agent, body=make_put("plan", make_list_md("1. ", [first, second, third])))
    )
    _, draft, _ = take_all_actions(
        board, make_user_actions(make_put("plan", make_list_md("1. ", [first, new, third])), make_put("mine", new))
    )
    diff = "\n".join(["@@ -1,3 +1,3 @@", f" 1. {first}", f"-1. {second}", f"+1. {new}", f" 1. {third}"])
    assert draft.actions == (
        TurnAction(id="u0", author=Author.user, body=Edit(kind="edit", id="plan", diff=diff)),
        TurnAction(id="u1", author=Author.user, body=make_put("mine", new)),
    )
