import asyncio
import random
import re
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from playwright.async_api import Browser, Page, async_playwright, expect

from agent_hud.hud import Hud
from agent_hud.models.actions import Action, ActionKind, Author, Link, Reaction
from agent_hud.models.board import Arrow, Card, Point
from agent_hud.settings import find_static_dir
from tests.conversation import TOKEN, Agent, open_agent, open_page, serve
from tests.factories import as_json, comment, fill, link, move, put, react, read_board, remove, restore, say, unlink

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
    await settled(page)

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


async def test_a_fast_drag_from_the_dot_draws_an_arrow_and_its_label_selects_it_for_delete_with_undo(
    page: Page, agent: Agent
) -> None:
    """Assemble: a card of options and a card of questions side by side.
    Act: the pointer jumps from outside the options card straight onto the dot of option 2, drags to the question and
    releases; then clicks the dot without a move; the agent labels the arrow; the user clicks the label, presses Delete,
    clicks Undo in the toast, and sends.
    Assert: the board did not pan and the agent hears the link; the click on the dot opens no feedback; the label click
    selects the arrow, Delete removes it with a toast, Undo links it again, and the agent hears the unlink and the link."""
    await agent.write(
        put("options", "1. highlight on the server\n2. highlight in the browser"),
        put("questions", "1. Which languages?"),
        move("options", 0, 0),
        move("questions", 500, 0),
    )
    card = page.locator('article[data-ref="options"]')
    await expect(card).to_be_visible()
    await settled(page)
    before = await boxes(page, "options")
    dot = await page.get_by_label("Draw an arrow from options/2").bounding_box()
    goal = await page.locator('[data-ref="questions/1"]').bounding_box()
    assert dot is not None and goal is not None
    await page.mouse.move(dot["x"] + 200, dot["y"] + 150)
    await page.mouse.move(dot["x"] + dot["width"] - 6, dot["y"] + dot["height"] / 2, steps=1)
    await page.mouse.down()
    await page.mouse.move(goal["x"] + goal["width"] / 2, goal["y"] + goal["height"] / 2, steps=3)
    await page.mouse.up()
    assert await boxes(page, "options") == before, "a drag from the dot pans nothing"
    await send(page)
    match await agent.hear():
        case [Link(kind=ActionKind.link, id=arrow_id, src="options/2", dst="questions/1")]:
            pass
        case other:
            pytest.fail(f"the agent heard {other}, not a link from options/2 to questions/1")

    await page.mouse.click(dot["x"] + dot["width"] - 6, dot["y"] + dot["height"] / 2)
    await expect(page.get_by_label("Feedback on options/2")).to_have_count(0)

    await agent.write(link(arrow_id, "options/2", "questions/1", "decides"))
    await expect(page.get_by_label(f"Text of arrow {arrow_id}")).to_have_value("decides")
    await page.keyboard.press("Escape")
    await page.keyboard.press("Escape")
    label = page.get_by_label(f"Arrow {arrow_id}: decides")
    await expect(label).to_be_visible()
    await label.click()
    await expect(page.get_by_label(f"Text of arrow {arrow_id}")).to_be_visible()
    await page.keyboard.press("Escape")
    await page.keyboard.press("Delete")
    toast = page.locator('[role="status"]', has_text="Removed the arrow")
    await expect(toast).to_be_visible()
    await expect(label).to_have_count(0)
    await toast.get_by_role("button", name="Undo").click()
    await expect(page.get_by_label(f"Arrow {arrow_id}: decides")).to_be_visible()
    await send(page)
    assert await agent.hear() == [unlink(arrow_id), link(arrow_id, "options/2", "questions/1", "decides")]


