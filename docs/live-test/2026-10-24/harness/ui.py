"""The user's browser, for one step at a time: run a Python file of Playwright calls against the open page.

Usage: uv run --project /home/user/agent-hud/server python ui.py step.py
The step file gets `page` (the open board page), `shot(name)` (a screenshot into shots/, returns its path) and `expect`.
"""
import asyncio
import pathlib
import sys
from playwright.async_api import async_playwright, expect

SHOTS = pathlib.Path(__file__).parent / "shots"

async def main(step: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9333")
        page = browser.contexts[0].pages[0]
        async def shot(name: str) -> str:
            path = SHOTS / f"{name}.png"
            await page.screenshot(path=str(path))
            return str(path)
        code = pathlib.Path(step).read_text()
        scope = {"page": page, "shot": shot, "expect": expect, "asyncio": asyncio}
        exec("async def __step__(page, shot, expect, asyncio):\n" + "".join(f"    {line}\n" for line in code.splitlines()), scope)
        await scope["__step__"](page, shot, expect, asyncio)

asyncio.run(main(sys.argv[1]))
