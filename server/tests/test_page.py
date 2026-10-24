import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import Browser, Page, async_playwright, expect

from agent_hud.hud import Hud
from agent_hud.models.actions import Action, ActionKind, Author, Link, Reaction
from agent_hud.models.board import Arrow, Card
from agent_hud.settings import find_static_dir
from tests.conversation import TOKEN, Agent, open_agent, open_page, serve
from tests.factories import comment, fill, link, move, put, react, read_board, remove, restore, say

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
    """An agent on the test's board."""
    async with open_agent(address) as agent:
        yield agent


@pytest_asyncio.fixture(loop_scope="module")
async def page(browser: Browser, address: tuple[str, int], agent: Agent) -> AsyncIterator[Page]:
    """The board page in the browser, live on the agent's board."""
    host, port = address
    page = await browser.new_page(viewport={"width": 1440, "height": 900})
    await page.goto(f"http://{host}:{port}/?token={TOKEN}")
    await expect(page.get_by_label("Message the agent")).to_be_visible()
    yield page
    await page.close()


async def settled(page: Page) -> None:
    """Once the animations that end have ended or stopped."""
    await page.evaluate(
        "Promise.all(document.getAnimations()"
        ".filter(a => a.effect?.getComputedTiming().iterations !== Infinity)"
        ".map(a => a.finished.catch(() => null)))"
    )


async def snap(page: Page, path: Path) -> None:
    """A screenshot once the animations that end have ended or stopped."""
    await settled(page)
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
    Act: the user moves the pointer from option 2 to its dot, as a hand does, drags the dot to the question and sends;
    then the agent labels the arrow.
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
    # The dot is at the right end of its strip; the steps pass each point between the part and the dot.
    await page.mouse.move(dot["x"] + dot["width"] - 6, dot["y"] + dot["height"] / 2, steps=20)
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