async def test_the_user_reviews_a_line_of_code_in_the_browser(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a card with inline code and a code block of a file from line 10.
    Act: the user rejects line 2, which is part 3 after the paragraph, with the quick reaction, comments on it and sends.
    Assert: the inline code shows no backticks, the block shows the file and the line numbers, and the agent hears the reaction and the comment with the file and line of the part; a screenshot goes in tmp_path."""
    await agent.write(
        put(
            "code",
            "Call `render` once.\n\n```python file=src/render.py start=10\ndef render(md: str) -> str:\n    return md\n```",
        )
    )
    await expect(page.locator('[data-ref="code"] pre.shiki')).to_be_visible()
    await expect(page.locator('[data-ref="code"] figcaption')).to_have_text("src/render.py")
    await expect(page.locator('[data-ref="code/3"]')).to_have_text("11    return md")
    inline = page.locator('[data-ref="code"] p code')
    assert await inline.evaluate("code => getComputedStyle(code, '::before').content") == "none"

    await page.locator('[data-ref="code/3"]').hover()
    await page.get_by_label("reject code/3").click()
    await page.locator('[data-ref="code/3"]').click()
    await page.get_by_label("Comment").fill("md is not html")
    await page.get_by_label("Comment").press("Enter")
    await send(page)
    turn = await agent.turn()
    assert [heard.body for heard in turn.actions] == [
        react("code/3", Reaction.reject),
        comment("code/3", "md is not html"),
    ]
    assert {ref: text for heard in turn.actions for ref, text in heard.parts.items()} == {
        "code/3": "src/render.py:11:     return md"
    }
    await expect(page.get_by_label("reject code/3")).to_have_attribute("aria-pressed", "true")
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


async def test_a_card_is_as_wide_as_its_content_up_to_a_column(page: Page, agent: Agent) -> None:
    """Assemble: a short note, a table with three input columns and a long step, and a long paragraph.
    Assert: the note is narrower than 300 pixels; the table's row is one line tall, with its step text on one line and
    wider than 200 pixels; the paragraph's card is a column wide, 640 pixels."""
    step = "Bump the version in the plugin and the server"
    await agent.write(
        put("note", "ok"),
        put(
            "tasks",
            f"| Step | Owner {{agent, user}} | Hours {{number}} | Done {{check}} |\n|---|---|---|---|\n| {step} | | | |",
        ),
        put("prose", " ".join(f"word{n}" for n in range(80))),
    )
    shown = await boxes(page, "note", "tasks", "prose")
    assert shown["note"][2] < 300
    assert shown["prose"][2] == 640
    row = await page.locator('[data-ref="tasks/1"]').bounding_box()
    text = await page.locator('[data-ref="tasks/1"] td').nth(1).bounding_box()
    assert row is not None and text is not None
    assert row["height"] < 48, "the step is on one line"
    assert text["width"] > 200


async def on_top(page: Page, x: float, y: float) -> str | None:
    """The id of the card that shows at the point of the screen, or None when no card does."""
    found = await page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.closest('article[data-ref]')?.dataset.ref ?? null", [x, y]
    )
    return None if found is None else str(found)


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
    Act: open the board in a second tab; the agent puts a taller version of the first card, which reaches the fourth.
    Assert: read has a place for each card, on three columns, with the fourth below the first; the second tab shows
    each card where the first tab does; the fourth card keeps its place, since a place is set once, and the taller first
    card shows over it."""
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
        await expect(page.locator('[data-ref="a/12"]')).to_have_text("step 12")
        tall = await boxes(page, "a", "d")
        assert tall["a"][3] > first["a"][3] + 48, "the taller first card reaches the fourth"
        assert (await read_board(agent.tools)).positions["d"] == board.positions["d"]
        assert tall["d"] == first["d"]
        assert await on_top(page, tall["d"][0] + 40, tall["d"][1] + 10) == "a"


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


async def test_the_editor_saves_with_its_button_and_asks_once_when_a_changed_part_has_feedback(
    page: Page, agent: Agent
) -> None:
    """Assemble: a plan of two steps, where the user approved step 2.
    Act: the user opens the editor with the pencil, changes step 2 and clicks Save, then Keep editing, then saves with
    Ctrl+Enter and Save anyway; then opens the editor again, changes step 1 alone and clicks Save.
    Assert: the editor shows Save and Cancel; the first save asks once, naming one part whose feedback moves, and keeps
    the editor open on Keep editing; Save anyway saves and the approve is gone with the changed text; a change of a part
    without feedback saves without a question."""
    await agent.write(put("plan", "1. parse\n2. render"))
    card = page.locator('article[data-ref="plan"]')
    await page.locator('[data-ref="plan/2"]').hover()
    await page.get_by_label("approve plan/2").click()
    await page.mouse.move(700, 700)
    await expect(card.get_by_role("img", name="user: approve")).to_be_visible()

    await card.hover()
    await page.get_by_label("Edit plan").click()
    box = page.get_by_label("Markdown of plan")
    await expect(box).to_be_visible()
    await expect(card.get_by_role("button", name="Save", exact=True)).to_be_visible()
    await expect(card.get_by_role("button", name="Cancel")).to_be_visible()
    await box.fill("1. parse\n2. render fast")
    await card.get_by_role("button", name="Save", exact=True).click()
    await expect(card.get_by_role("alert")).to_contain_text("moves the feedback on 1 part you changed")
    await card.get_by_role("button", name="Keep editing").click()
    await expect(box).to_be_visible()
    await expect(card.get_by_role("alert")).to_have_count(0)
    await box.press("Control+Enter")
    await card.get_by_role("button", name="Save anyway").click()
    await expect(page.locator('[data-ref="plan/2"]')).to_have_text("render fast")
    await expect(card.get_by_role("img", name="user: approve")).to_have_count(0)

    await card.hover()
    await page.get_by_label("Edit plan").click()
    await box.fill("1. parse the config\n2. render fast")
    await card.get_by_role("button", name="Save", exact=True).click()
    await expect(page.locator('[data-ref="plan/1"]')).to_have_text("parse the config")
    await expect(box).to_have_count(0)


async def test_a_note_lands_in_view_saves_on_a_click_outside_and_opens_no_feedback(page: Page, agent: Agent) -> None:
    """Assemble: an empty board with the chat at the bottom right.
    Act: the user double-clicks near the bottom right of the free space, types a note and clicks elsewhere on the board.
    Assert: the draft is whole inside the viewport and left of the chat; the click outside saves the note as a card by
    the user, with no feedback panel open."""
    await agent.write(say("hello"))
    chat = await page.get_by_role("complementary", name="Chat with the agent").bounding_box()
    assert chat is not None
    await page.mouse.dblclick(chat["x"] - 40, 860)
    draft = page.get_by_role("textbox", name="New note")
    await expect(draft).to_be_visible()
    box = await draft.locator("xpath=ancestor::div[contains(@class, 'absolute')][1]").bounding_box()
    assert box is not None
    assert box["x"] + box["width"] <= chat["x"], "the draft is left of the chat"
    assert box["y"] + box["height"] <= 900, "the draft is above the bottom of the viewport"
    await draft.fill("remember the docs")
    await page.mouse.click(600, 100)
    note = page.locator("article").filter(has_text="remember the docs")
    await expect(note).to_be_visible()
    await expect(note.get_by_role("img", name="By you")).to_be_visible()
    await expect(page.locator('[aria-label^="Feedback on"]')).to_have_count(0)


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


def inside(box: dict[str, float], area: dict[str, float]) -> bool:
    """Whether the box is in the area, both as Playwright gives bounding boxes."""
    return (
        box["x"] >= area["x"]
        and box["y"] >= area["y"]
        and box["x"] + box["width"] <= area["x"] + area["width"]
        and box["y"] + box["height"] <= area["y"] + area["height"]
    )


async def test_the_feedback_panel_stays_in_the_viewport_at_every_zoom(page: Page, agent: Agent) -> None:
    """Assemble: a wide code card near the right edge of the view, and a chat panel at the right.
    Act: the user selects a code line; then zooms out to a third.
    Assert: the panel is inside the viewport, to the left of the card, since the right has no room; zoomed out,
    the panel has the same size, and sits beside the card still, on either side."""
    await agent.write(put("code", "```python\nx = 1\ny = 2\n```"), move("code", 700, 0))
    await page.locator('[data-ref="code/2"]').click()
    panel = page.get_by_label("Feedback on code/2")
    await expect(panel).to_be_visible()
    await settled(page)
    viewport = {"x": 0, "y": 0, "width": 1440, "height": 900}
    before = await panel.bounding_box()
    card = await page.locator('article[data-ref="code"]').bounding_box()
    assert before is not None and card is not None
    assert inside(before, viewport)
    assert before["x"] + before["width"] <= card["x"]
    for _ in range(5):
        await page.keyboard.press("-")
    await settled(page)
    after = await panel.bounding_box()
    card = await page.locator('article[data-ref="code"]').bounding_box()
    assert after is not None and card is not None
    assert round(card["width"]) < 300, "the card is a third of its size"
    assert (round(after["width"]), round(after["height"])) == (round(before["width"]), round(before["height"]))
    assert inside(after, viewport)
    assert after["x"] >= card["x"] + card["width"] or after["x"] + after["width"] <= card["x"]


async def test_the_wheel_over_the_comments_scrolls_them_and_not_the_board(page: Page, agent: Agent) -> None:
    """Assemble: a plan whose first step has thirty comments from the agent.
    Act: the user selects the step and turns the wheel over the comments.
    Assert: the comments scroll, and the card stays where it was."""
    await agent.write(put("plan", "1. parse\n2. render"), *(comment("plan/1", f"note {n}") for n in range(30)))
    await page.locator('[data-ref="plan/1"]').click()
    comments = page.get_by_label("Comments on plan/1")
    await expect(comments).to_be_visible()
    await settled(page)
    card = await boxes(page, "plan")
    box = await comments.bounding_box()
    assert box is not None
    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await page.mouse.wheel(0, 400)
    await expect(comments).not_to_have_js_property("scrollTop", 0)
    assert await boxes(page, "plan") == card


async def test_headings_and_paragraphs_take_feedback(page: Page, agent: Agent) -> None:
    """Assemble: the agent puts a card with a heading, a paragraph and a list.
    Act: the user approves the paragraph with the quick reaction and sends.
    Assert: the heading, the paragraph and the item are parts 1 to 3, the paragraph's feedback opens, and the agent
    hears the reaction with the paragraph's text."""
    await agent.write(put("doc", "# Title\n\nSome prose here.\n\n1. a step"))
    await expect(page.locator('[data-ref="doc/1"]')).to_have_text("Title")
    await expect(page.locator('[data-ref="doc/2"]')).to_have_text("Some prose here.")
    await expect(page.locator('[data-ref="doc/3"]')).to_have_text("a step")
    await page.locator('[data-ref="doc/2"]').click()
    await expect(page.get_by_label("Feedback on doc/2")).to_be_visible()
    await page.keyboard.press("a")
    await send(page)
    turn = await agent.turn()
    assert [heard.body for heard in turn.actions] == [react("doc/2", Reaction.approve)]
    assert [heard.parts for heard in turn.actions] == [{"doc/2": "Some prose here."}]


