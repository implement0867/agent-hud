"""Keeps one headless Chromium open with a CDP port, so that each step connects to the same page."""
import asyncio
import sys
from playwright.async_api import async_playwright

async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--remote-debugging-port=9333"])
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        await page.goto(sys.argv[1])
        print("ready", flush=True)
        await asyncio.Event().wait()

asyncio.run(main())
