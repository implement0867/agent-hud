import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_hud.boards import BoardRegistry, BoardSummary, board_id_for_project, parse_board_id
from agent_hud.hud import Hud
from agent_hud.models.actions import Action, Author
from agent_hud.models.events import AgentState
from tests.factories import put


@given(st.from_regex(r"[A-Za-z0-9_-]{1,64}", fullmatch=True))
def test_a_plain_id_is_its_own_board_id(key: str) -> None:
    """Act: the board id of a plain id.
    Assert: the id itself."""
    assert board_id_for_project(key) == key


@pytest.mark.parametrize("text", ["", "a/b", "has space", "x" * 65, "../shared"])
def test_a_board_id_rejects_other_text(text: str) -> None:
    """Act: parse text that is not 1 to 64 letters, digits, _ or -, directly and as a board summary's id.
    Assert: ValueError both times."""
    with pytest.raises(ValueError, match="is not a board id"):
        parse_board_id(text)
    with pytest.raises(ValueError, match="is not a board id"):
        BoardSummary.model_validate({"id": text, "cards": 0, "agent": AgentState.away})


@pytest.mark.parametrize(
    ("key", "name"),
    [("/home/me/work/agent-hud", "agent-hud"), ("C:\\Users\\me\\My Project", "My-Project"), ("/", "board")],
)
def test_a_path_gives_a_board_id_of_its_last_name_and_a_hash(key: str, name: str) -> None:
    """Act: the board id of a path.
    Assert: the last name of the path, with one letter for each run of other characters, and six hex digits of the whole, so that two paths of one name differ."""
    assert re.fullmatch(rf"{re.escape(name)}-[0-9a-f]{{6}}", board_id_for_project(key))
    assert board_id_for_project(key) != board_id_for_project(f"{key}/x")


def test_the_registry_keeps_a_board_for_each_project_in_its_own_file(tmp_path: Path) -> None:
    """Assemble: a registry on a directory.
    Act: get the huds of two projects, twice each, and of no project; put a card on one; close them and open a registry on the directory again.
    Assert: the same hud for the same project, another for another, the default one for none; each board has a file named by its id; the new registry opens each file, and the card is on its board."""
    registry = BoardRegistry(tmp_path)
    one, two = registry.hud_for("/home/me/one"), registry.hud_for("/home/me/two")
    assert (
        one is registry.hud_for("/home/me/one") and one is not two and registry.hud_for(None) is registry.find("shared")
    )
    one.act([Action(id="a", author=Author.agent, body=put("plan", "1. a"))])
    assert sorted(file.name for file in tmp_path.glob("*.db")) == sorted(
        f"{board_id_for_project(key)}.db" for key in ["/home/me/one", "/home/me/two", "shared"]
    )
    registry.compact()
    registry.close()
    again = BoardRegistry(tmp_path)
    opened = again.find(board_id_for_project("/home/me/one"))
    assert opened is not None and list(opened.board.cards) == ["plan"]
    assert [board.id for board in again.summaries()] == [
        "shared",
        board_id_for_project("/home/me/one"),
        board_id_for_project("/home/me/two"),
    ]
    assert [(board.cards, board.agent) for board in again.summaries()][:2] == [
        (0, AgentState.away),
        (1, AgentState.away),
    ]
    assert again.find("nowhere") is None and again.find("../shared") is None
    again.close()


def test_a_given_hud_is_the_default_board() -> None:
    """Assemble: a hud, and a registry without a directory around it.
    Assert: the hud is the default board, and another project gets a board with no file."""
    hud = Hud()
    registry = BoardRegistry(None, default_hud=hud)
    assert registry.hud_for(None) is hud and registry.hud_for("x") is not hud