async def test_a_cell_and_a_header_open_no_feedback_and_c_opens_the_selections(page: Page, agent: Agent) -> None:
    """Assemble: a table with input columns.
    Act: the user focuses a cell with the keyboard and clicks a checkbox; then clicks the card's header and presses C.
    Assert: no feedback opens for the cells; the header click selects the card without its feedback; C opens the
    card's feedback with the comment box focused."""
    await agent.write(
        put("tasks", "| Task | Hours {number} | Done {check} |\n|---|---|---|\n| parse | | |\n| render | | |")
    )
    await page.get_by_label("Input tasks/2/2").focus()
    await page.get_by_label("Input tasks/1/3").click()
    await expect(page.locator('[aria-label^="Feedback on"]')).to_have_count(0)
    card = page.locator('article[data-ref="tasks"]')
    await card.locator("header").click(position={"x": 150, "y": 10})
    await expect(card).to_have_class(re.compile("ring-sky-400"))
    await expect(page.locator('[aria-label^="Feedback on"]')).to_have_count(0)
    await page.keyboard.press("c")
    await expect(page.get_by_label("Feedback on tasks")).to_be_visible()
    await expect(page.get_by_label("Comment")).to_be_focused()


async def test_escape_closes_the_feedback_then_the_selection_and_the_pending_list(page: Page, agent: Agent) -> None:
    """Assemble: a plan.
    Act: the user clicks step 2, focuses the comment box and presses Esc, then A; presses Esc and A again; then opens
    the list of what Send carries and presses Esc; opens it again and clicks the empty board.
    Assert: the first Esc closes the panel and keeps step 2 selected, so A approves it; the second Esc clears the
    selection, so A changes nothing; Esc and a click outside close the list."""
    await agent.write(put("plan", "1. parse\n2. render"))
    part = page.locator('[data-ref="plan/2"]')
    await part.click()
    panel = page.get_by_label("Feedback on plan/2")
    await expect(panel).to_be_visible()
    await page.get_by_label("Comment").focus()
    await page.keyboard.press("Escape")
    await expect(panel).to_have_count(0)
    await page.keyboard.press("a")
    await page.mouse.move(700, 700)
    await expect(part.get_by_role("img", name="user: approve")).to_be_visible()
    await page.keyboard.press("Escape")
    await page.keyboard.press("a")
    await expect(part.get_by_role("img", name="user: approve")).to_be_visible()
    chevron = page.get_by_label("What goes to the agent")
    pending = page.get_by_label("Pending actions")
    await chevron.click()
    await expect(pending).to_be_visible()
    await page.keyboard.press("Escape")
    await expect(pending).to_have_count(0)
    await chevron.click()
    await expect(pending).to_be_visible()
    await page.mouse.click(700, 700)
    await expect(pending).to_have_count(0)


