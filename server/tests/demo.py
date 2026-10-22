"""
Record the screen recording in the README: a scripted review on the board, from the built UI.
Run it with `make demo`, which builds the UI first. It needs ffmpeg.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.async_api import Locator, Page, ViewportSize, async_playwright, expect

from agent_hud.deps import get_hud
from agent_hud.settings import find_static_dir
from tests.conversation import Agent, open_agent, serve
from tests.factories import comment, move, put, say


async def click(page: Page, target: Locator) -> None:
    """Move the pointer to the middle of the target in steps, so that the recording shows it move, then click."""
    box = await target.bounding_box()
    assert box is not None
    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25)
    await page.wait_for_timeout(250)
    await target.click()


async def review(page: Page, agent: Agent) -> None:
    """
    The agent puts a plan and code; the user rejects a step, comments, asks about a code line and sends;
    the agent answers and puts a new plan; the user looks at the old plan in the history and says go ahead.
    """
    await agent.write(
        put(
            "plan",
            "## Cache the parsed cards\n\n1. parse each card once\n2. rewrite the cache\n3. render from the cache",
        ),
        put(
            "code",
            "```python file=src/agent_hud/outline.py start=17\ndef parse(md: str) -> Outline:\n    return Outline(md)\n```",
        ),
        move("plan", 0, 0),
        move("code", 0, 250),
        say("Review the plan, then click Send"),
    )
    await page.wait_for_timeout(1800)

    await click(page, page.locator('[data-ref="plan/2"]'))
    await page.wait_for_timeout(400)
    await click(page, page.get_by_label("Feedback on plan/2").get_by_role("button", name="reject"))
    await page.wait_for_timeout(400)
    await click(page, page.get_by_label("Comment"))
    await page.keyboard.type("the cache is shared with the page", delay=45)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(900)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)

    await click(page, page.locator('[data-ref="code/2"]'))
    await page.wait_for_timeout(300)
    await click(page, page.get_by_label("Feedback on code/2").get_by_role("button", name="question"))
    await page.wait_for_timeout(900)
    await page.keyboard.press("Escape")

    await click(page, page.get_by_label("Send to the agent"))
    await agent.hear()
    await page.wait_for_timeout(1800)

    await agent.write(comment("plan/2", "Then I keep it, and add a lock."))
    await page.wait_for_timeout(1500)
    await agent.write(
        put(
            "plan",
            "## Cache the parsed cards\n\n1. parse each card once\n2. keep the cache, with a lock\n3. render from the cache",
        ),
        say("I kept the cache. The old plan is in the history."),
    )
    await page.wait_for_timeout(1800)

    await click(page, page.get_by_label("History of plan"))
    await page.wait_for_timeout(2600)
    await click(page, page.get_by_label("Close the history"))
    await page.wait_for_timeout(500)

    await click(page, page.get_by_label("Message the agent"))
    await page.keyboard.type("go ahead", delay=60)
    await page.keyboard.press("Enter")
    await agent.hear()
    await page.wait_for_timeout(1800)


async def record(videos: Path) -> Path:
    """The video of the review on a new board, in the videos directory."""
    size = ViewportSize(width=1280, height=720)
    # Videos do not show the pointer, so the page draws a dot where it is.
    pointer = """
        addEventListener("DOMContentLoaded", () => {
          const dot = document.createElement("div");
          dot.style.cssText = "position:fixed;z-index:99999;width:18px;height:18px;margin:-9px 0 0 -9px;"
            + "border-radius:50%;background:rgba(15,23,42,.35);border:2px solid #fff;"
            + "box-shadow:0 1px 4px rgba(0,0,0,.4);pointer-events:none;transition:transform .1s;left:-40px;top:-40px";
          document.body.appendChild(dot);
          addEventListener("mousemove", (e) => { dot.style.left = e.clientX + "px"; dot.style.top = e.clientY + "px"; }, true);
          addEventListener("mousedown", () => { dot.style.transform = "scale(.7)"; }, true);
          addEventListener("mouseup", () => { dot.style.transform = ""; }, true);
        });
    """
    get_hud.cache_clear()
    async with serve(find_static_dir()) as address, open_agent(address) as agent, async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(viewport=size, record_video_dir=videos, record_video_size=size)
        await context.add_init_script(pointer)
        page = await context.new_page()
        await page.goto(f"http://{address[0]}:{address[1]}/")
        await expect(page.get_by_label("Message the agent")).to_be_visible()
        await page.mouse.move(640, 400)
        await page.wait_for_timeout(800)
        await review(page, agent)
        assert page.video is not None
        video = Path(await page.video.path())
        await context.close()
        await browser.close()
    return video


def main(gif: Path) -> None:
    """Record the review, and write it to gif at 960 pixels wide and 10 frames a second."""
    with TemporaryDirectory() as videos:
        video = asyncio.run(record(Path(videos)))
        palette = (
            "split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-i",
                video,
                "-vf",
                f"fps=10,scale=960:-1:flags=lanczos,{palette}",
                gif,
            ],
            check=True,
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
