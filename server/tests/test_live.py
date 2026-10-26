"""
The live check of the monitor channel, on demand: a nested Claude Code session with the plugin opens a monitor on its
board, the user's turn comes after the Monitor tool's cap, and the agent answers it within a minute. It needs `claude`
on the PATH, signed in, and AGENT_HUD_LIVE set; it takes the cap and two minutes, unless AGENT_HUD_LIVE_AFTER gives
the seconds to wait after the monitor opens instead. `make check-live` runs it.
"""

import asyncio
import os
import re
import signal
import socket
import subprocess
import sys
from asyncio.subprocess import Process
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe
from time import monotonic

import pytest
from websockets.asyncio.client import connect

from agent_hud.boards import board_id
from agent_hud.models.actions import Author
from agent_hud.models.events import AgentState, Snapshot
from tests.conversation import User
from tests.factories import comment, say

pytestmark = pytest.mark.skipif(not os.environ.get("AGENT_HUD_LIVE"), reason="set AGENT_HUD_LIVE to run the live check")

BRIEF = """\
You are the agent on the agent-hud board. The user is a person at a browser, who reaches you only through the board.
Use the board skill of the agent-hud plugin.
1. Call the board's listen tool. Open its url with the Monitor tool's ws source, the description board, and timeout_ms as long as the tool allows.
2. Write one card, plan, with a list of two steps, and say one line that asks the user to review it and click Send.
3. Wait for the user's turn on the monitor. Do not poll, do not sleep, and do not use Bash. When the Monitor expires, open it again at once, in the same way.
4. When a turn comes, answer each comment of the user with a comment on the same card and quote, and say one line about what you did. Then wait for the next turn in the same way, until the user says that you are done.
"""


@dataclass
class Session:
    """A nested Claude Code session with the plugin, and what its event stream has shown so far."""

    process: Process
    log: Path
    cap: float | None = None
    """The Monitor's cap in seconds, from the result of the first Monitor call."""
    opened: float | None = None
    """When the first Monitor call returned, by monotonic()."""
    writes: int = 0
    """The write calls so far."""
    lines: list[str] = field(default_factory=list)

    async def follow(self) -> None:
        """Read the session's events to the end, and note the Monitor's cap and each write."""
        assert self.process.stdout is not None
        with self.log.open("a") as log:
            async for raw in self.process.stdout:
                line = raw.decode(errors="replace")
                log.write(line)
                self.lines.append(line)
                if self.cap is None and (found := re.search(r"Monitor started .*?expires in (\d+)(m|s)", line)):
                    self.cap = float(found[1]) * (60 if found[2] == "m" else 1)
                    self.opened = monotonic()
                if '"name":"mcp__plugin_agent-hud_board__write"' in line:
                    self.writes += 1

    async def until(self, check: str, seconds: float) -> None:
        """Wait until the check, an attribute that is set or counts above 0, holds. AssertionError after the seconds."""
        deadline = monotonic() + seconds
        while not getattr(self, check):
            assert monotonic() < deadline, f"no {check} from the session in {seconds:.0f} s; see {self.log}"
            assert self.process.returncode is None, f"the session ended with {self.process.returncode}; see {self.log}"
            await asyncio.sleep(1)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_app(state: Path, port: int, token: str) -> tuple[list[str], dict[str, str]]:
    """
    Start the app on the port with the token through the plugin's hook, with its state in the state dir, as a session's
    start does; the hook then finds it running. The command of the session and the environment that the hook used.
    """
    repo = Path(__file__).resolve().parents[2]
    env = {**os.environ, "AGENT_HUD_PORT": str(port), "AGENT_HUD_TOKEN": token, "XDG_STATE_HOME": str(state)}
    subprocess.run([str(repo / "hooks" / "serve.sh")], env={**env, "CLAUDE_PLUGIN_ROOT": str(repo)}, check=True)
    args = [
        "claude",
        "--plugin-dir",
        str(repo),
        "-p",
        BRIEF,
        "--allowedTools",
        "mcp__plugin_agent-hud_board__*,Monitor,Skill",
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "60",
    ]
    return args, env


def stop_app(state: Path) -> None:
    """Stop the app that the hook started, by the pid it recorded in the state dir."""
    pid_file = state / "agent-hud" / "server.pid"
    if pid_file.exists():
        os.kill(int(pid_file.read_text()), signal.SIGTERM)


@asynccontextmanager
async def nested_session(tmp_path: Path, port: int, token: str) -> AsyncIterator[Session]:
    """A Claude Code session with the plugin in a project of its own, whose hook starts the app on the port, until the context ends."""
    project, state = tmp_path / "project", tmp_path / "state"
    project.mkdir()
    args, env = start_app(state, port, token)
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=project,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    session = Session(process, tmp_path / "session.jsonl")
    reader = asyncio.create_task(session.follow())
    try:
        yield session
    finally:
        if process.returncode is None:
            process.terminate()
            await process.wait()
        await reader
        stop_app(state)


@asynccontextmanager
async def open_page(port: int, token: str, board: str) -> AsyncIterator[User]:
    """A page on the board, as the user's browser opens it, until the context ends."""
    url = f"ws://127.0.0.1:{port}/ws?token={token}&board={board}"
    async with connect(url, origin=f"http://127.0.0.1:{port}", proxy=None) as page:
        yield User(page, Snapshot.model_validate_json(await page.recv()))


async def test_the_agent_answers_a_turn_sent_after_the_monitors_cap(tmp_path: Path) -> None:
    """Assemble: a nested Claude Code session with the plugin, which opens its monitor and puts a plan on its board.
    Act: after the Monitor's cap has passed, the user approves a step and sends a message.
    Assert: the session's first Monitor result names the cap, and the agent writes within a minute of the turn."""
    port, token = free_port(), token_urlsafe(16)
    async with nested_session(tmp_path, port, token) as session:
        await session.until("cap", 180)
        assert session.cap is not None and session.opened is not None
        await session.until("writes", 180)
        board = board_id(str(tmp_path / "project"))
        async with open_page(port, token, board) as user:
            deadline = monotonic() + 120
            while "plan" not in user.board.cards or user.snapshot.agent is AgentState.away:
                assert monotonic() < deadline, f"the page shows no plan with an agent waiting; see {session.log}"
                await user.notes(
                    lambda snapshot: "plan" in snapshot.board.cards and snapshot.agent is not AgentState.away
                )
        after = float(os.environ.get("AGENT_HUD_LIVE_AFTER", session.cap + 60))
        wait = session.opened + after - monotonic()
        print(f"\nthe monitor's cap is {session.cap:.0f} s; the user's turn comes in {wait:.0f} s", file=sys.stderr)
        await asyncio.sleep(max(wait, 0))
        async with open_page(port, token, board) as user:
            said = sum(message.author is Author.agent for message in user.board.messages)
            writes = session.writes
            await user.act(comment("plan", "The steps read well."))
            await user.act(say("The first step is fine. Add a third step."))
            sent = monotonic()
            while session.writes == writes:
                assert monotonic() < sent + 60, (
                    f"the agent did not write within 60 s of the turn, {after:.0f} s after its monitor opened; see {session.log}"
                )
                await asyncio.sleep(1)
            answered = monotonic() - sent
            await user.notes(
                lambda snapshot: sum(message.author is Author.agent for message in snapshot.board.messages) > said
            )
            assert sum(message.author is Author.agent for message in user.board.messages) > said
            print(f"the agent wrote {answered:.0f} s after the turn", file=sys.stderr)
            await user.act(say("You are done."))