async def test_the_quick_buttons_are_not_in_the_tab_order(page: Page, agent: Agent) -> None:
    """Assemble: a table of two rows with a number column.
    Act: the user hovers the first row, so that its quick buttons show, focuses its cell and presses Tab.
    Assert: the focus lands on the second row's cell, past the quick buttons."""
    await agent.write(put("tasks", "| Task | Hours {number} |\n|---|---|\n| parse | |\n| render | |"))
    await page.locator('[data-ref="tasks/1"]').hover()
    await expect(page.get_by_label("approve tasks/1")).to_be_visible()
    await page.get_by_label("Input tasks/1/2").focus()
    await page.keyboard.press("Tab")
    await expect(page.get_by_label("Input tasks/2/2")).to_be_focused()


async def test_the_feedback_panel_keeps_clear_of_the_cards(page: Page, agent: Agent) -> None:
    """Assemble: two cards side by side at the left edge of the view, with a gap narrower than the panel.
    Act: the user clicks a step of the left card.
    Assert: the panel is inside the viewport and covers neither card."""
    await agent.write(
        put("a", "1. parse\n2. render"),
        put("b", "\n".join(f"{n}. step {n}" for n in range(1, 9))),
        move("a", 0, 0),
        move("b", 430, 0),
    )
    await page.locator('[data-ref="a/1"]').click()
    panel = await page.get_by_label("Feedback on a/1").bounding_box()
    assert panel is not None
    shown = await boxes(page, "a", "b")
    assert inside(panel, {"x": 0, "y": 0, "width": 1440, "height": 900})
    assert (
        crossing(
            {"panel": (round(panel["x"]), round(panel["y"]), round(panel["width"]), round(panel["height"])), **shown}
        )
        == []
    )


