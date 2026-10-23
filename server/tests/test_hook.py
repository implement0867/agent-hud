import asyncio
import os
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

# The app fixture serves in the module's loop, so the tests run there too.
pytestmark = pytest.mark.asyncio(loop_scope="module")

ROOT = Path(__file__).parents[2]
TOOLS = ("sh", "curl", "sed", "grep", "mkdir", "cat", "sleep", "kill", "nohup")


async def run_hook(port: int, state_home: Path, path: str | None = None) -> subprocess.CompletedProcess[str]:
    """The hook run for the port, in a thread so that the servers in the test's loop can answer it."""
    env = os.environ | {
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "AGENT_HUD_PORT": str(port),
        "XDG_STATE_HOME": str(state_home),
    }
    if path is not None:
        env["PATH"] = path
    return await asyncio.to_thread(
        subprocess.run,
        ["sh", str(ROOT / "hooks" / "serve.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.fixture
def path_without_uv(tmp_path: Path) -> str:
    """A PATH of only the tools that the hook uses, so that uv is not on it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in TOOLS:
        if (found := shutil.which(tool)) is not None:
            (bin_dir / tool).symlink_to(found)
    return str(bin_dir)


@pytest_asyncio.fixture(loop_scope="module")
async def other_program() -> AsyncIterator[int]:
    """The port of a server that answers 200 with another body, as a program that is not the app does."""

    async def answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(answer, "127.0.0.1", 0)
    async with server:
        yield server.sockets[0].getsockname()[1]


async def test_hook_exits_at_once_when_this_version_answers(address: tuple[str, int], tmp_path: Path) -> None:
    """Assemble: the app on a port.
    Act: run the hook for that port.
    Assert: exit 0, no message, and no server of its own started."""
    _, port = address
    result = await run_hook(port, tmp_path)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    assert not (tmp_path / "agent-hud" / "server.pid").exists()


async def test_hook_fails_when_another_program_answers(other_program: int, tmp_path: Path) -> None:
    """Assemble: another program on a port.
    Act: run the hook for that port.
    Assert: exit 1, and the message names the port and the variable to set."""
    result = await run_hook(other_program, tmp_path)
    assert result.returncode == 1
    assert f"port {other_program}" in result.stderr
    assert "AGENT_HUD_PORT" in result.stderr


async def test_hook_fails_when_uv_is_not_installed(
    address: tuple[str, int], tmp_path: Path, path_without_uv: str
) -> None:
    """Assemble: a PATH without uv.
    Act: run the hook.
    Assert: exit 1, and the message says where to get uv."""
    _, port = address
    result = await run_hook(port, tmp_path, path_without_uv)
    assert result.returncode == 1
    assert "uv is not installed" in result.stderr
    assert "https://docs.astral.sh/uv/" in result.stderr
