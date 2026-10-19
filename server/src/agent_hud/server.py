from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.lifespan import lifespan
from fastmcp.tools.function_tool import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_hud.agent import OpError, apply
from agent_hud.board import open_board
from agent_hud.hub import Hub
from agent_hud.ops import Op
from agent_hud.report import report, show_cards
from agent_hud.schema import compact
from agent_hud.settings import HudSettings
from agent_hud.state import Delta
from agent_hud.web import CanvasServer


def build(settings: HudSettings, hub: Hub | None = None) -> FastMCP:
    hub = hub or open_board(settings)
    canvas = CanvasServer(hub, settings)

    @lifespan
    async def stop_canvas(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        try:
            yield {}
        finally:
            await canvas.stop()

    async def write(ops: Annotated[list[Op], Field(min_length=1, description="Operations")]) -> str:
        """Change the canvas the user sees in their browser. Ops run in order, all or nothing.

        put {id, md}: markdown becomes a card. One list -> items the user approves, rejects or
        questions one by one. One table -> rows and cells they can comment on; a header cell with
        {check}, {text}, {number} or {a,b,c} makes that column an input the user fills.
        Other markdown -> a text card. A leading heading is the title. Re-put keeps feedback on
        unchanged items.

        Labels: `plan` card, `plan.3` item 3, `opts.r2` row 2, `opts.r2.pick` cell, `opts.pick` column.
        set {at, value}; insert {at, value} before `plan.3`, or append at `plan`; remove {at};
        reply {at, text} answers a comment; link {src, dst, text} draws an arrow; clear.
        """
        try:
            hub.publish(apply(hub.state, ops))
        except OpError as exc:
            raise ToolError(str(exc)) from None
        return "ok" + await canvas.viewer_hint()

    async def read(
        ctx: Context,
        wait: Annotated[int, Field(ge=0, description="Seconds to wait for Send; 0 returns at once")] = 0,
        show: Annotated[list[str] | None, Field(description="Card ids to dump in full")] = None,
    ) -> str:
        """What the user did on the canvas since your last read, one line per part, e.g.
        `plan.3 approve`, `plan.2 question; "unclear"`, `plan.5 = "new text"`, `opts.r2.pick = "x"`,
        `n4: note "..."`, `link l5 plan.6 -> plan.1 "entails?" by user`, `submit "msg"` (user pressed Send).

        wait=N blocks up to N s until the user presses Send; use after asking for review.
        show=[ids] or ["*"] adds the full current state of those cards.
        """
        hint = await canvas.viewer_hint()
        if wait > 0 and not hub.state.unread_submit():
            if not await hub.wait_for_viewer(15):
                return f"no canvas tab is open, so nobody can press Send: ask the user to open {canvas.url}"

            async def tick(elapsed: float) -> None:
                await ctx.report_progress(elapsed, wait, "waiting for the user to press Send")

            if not await hub.wait_for_submit(min(wait, settings.max_wait), tick):
                pending = hub.state.pending
                return f"no Send within {wait}s; {pending} unread changes. Read again to keep waiting.{hint}"
        out = report(hub.state)
        hub.publish(Delta())
        if show:
            out += "\n\n" + show_cards(hub.state, show)
        return out + hint

    mcp = FastMCP(
        "agent-hud",
        instructions="agent-hud is a canvas in the user's browser. Put plans, options and trade-off tables there "
        "when you need the user's verdict per item, then call read with wait to receive it.",
        lifespan=stop_canvas,
    )
    for fn, annotations in [
        (write, ToolAnnotations(destructive_hint=False, idempotent_hint=False, open_world_hint=False)),
        (read, ToolAnnotations(read_only_hint=True, open_world_hint=False)),
    ]:
        tool = FunctionTool.from_function(fn, output_schema=None, annotations=annotations)
        match compact(tool.parameters):
            case dict() as parameters:
                tool.parameters = parameters
            case _:
                raise TypeError(f"{tool.name} input schema must stay an object")
        mcp.add_tool(tool)
    return mcp
