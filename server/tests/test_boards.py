import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.boards import Huds, board_id
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, Author
from agent_hud.models.events import AgentState
from tests.factories import put


@given(st.from_regex(r"[A-Za-z0-9_-]{1,64}", fullmatch=True))
def test_a_plain_id_is_its_own_board_id(key: str) -> None:
    """Act: the board id of a plain id.
    Assert: the id itself."""
    assert board_id(key) == key


@pytest.mark.parametrize(
    ("key", "name"),
    [("/home/me/work/agent-hud", "agent-hud"), ("C:\\Users\\me\\My Project", "My-Project"), ("/", "board")],
)
def test_a_path_gives_a_board_id_of_its_last_name_and_a_hash(key: str, name: str) -> None:
    """Act: the board id of a path.
    Assert: the last name of the path, with one letter for each run of other characters, and six hex digits of the whole, so that two paths of one name differ."""
    assert re.fullmatch(rf"{re.escape(name)}-[0-9a-f]{{6}}", board_id(key))
    assert board_id(key) != board_id(f"{key}/x")


def test_the_huds_keep_a_board_for_each_key_in_its_own_file(tmp_path: Path) -> None:
    """Assemble: huds on a directory.
    Act: get the boards of two keys, twice each, and of no key; put a card on one; close them and open huds on the directory again.
    Assert: the same hud for the same key, another for another, the shared one for none; each board has a file named by its id; the new huds open each file, and the card is on its board."""
    huds = Huds(tmp_path)
    one, two = huds.of("/home/me/one"), huds.of("/home/me/two")
    assert one is huds.of("/home/me/one") and one is not two and huds.of(None) is huds.get("shared")
    one.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    assert sorted(file.name for file in tmp_path.glob("*.db")) == sorted(
        f"{board_id(key)}.db" for key in ["/home/me/one", "/home/me/two", "shared"]
    )
    huds.compact()
    huds.close()
    again = Huds(tmp_path)
    opened = again.get(board_id("/home/me/one"))
    assert opened is not None and list(opened.board.cards) == ["plan"]
    assert [board.id for board in again.boards()] == ["shared", board_id("/home/me/one"), board_id("/home/me/two")]
    assert [(board.cards, board.agent) for board in again.boards()][:2] == [(0, AgentState.away), (1, AgentState.away)]
    assert again.get("nowhere") is None
    again.close()


def test_a_given_hud_is_the_shared_board() -> None:
    """Assemble: a hud, and huds without a directory around it.
    Assert: the hud is the shared board, and another key gets a board with no file."""
    hud = Hud()
    huds = Huds(None, shared=hud)
    assert huds.of(None) is hud and huds.of("x") is not hud