async def test_a_card_out_of_view_gets_a_chip_that_shows_it(page: Page, agent: Agent) -> None:
    """Assemble: the agent puts a card in view, then one far to the right and below.
    Act: the user clicks the chip for the far card.
    Assert: a chip names the far card at the edge of the view, clear of the chat, and none names the near card;
    after the click the far card is in view, clear of the chat, and the chip is gone."""
    await agent.write(put("near", "1. here"), put("far", "1. there"), move("far", 2600, 1800))
    chip = page.get_by_label("New card far")
    await expect(chip).to_be_visible()
    await expect(page.get_by_label("New card near")).to_have_count(0)
    await settled(page)
    box = await chip.bounding_box()
    chat = await page.get_by_label("Chat with the agent").bounding_box()
    assert box is not None and chat is not None
    assert inside(box, {"x": 0, "y": 0, "width": chat["x"], "height": 900})
    await chip.click()
    await expect(chip).to_have_count(0)
    await settled(page)
    card = await page.locator('article[data-ref="far"]').bounding_box()
    assert card is not None
    assert inside(card, {"x": 0, "y": 0, "width": chat["x"], "height": 900})


async def test_fit_all_keeps_the_cards_clear_of_the_chat(page: Page, agent: Agent) -> None:
    """Assemble: two cards far apart, and the chat open at the right.
    Act: the user presses 1.
    Assert: both cards are inside the viewport to the left of the chat."""
    await agent.write(put("a", "1. one"), put("b", "1. two"), move("a", 0, 0), move("b", 2600, 1800))
    await expect(page.locator('article[data-ref="b"]')).to_be_attached()
    await page.keyboard.press("1")
    await settled(page)
    chat = await page.get_by_label("Chat with the agent").bounding_box()
    assert chat is not None
    for card_id in "ab":
        card = await page.locator(f'article[data-ref="{card_id}"]').bounding_box()
        assert card is not None
        assert inside(card, {"x": 0, "y": 0, "width": chat["x"], "height": 900}), card_id


