from collections import defaultdict
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import Engine

from agent_hud.boards import TBoardName
from agent_hud.database import open_database
from agent_hud.presence import Presence
from tests.conversation import serve
from tests.factories import StoredBoard, create_board


@pytest.fixture(scope="module")
def static_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty directory for the UI, for the tests that do not open the page in a browser."""
    return tmp_path_factory.mktemp("static")


@pytest.fixture(scope="module")
def state_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A directory for the app's token file."""
    return tmp_path_factory.mktemp("state")


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    """A new database for each test, in the test's directory."""
    engine = open_database(tmp_path / "agent-hud.db")
    yield engine
    engine.dispose()


@pytest.fixture
def presences() -> defaultdict[TBoardName, Presence]:
    """The live presence of each board, new for each test."""
    return defaultdict(Presence)


@pytest.fixture
def board(engine: Engine) -> StoredBoard:
    """A new board BOARD in the test's database."""
    return create_board(engine)


@pytest_asyncio.fixture(loop_scope="module")
async def address(
    static_dir: Path,
    tmp_path: Path,
    engine: Engine,
    presences: defaultdict[TBoardName, Presence],
    board: StoredBoard,
) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the app on the test's database, whose one board is BOARD, on a free port, in the module's event loop."""
    async with serve(engine, presences, static_dir, tmp_path) as address:
        yield address
