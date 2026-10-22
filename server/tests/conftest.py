from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from tests.conversation import serve


@pytest.fixture(scope="module")
def static_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty directory for the UI, for the tests that do not open the page in a browser."""
    return tmp_path_factory.mktemp("static")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def address(static_dir: Path) -> AsyncIterator[tuple[str, int]]:
    """Host and port of the app on a free port, in the module's event loop."""
    async with serve(static_dir) as address:
        yield address