async def test_the_user_drags_the_chat_to_a_width_that_the_browser_keeps(page: Page) -> None:
    """Act: the user drags the chat's left edge 120 px to the left, then reloads the page.
    Assert: the chat is 120 px wider, and still after the reload."""
    chat = page.get_by_label("Chat with the agent")
    await settled(page)
    before = await chat.bounding_box()
    handle = await page.get_by_label("Resize the chat").bounding_box()
    assert before is not None and handle is not None
    await page.mouse.move(handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2)
    await page.mouse.down()
    await page.mouse.move(handle["x"] + handle["width"] / 2 - 120, handle["y"] + handle["height"] / 2, steps=5)
    await page.mouse.up()
    after = await chat.bounding_box()
    assert after is not None and round(after["width"]) == round(before["width"]) + 120
    await page.reload()
    await expect(chat).to_be_visible()
    await settled(page)
    again = await chat.bounding_box()
    assert again is not None and round(again["width"]) == round(after["width"])


async def test_the_page_lists_the_boards_and_opens_another(page: Page, agent: Agent, address: tuple[str, int]) -> None:
    """Assemble: an agent in a project puts a card on the project's board, while the page shows the shared board.
    Act: the user opens the menu of boards and clicks the project's board.
    Assert: the menu names the shared board as the page's, and the project's board with one card; the page then shows
    the project's board with the card, and names it."""
    host, port = address
    project = StreamableHttpTransport(
        f"http://{host}:{port}/mcp/", headers={"X-Agent-Hud-Board": "/home/me/demo"}, auth=TOKEN
    )
    async with Client(project) as tools:
        await tools.call_tool("write", {"actions": as_json(put("plan", "1. a"))})
        board = str((await tools.call_tool("listen", {})).structured_content["board"])  # type: ignore[index]
    await agent.write(put("shared-note", "1. b"))
    await expect(page.locator('article[data-ref="shared-note"]')).to_be_visible()
    await page.get_by_label("Boards").click()
    menu = page.get_by_role("menu", name="Other boards")
    await expect(menu.get_by_role("menuitem", name=re.compile("^shared"))).to_have_attribute("aria-current", "page")
    item = menu.get_by_role("menuitem", name=re.compile(f"^{board} 1 card$"))
    await expect(item).to_be_visible()
    await item.click()
    await expect(page.locator('article[data-ref="plan"]')).to_be_visible()
    await expect(page.locator('article[data-ref="shared-note"]')).to_have_count(0)
    assert f"board={board}" in page.url
    await expect(page.get_by_label("Boards")).to_have_text(board)


