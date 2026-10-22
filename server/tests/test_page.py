from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import Browser, Page, async_playwright, expect

from agent_hud.deps import get_hud
from agent_hud.models.actions import ActionKind, Author, Link, Reaction
from agent_hud.models.board import Arrow
from agent_hud.settings import find_static_dir
from tests.conversation import Agent, open_agent
from tests.factories import comment, fill, link, move, put, react, read_board, say

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(scope="module")
def static_dir() -> Path:
    """The built UI, so that the browser opens the page that users see."""
    return find_static_dir()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def browser() -> AsyncIterator[Browser]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        yield browser
        await browser.close()


@pytest_asyncio.fixture(loop_scope="module")
async def agent(address: tuple[str, int]) -> AsyncIterator[Agent]:
    """An agent on a new board."""
    get_hud.cache_clear()
    async with open_agent(address) as agent:
        yield agent


@pytest_asyncio.fixture(loop_scope="module")
async def page(browser: Browser, address: tuple[str, int], agent: Agent) -> AsyncIterator[Page]:
    """The board page in the browser, live on the agent's board."""
    host, port = address
    page = await browser.new_page(viewport={"width": 1440, "height": 900})
    await page.goto(f"http://{host}:{port}/")
    await expect(page.get_by_label("Message the agent")).to_be_visible()
    yield page
    await page.close()


async def snap(page: Page, path: Path) -> None:
    """A screenshot once the animations that end have ended or stopped."""
    await page.evaluate(
        "Promise.all(document.getAnimations()"
        ".filter(a => a.effect?.getComputedTiming().iterations !== Infinity)"
        ".map(a => a.finished.catch(() => null)))"
    )
    await page.screenshot(path=path)


async def send(page: Page) -> None:
    await page.get_by_label("Send to the agent").click()