async def test_each_card_shows_its_author_and_id_and_the_user_sets_its_width(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: the agent puts a plan, and the user writes a note.
    Act: the user drags the bottom right corner of the plan 200 pixels to the right, and reloads the page.
    Assert: each card shows its id and the icon of its author on the same background; the plan is 200 pixels wider after
    the reload, the agent reads its width, and the user's turn does not carry the resize; a screenshot goes in tmp_path."""
    await agent.write(put("plan", "1. parse\n2. render"), move("plan", 0, 0))
    await page.mouse.dblclick(300, 600)
    await page.get_by_role("textbox", name="New note").fill("check the docs")
    await page.get_by_role("textbox", name="New note").press("Control+Enter")
    note = page.locator("article").filter(has_text="check the docs")
    await expect(note.get_by_role("img", name="By you")).to_be_visible()
    note_id = await note.get_attribute("data-ref")
    assert note_id is not None
    await expect(note.locator("header")).to_contain_text(note_id)
    plan = page.locator('article[data-ref="plan"]')
    await expect(plan.get_by_role("img", name="By the agent")).to_be_visible()
    await expect(plan.locator("header")).to_contain_text("plan")
    background = "article => getComputedStyle(article).backgroundColor"
    assert await note.evaluate(background) == await plan.evaluate(background)
    await expect(page.get_by_label("1 unsent")).to_be_visible()

    before = await plan.bounding_box()
    corner = await page.get_by_role("separator", name="Width of plan").bounding_box()
    assert before is not None and corner is not None
    await page.mouse.move(corner["x"] + corner["width"] / 2, corner["y"] + corner["height"] / 2)
    await page.mouse.down()
    await page.mouse.move(corner["x"] + corner["width"] / 2 + 200, corner["y"] + corner["height"] / 2, steps=10)
    await page.mouse.up()
    assert (await read_board(agent.tools)).widths == {"plan": before["width"] + 200}
    await page.reload()
    await expect(plan).to_be_visible()
    after = await plan.bounding_box()
    assert after is not None and after["width"] == before["width"] + 200
    await expect(page.get_by_label("1 unsent")).to_be_visible()
    await snap(page, tmp_path / "1-width.png")


async def boxes(page: Page, *ids: str) -> dict[str, tuple[int, int, int, int]]:
    """The screen rect of each card, by id, in whole pixels, once the cards have settled."""
    await settled(page)
    rects = {}
    for card_id in ids:
        box = await page.locator(f'article[data-ref="{card_id}"]').bounding_box()
        assert box is not None
        rects[card_id] = (round(box["x"]), round(box["y"]), round(box["width"]), round(box["height"]))
    return rects


async def test_the_page_places_new_cards_where_every_tab_and_the_agent_sees_them(
    page: Page, agent: Agent, browser: Browser, address: tuple[str, int]
) -> None:
    """Assemble: the agent puts four cards with no place, where the first is the shortest.
    Act: open the board in a second tab; the agent puts a taller version of the first card.
    Assert: read has a place for each card, on three columns, with the fourth below the first; the second tab shows
    each card where the first tab does; the fourth card moved down below the taller first card in the agent's read."""
    async with open_page(address) as user:
        await agent.write(
            put("a", "short"), put("b", "1. a\n2. b\n3. c"), put("c", "1. a\n2. b\n3. c"), put("d", "last")
        )
        await user.notes(lambda snapshot: len(snapshot.board.positions) == 4)
        board = await read_board(agent.tools)
        assert {card_id: at.x for card_id, at in board.positions.items()} == {"a": 0, "b": 688, "c": 1376, "d": 0}
        first = await boxes(page, "a", "b", "c", "d")
        assert board.positions["d"].y == first["a"][3] + 48

        host, port = address
        other = await browser.new_page(viewport={"width": 1440, "height": 900})
        await other.goto(f"http://{host}:{port}/?token={TOKEN}")
        for card_id in "abcd":
            await expect(other.locator(f'article[data-ref="{card_id}"]')).to_be_visible()
        assert await boxes(other, "a", "b", "c", "d") == first
        await other.close()

        await agent.write(put("a", "\n".join(f"{n}. step {n}" for n in range(1, 13))))
        await user.notes(lambda snapshot: snapshot.board.positions["d"].y != first["a"][3] + 48)
        board = await read_board(agent.tools)
        tall = await boxes(page, "a", "d")
        assert tall["a"][3] > first["a"][3]
        assert board.positions["d"].y == tall["a"][3] + 48
        assert tall["d"][1] == tall["a"][1] + tall["a"][3] + 48


async def test_an_edit_does_not_replace_a_newer_version_unless_the_user_says_so(page: Page, agent: Agent) -> None:
    """Assemble: the agent's plan on the board.
    Act: the user opens the editor and types; the agent puts a new version; the user saves with Ctrl+Enter, then clicks Save over it.
    Assert: the editor says the card changed and stays open with the agent's version on the board; after Save over it the card
    has the user's text, keeps the agent's author with edited true, and says edited by you."""
    await agent.write(put("plan", "1. parse\n2. render"))
    card = page.locator('article[data-ref="plan"]')
    await card.hover()
    await page.get_by_label("Edit plan").click()
    box = page.get_by_label("Markdown of plan")
    await box.fill("1. parse\n2. render\n3. ship")
    await agent.write(put("plan", "1. parse\n2. cache\n3. render"))
    await expect(page.get_by_role("alert")).to_contain_text("new version of this card")
    await box.press("Control+Enter")
    await expect(box).to_be_visible()
    assert (await read_board(agent.tools)).cards["plan"].md == "1. parse\n2. cache\n3. render"
    await page.get_by_role("button", name="Save over it").click()
    await expect(page.locator('[data-ref="plan/3"]')).to_have_text("ship")
    await expect(card).to_contain_text("edited by you")
    board = await read_board(agent.tools)
    assert board.cards["plan"] == Card(md="1. parse\n2. render\n3. ship", author=Author.agent, edited=True)


async def test_a_removed_card_comes_back_with_undo_or_from_the_history(page: Page, agent: Agent) -> None:
    """Assemble: two cards of the agent, placed.
    Act: the user selects the first and presses Delete, then clicks Undo in the toast; then removes the second with its
    button and clicks Restore in the history; then sends.
    Assert: the first card is back where it was, the second is back, and the agent hears the removes and restores."""
    await agent.write(put("a", "first"), put("b", "second"))
    await expect(page.locator('article[data-ref="b"]')).to_be_visible()
    before = await boxes(page, "a")
    await page.locator('article[data-ref="a"] header').click()
    await page.keyboard.press("Delete")
    toast = page.locator('[role="status"]', has_text="Removed a")
    await expect(toast).to_be_visible()
    await toast.get_by_role("button", name="Undo").click()
    await expect(page.locator('article[data-ref="a"]')).to_be_visible()
    assert await boxes(page, "a") == before
    await page.locator('article[data-ref="b"]').hover()
    await page.get_by_label("Remove b").click()
    await expect(page.locator('article[data-ref="b"]')).to_have_count(0)
    await page.keyboard.press("h")
    await page.get_by_label("Restore b").click()
    await expect(page.locator('article[data-ref="b"]')).to_be_visible()
    await send(page)
    assert await agent.hear() == [remove("a"), restore("a"), remove("b"), restore("b")]


async def test_a_half_written_comment_survives_the_agents_new_version(page: Page, agent: Agent) -> None:
    """Assemble: the agent's plan.
    Act: the user selects plan/2 and types a comment without sending; the agent puts a new version; the user selects plan/2 again.
    Assert: the panel closed with the new version, and when it opens again the box has the text and says the card changed."""
    await agent.write(put("plan", "1. parse\n2. render"))
    await page.locator('[data-ref="plan/2"]').click()
    await page.get_by_label("Comment").fill("what about the cache")
    await agent.write(put("plan", "1. parse\n2. render\n3. ship"))
    await expect(page.get_by_label("Feedback on plan/2")).to_have_count(0)
    await page.locator('[data-ref="plan/2"]').click()
    await expect(page.get_by_label("Comment")).to_have_value("what about the cache")
    await expect(page.get_by_label("Feedback on plan/2")).to_contain_text(
        "The card changed since you started this comment"
    )


async def test_the_page_keeps_the_board_and_a_draft_while_the_server_is_away(
    browser: Browser, static_dir: Path, tmp_path: Path
) -> None:
    """Assemble: a page on a board with a card, and a half-written chat message.
    Act: stop the server; then start it again on the same port.
    Assert: while the server is away the page shows a banner and still the card; once it is back the banner goes,
    the draft is still in the box, and a message reaches the board."""
    hud = Hud()
    hud.act([Action(id="a", author=Author.agent, body=put("plan", "1. parse"))])
    async with serve(hud, static_dir, tmp_path) as (host, port):
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(f"http://{host}:{port}/?token={TOKEN}")
        await expect(page.locator('article[data-ref="plan"]')).to_be_visible()
        await page.get_by_label("Message the agent").fill("half a thought")
    await expect(page.get_by_role("alert")).to_contain_text("not reachable")
    await expect(page.locator('article[data-ref="plan"]')).to_be_visible()
    async with serve(hud, static_dir, tmp_path, port=port):
        await expect(page.get_by_role("alert")).to_have_count(0, timeout=15000)
        await expect(page.get_by_label("Message the agent")).to_have_value("half a thought")
        await page.get_by_label("Message the agent").press("Enter")
        await expect(page.get_by_label("Chat with the agent")).to_contain_text("half a thought")
        assert [said.text for said in hud.board.messages] == ["half a thought"]
    await page.close()


async def test_the_shortcut_sheet_names_the_keys_for_the_platform(page: Page) -> None:
    """Act: press ?, then Esc.
    Assert: a dialog of shortcuts opens, with the modifier of the platform, and closes."""
    await page.keyboard.press("?")
    sheet = page.get_by_role("dialog", name="Shortcuts")
    await expect(sheet).to_be_visible()
    await expect(sheet).to_contain_text("Ctrl + Enter")
    await page.keyboard.press("Escape")
    await expect(sheet).to_have_count(0)


async def test_a_narrow_screen_shows_the_toolbar_whole_above_the_chat(
    browser: Browser, address: tuple[str, int], agent: Agent
) -> None:
    """Assemble: a page 390 px wide, with a card and a message from the agent.
    Assert: the Send button is inside the viewport, the chat ends above the toolbar, and a hover on the message gives its time."""
    host, port = address
    await agent.write(put("plan", "1. parse"), say("hello"))
    page = await browser.new_page(viewport={"width": 390, "height": 800})
    await page.goto(f"http://{host}:{port}/?token={TOKEN}")
    await expect(page.locator('article[data-ref="plan"]')).to_be_visible()
    send_box = await page.get_by_label("Send to the agent").bounding_box()
    toolbar = await page.get_by_role("navigation", name="Tools").bounding_box()
    chat = await page.get_by_label("Chat with the agent").bounding_box()
    assert send_box is not None and toolbar is not None and chat is not None
    assert send_box["x"] >= 0 and send_box["x"] + send_box["width"] <= 390
    assert chat["y"] + chat["height"] <= toolbar["y"]
    title = await page.get_by_label("Chat with the agent").locator("li").first.get_attribute("title")
    assert title is not None and re.search(r"\d{1,2}:\d{2}", title)
    await page.close()