async def positions_once(agent: Agent, check: Callable[[dict[str, Point]], bool]) -> dict[str, Point]:
    """The card positions in the agent's read once they pass the check, or after three seconds without it."""
    for _ in range(30):
        positions = (await read_board(agent.tools)).positions
        if check(positions):
            return positions
        await asyncio.sleep(0.1)
    return (await read_board(agent.tools)).positions


async def test_cards_may_cross_after_their_first_place_and_the_one_last_touched_shows_on_top(
    page: Page, agent: Agent
) -> None:
    """Assemble: a tall code card at the top left, and a plan that the agent moves 200 pixels below the code's top, onto it.
    Act: the user clicks the code card's header; then the agent puts a new version of the plan.
    Assert: the plan stays where the agent put it, in the agent's read and on the page, and shows over the code card
    where they cross; after the click the code card shows on top there; after the new version the plan does again."""
    code = "```python\n" + "\n".join(f"line_{n} = {n}" for n in range(1, 12)) + "\n```"
    await agent.write(put("code", code), put("plan", "1. parse\n2. render"), move("code", 0, 0), move("plan", 0, 200))
    await expect(page.locator('[data-ref="plan/2"]')).to_have_text("render")
    shown = await boxes(page, "code", "plan")
    assert shown["code"][3] > 200, "the plan at 200 is on the code card"
    assert (await read_board(agent.tools)).positions["plan"] == Point(x=0, y=200)
    assert shown["plan"][1] == shown["code"][1] + 200
    x, y = shown["plan"][0] + 40, shown["plan"][1] + 10
    assert await on_top(page, x, y) == "plan"

    await page.locator('article[data-ref="code"] header').click(position={"x": 150, "y": 10})
    assert await on_top(page, x, y) == "code"
    assert (await read_board(agent.tools)).positions["plan"] == Point(x=0, y=200), "a touch moves nothing"

    await agent.write(put("plan", "1. parse\n2. render\n3. ship"))
    await expect(page.locator('[data-ref="plan/3"]')).to_have_text("ship")
    assert await on_top(page, x, y) == "plan"


async def test_a_click_on_the_comment_count_opens_the_thread_and_leaves_the_verdict(page: Page, agent: Agent) -> None:
    """Assemble: a plan, where the agent commented on step 2.
    Act: the user hovers step 2 and approves it with the quick button; then hovers again and clicks the comment count.
    Assert: the comment count stays in place while the quick buttons show, beside them and not under them; the click
    opens the feedback on step 2 with the approve still pressed; the agent hears the approve alone, and no question
    button is among the quick buttons."""
    await agent.write(put("plan", "1. parse\n2. render"), comment("plan/2", "the cache is shared"))
    part = page.locator('[data-ref="plan/2"]')
    thread = page.get_by_label("Thread on plan/2")
    await expect(thread).to_be_visible()
    await settled(page)
    resting = await thread.bounding_box()
    await part.hover()
    approve = page.get_by_label("approve plan/2")
    await expect(approve).to_be_visible()
    await expect(page.get_by_label("question plan/2")).to_have_count(0)
    hovered = await thread.bounding_box()
    quick = await approve.bounding_box()
    assert resting is not None and hovered is not None and quick is not None
    assert {k: round(v) for k, v in hovered.items()} == {k: round(v) for k, v in resting.items()}, "the count stays put"
    assert quick["x"] + quick["width"] <= hovered["x"], "the quick buttons sit before the comment count"
    await approve.click()
    await expect(approve).to_have_attribute("aria-pressed", "true")
    await page.mouse.move(0, 0)
    await part.hover()
    await thread.click()
    await expect(page.get_by_label("Feedback on plan/2")).to_be_visible()
    await expect(page.get_by_label("approve plan/2")).to_have_attribute("aria-pressed", "true")
    await send(page)
    assert await agent.hear() == [react("plan/2", Reaction.approve)]