async def test_the_user_reviews_a_plan_in_the_browser(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a plan of three steps and asks the user to review it.
    Act: the user rejects step 2 with the quick reaction, comments on it and sends; the agent answers and puts a new plan; the user opens the history and sends a chat message.
    Assert: the agent hears the user's turns, the chat shows the agent's answer on plan/2, the new plan closes the old feedback and shows in the history with it; a screenshot of each turn goes in tmp_path."""
    await agent.write(put("plan", "1. parse\n2. rewrite the cache\n3. render"), say("Review the plan"))
    await expect(page.locator('[data-ref="plan/3"]')).to_have_text("render")
    await expect(page.get_by_label("Chat with the agent")).to_contain_text("Review the plan")
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("your turn")
    await snap(page, tmp_path / "1-plan.png")

    await page.locator('[data-ref="plan/2"]').hover()
    await page.get_by_label("reject plan/2").click()
    await page.locator('[data-ref="plan/2"]').click()
    await page.get_by_label("Comment").fill("the cache is shared")
    await page.get_by_label("Comment").press("Enter")
    await expect(page.get_by_label("2 unsent")).to_be_visible()
    await send(page)
    assert await agent.hear() == [react("plan/2", Reaction.reject), comment("plan/2", "the cache is shared")]
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("working on your turn")
    await expect(page.get_by_label("reject plan/2")).to_have_attribute("aria-pressed", "true")
    await snap(page, tmp_path / "2-review.png")

    await agent.write(comment("plan/2", "Who else reads it?"))
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("Agent connected · your turn")
    await expect(page.get_by_label("Feedback on plan/2")).to_contain_text("Who else reads it?")
    chat = page.get_by_label("Chat with the agent")
    await expect(chat).to_contain_text("Who else reads it?")
    await expect(chat.get_by_label("Show plan/2")).to_have_count(2)
    await snap(page, tmp_path / "3-answer.png")

    await agent.write(put("plan", "1. parse\n2. keep the cache\n3. render"), say("I kept the cache"))
    await expect(page.locator('[data-ref="plan/2"]')).to_have_text("keep the cache")
    await expect(page.get_by_label("Feedback on plan/2")).to_be_hidden()
    await expect(page.get_by_label("reject plan/2")).to_have_attribute("aria-pressed", "false")
    await page.get_by_label("History of plan").click()
    old = page.get_by_label("plan version 1")
    await expect(old).to_contain_text("rewrite the cache")
    await expect(old).to_contain_text("the cache is shared")
    await expect(page.locator('[data-ref="plan/2"]')).to_have_count(1)
    await snap(page, tmp_path / "4-history.png")

    await page.get_by_label("Close the history").click()
    await page.get_by_label("Message the agent").fill("go ahead")
    await page.get_by_label("Message the agent").press("Enter")
    assert await agent.hear() == [say("go ahead")]
    await expect(page.get_by_label("Chat with the agent")).to_contain_text("go ahead")
    await snap(page, tmp_path / "5-go.png")


async def test_the_user_fills_a_table_in_the_browser(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a table of tasks with a size, hours and done column.
    Act: the user chooses a size, types the hours, checks a task as done and sends; then the agent asks about the hours.
    Assert: the agent hears each value with the type of its column, reads the same values, and the page keeps them; a screenshot of each turn goes in tmp_path."""
    await agent.write(
        put(
            "tasks",
            "| Task | Size {S, M, L} | Hours {number} | Done {check} |\n|---|---|---|---|\n| parse | | | |\n| render | | | |",
        )
    )
    await expect(page.get_by_label("Input tasks/2/3")).to_have_attribute("placeholder", "…")
    await page.get_by_label("Input tasks/1/2").select_option("M")
    await page.get_by_label("Input tasks/1/3").fill("4")
    await page.get_by_label("Input tasks/1/3").press("Enter")
    await page.get_by_label("Input tasks/2/4").click()
    await expect(page.get_by_label("3 unsent")).to_be_visible()
    await send(page)
    assert await agent.hear() == [fill("tasks/1/2", "M"), fill("tasks/1/3", 4), fill("tasks/2/4", value=True)]
    assert (await read_board(agent.tools)).values == {"tasks/1/2": "M", "tasks/1/3": 4, "tasks/2/4": True}
    await snap(page, tmp_path / "1-filled.png")

    await agent.write(comment("tasks/1", "Do 4 hours cover the tests?"))
    await expect(page.get_by_label("Chat with the agent")).to_contain_text("Do 4 hours cover the tests?")
    await expect(page.get_by_label("Input tasks/1/3")).to_have_value("4")
    await expect(page.get_by_label("Input tasks/2/4")).to_be_checked()
    await snap(page, tmp_path / "2-question.png")


async def test_the_user_draws_an_arrow_between_code_and_an_option_in_the_browser(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: the agent puts a code card in colour, a card of options and a card of questions side by side.
    Act: the user drags the dot of option 2 to the question and sends; then the agent labels the arrow.
    Assert: the agent hears a link from option 2 to the question and reads it with the label, and the page shows the label; a screenshot of each turn goes in tmp_path."""
    await agent.write(
        put("code", "```python\ndef render(md: str) -> str:\n    return md\n```"),
        put("options", "1. highlight on the server\n2. highlight in the browser"),
        put("questions", "1. Which languages?"),
        move("code", 0, 0),
        move("options", 700, 0),
        move("questions", 1140, 0),
    )
    await expect(page.locator('[data-ref="code"] pre.shiki')).to_be_visible()

    await page.locator('[data-ref="options/2"]').hover()
    dot = await page.get_by_label("Draw an arrow from options/2").bounding_box()
    goal = await page.locator('[data-ref="questions/1"]').bounding_box()
    assert dot is not None and goal is not None
    await page.mouse.move(dot["x"] + dot["width"] / 2, dot["y"] + dot["height"] / 2)
    await page.mouse.down()
    await page.mouse.move(goal["x"] + goal["width"] / 2, goal["y"] + goal["height"] / 2, steps=10)
    await page.mouse.up()
    await send(page)
    match await agent.hear():
        case [Link(kind=ActionKind.link, id=arrow_id, src="options/2", dst="questions/1")]:
            pass
        case other:
            pytest.fail(f"the agent heard {other}, not a link from options/2 to questions/1")
    await snap(page, tmp_path / "1-arrow.png")

    await agent.write(link(arrow_id, "options/2", "questions/1", "decides"))
    assert (await read_board(agent.tools)).arrows[arrow_id] == Arrow(
        src="options/2", dst="questions/1", text="decides", author=Author.agent
    )
    await expect(page.get_by_label(f"Text of arrow {arrow_id}")).to_have_value("decides")
    await page.keyboard.press("Escape")
    await page.keyboard.press("Escape")
    await expect(page.get_by_text("decides", exact=True)).to_be_visible()
    await snap(page, tmp_path / "2-label.png")


async def test_the_user_reviews_a_line_of_code_in_the_browser(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a card with inline code and a code block of a file from line 10.
    Act: the user rejects line 2 with the quick reaction, comments on it and sends.
    Assert: the inline code shows no backticks, the block shows the file and the line numbers, and the agent hears the reaction and the comment with the file and line of the part; a screenshot goes in tmp_path."""
    await agent.write(
        put(
            "code",
            "Call `render` once.\n\n```python file=src/render.py start=10\ndef render(md: str) -> str:\n    return md\n```",
        )
    )
    await expect(page.locator('[data-ref="code"] pre.shiki')).to_be_visible()
    await expect(page.locator('[data-ref="code"] figcaption')).to_have_text("src/render.py")
    await expect(page.locator('[data-ref="code/2"]')).to_have_text("11    return md")
    inline = page.locator('[data-ref="code"] p code')
    assert await inline.evaluate("code => getComputedStyle(code, '::before').content") == "none"

    await page.locator('[data-ref="code/2"]').hover()
    await page.get_by_label("reject code/2").click()
    await page.locator('[data-ref="code/2"]').click()
    await page.get_by_label("Comment").fill("md is not html")
    await page.get_by_label("Comment").press("Enter")
    await send(page)
    turn = await agent.turn()
    assert [heard.body for heard in turn.actions] == [
        react("code/2", Reaction.reject),
        comment("code/2", "md is not html"),
    ]
    assert {ref: text for heard in turn.actions for ref, text in heard.parts.items()} == {
        "code/2": "src/render.py:11:     return md"
    }
    await expect(page.get_by_label("reject code/2")).to_have_attribute("aria-pressed", "true")
    await snap(page, tmp_path / "1-line.png")


async def test_a_ref_in_the_chat_shows_the_part(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a plan of two steps.
    Act: the agent says a message that names plan/2, and the user clicks the ref in the chat; then the agent's monitor ends.
    Assert: the page selects plan/2 and opens its feedback, and the pill shows that no agent listens; a screenshot goes in tmp_path."""
    await agent.write(put("plan", "1. parse\n2. render"), say("Is plan/2 needed?"))
    await page.get_by_label("Chat with the agent").get_by_role("button", name="plan/2").click()
    await expect(page.get_by_label("Feedback on plan/2")).to_be_visible()
    await agent.monitor.close()
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("No agent connected")
    await snap(page, tmp_path / "1-ref.png")
