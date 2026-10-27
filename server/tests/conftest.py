from collections.abc import AsyncIterator, Iterator
from contextlib import closing
from pathlib import Path

import pytest
import pytest_asyncio

from agent_hud.hud import Hud
from tests.conversation import serve
from tests.factories import BOARD, memory_hud


@pytest.fixture(scope="module")
def static_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty directory for the UI, for the tests that do not open the page in a browser."""
    return tmp_path_factory.mktemp("static")


@pytest.fixture(scope="module")
def state_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A directory for the app's token file."""
    return tmp_path_factory.mktemp("state")


@pytest.fixture
def hud() -> Iterator[Hud]:
    """A new hud for each test."""
    with closing(memory_hud()) as hud:
        yield hud


@pytest_asyncio.fixture(loop_scope="module")
async def address(static_dir: Path, state_dir: Path, hud: Hud) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the app on the test's hud as its one board, on a free port, in the module's event loop."""
    async with serve({BOARD: hud}, static_dir, state_dir) as address:
        yield address