async def test_the_marks_of_a_table_row_sit_before_its_text(page: Page, agent: Agent) -> None:
    """Assemble: a table with a check column.
    Act: the user hovers the first row.
    Assert: the quick buttons sit before the row's text, and the row's checkbox is clear of them by more than their width."""
    await agent.write(put("tasks", "| Task | Done {check} |\n|---|---|\n| parse | |\n| render | |"))
    await positions_once(agent, {"tasks"}.issubset)
    await settled(page)
    row = page.locator('[data-ref="tasks/1"]')
    await row.hover()
    quick = page.get_by_label("approve tasks/1")
    await expect(quick).to_be_visible()
    approve = await quick.bounding_box()
    text = await row.locator("td").nth(1).bounding_box()
    check = await page.get_by_label("Input tasks/1/2").bounding_box()
    assert approve is not None and text is not None and check is not None
    assert approve["x"] + approve["width"] <= text["x"]
    assert check["x"] - (approve["x"] + approve["width"]) > 2 * approve["width"]


async def test_the_quick_reactions_of_a_card_sit_in_line_with_its_header(page: Page, agent: Agent) -> None:
    """Assemble: a card with a heading.
    Act: the user hovers the card's header.
    Assert: the strip of quick reactions is inside the header, to the right of the Remove button and above the heading."""
    await agent.write(put("plan", "# Plan\n\n1. parse"))
    header = page.locator('article[data-ref="plan"] header')
    await header.hover()
    approve = page.get_by_label("approve plan", exact=True)
    await expect(approve).to_be_visible()
    await settled(page)
    strip = await approve.locator("..").bounding_box()
    head = await header.bounding_box()
    remove_button = await page.get_by_label("Remove plan").bounding_box()
    heading = await page.locator('[data-ref="plan/1"]').bounding_box()
    assert strip is not None and head is not None and remove_button is not None and heading is not None
    assert inside(strip, head)
    assert strip["x"] >= remove_button["x"] + remove_button["width"]
    assert strip["y"] + strip["height"] <= heading["y"]


def crossing(shown: dict[str, tuple[int, int, int, int]]) -> list[tuple[str, str]]:
    """The pairs of cards whose screen rects cross."""
    found = list(shown.items())
    return [
        (a, b)
        for i, (a, (ax, ay, aw, ah)) in enumerate(found)
        for b, (bx, by, bw, bh) in found[i + 1 :]
        if ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by
    ]


async def test_new_cards_of_any_size_land_clear_of_each_other(page: Page, agent: Agent) -> None:
    """Assemble: eight cards of a seeded random mix of kinds and lengths: lists, code blocks, prose and tables.
    Act: the agent puts four in one write, then the other four one by one, with the page open.
    Assert: after each write, once every card has a place, no two cards on the page cross each other."""
    chance = random.Random(65)

    def md(n: int) -> str:
        match chance.randrange(4):
            case 0:
                return "\n".join(f"{i}. step {i} of card {n}" for i in range(1, chance.randint(2, 15)))
            case 1:
                return "```python\n" + "\n".join(f"value_{i} = {i}" for i in range(chance.randint(1, 20))) + "\n```"
            case 2:
                return " ".join(f"word{i}" for i in range(chance.randint(3, 120)))
            case _:
                rows = "\n".join(f"| task {i} | |" for i in range(chance.randint(1, 8)))
                return f"| Task | Hours {{number}} |\n|---|---|\n{rows}"

    cards = {f"card{n}": md(n) for n in range(8)}
    written: list[str] = []
    writes = [list(cards)[:4], *([card_id] for card_id in list(cards)[4:])]
    for batch in writes:
        await agent.write(*(put(card_id, cards[card_id]) for card_id in batch))
        written += batch
        placed = await positions_once(agent, set(written).issubset)
        assert set(written) <= set(placed), "every card has a place"
        shown = await boxes(page, *written)
        assert crossing(shown) == [], f"after {batch}: {shown}"
