"""MCP tools. Two tools keep the schema small: `write` changes the canvas, `read` returns what the user did."""

import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.lifespan import lifespan
from fastmcp.tools.function_tool import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.board import Board, OpError
from agent_hud.browser import open_browser
from agent_hud.demo import seed
from agent_hud.ops import Op
from agent_hud.persist import Persistence
from agent_hud.schema import compact_object
from agent_hud.settings import HudSettings
from agent_hud.web import CanvasServer


def build(settings: HudSettings, board: Board | None = None) -> FastMCP:
    board = board or Board(project=Path.cwd().name)
    canvas = CanvasServer(board, settings)
    if settings.state_file is not None:
        persistence = Persistence(board, settings.state_file)
        persistence.load()
        persistence.attach()
    if settings.demo:
        seed(board)
    last_open: float | None = None  # monotonic time; None means never
    last_hint: float | None = None

    @lifespan
    async def stop_canvas(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        try:
            yield {}
        finally:
            await canvas.stop()

    async def viewer_hint() -> str:
        """Open the canvas when no tab shows it; say so at most every few minutes."""
        nonlocal last_open, last_hint
        url = await canvas.ensure_started()
        now = time.monotonic()
        if board.viewers > 0:
            return ""
        if settings.open_browser and (last_open is None or now - last_open > 60) and open_browser(url):
            last_open = last_hint = now
            return f"\n(opened {url} in the browser)"
        if last_hint is not None and now - last_hint < 300:
            return ""
        last_hint = now
        return f"\n(no canvas tab is open: ask the user to open {url})"

    async def write(ops: Annotated[list[Op], Field(min_length=1, description="Operations")]) -> str:
        """Change the canvas the user sees in their browser. Ops run in order, all or nothing.

        put {id, md}: markdown becomes a card. One list -> items the user approves, rejects or
        questions one by one. One table -> rows and cells they can comment on. A header cell with
        {check}, {text}, {number} or {a,b,c} -> an interactive table: the user fills that column.
        Other markdown -> a text card. A leading heading is the title. Re-put keeps feedback on
        unchanged items.

        Labels: `plan` card, `plan.3` item 3, `opts.r2` row 2, `opts.r2.pick` cell, `opts.pick` column.
        set {at, value}; insert {at, value} before `plan.3`, or append at `plan`; remove {at};
        reply {at, text} answers a comment; link {src, dst, text} draws an arrow; clear.
        """
        try:
            board.apply(ops)
        except OpError as exc:
            raise ToolError(str(exc)) from None
        return "ok" + await viewer_hint()

    async def read(
        ctx: Context,
        wait: Annotated[int, Field(ge=0, description="Seconds to wait for Send; 0 returns at once")] = 0,
        show: Annotated[list[str] | None, Field(description="Card ids to dump in full")] = None,
    ) -> str:
        """What the user did on the canvas since your last read, one line per part, e.g.
        `plan.3 approve`, `plan.2 question; "unclear"`, `plan.5 = "new text"`, `opts.r2.pick = yes`,
        `note n4 "..."`, `link l5 plan.6 -> plan.1 "entails?"`, `submit "msg"` (user pressed Send).

        wait=N blocks up to N s until the user presses Send; use after asking for review.
        show=[ids] or ["*"] adds the full current state of those cards.
        """
        hint = await viewer_hint()
        if wait > 0 and not board.unread_submit():
            if not await board.wait_for_viewer(15):
                url = await canvas.ensure_started()
                return f"no canvas tab is open, so nobody can press Send: ask the user to open {url}"

            async def tick(elapsed: float) -> None:
                await ctx.report_progress(elapsed, wait, "waiting for the user to press Send")

            if not await board.wait_for_submit(min(wait, settings.max_wait), tick):
                return f"no Send within {wait}s; {board.pending} unread changes. Read again to keep waiting.{hint}"
        out = board.report()
        if show:
            out += "\n\n" + board.show(show)
        return out + hint

    mcp = FastMCP(
        "agent-hud",
        instructions="agent-hud is a canvas in the user's browser. Put plans, options and trade-off tables there "
        "when you need the user's verdict per item, then call read with wait to receive it.",
        lifespan=stop_canvas,
    )
    tools = [
        FunctionTool.from_function(
            write,
            output_schema=None,
            annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=False, open_world_hint=False),
        ),
        FunctionTool.from_function(
            read, output_schema=None, annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False)
        ),
    ]
    for tool in tools:
        tool.parameters = compact_object(tool.parameters)
        mcp.add_tool(tool)
    return mcp
