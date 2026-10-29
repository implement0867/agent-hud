import asyncio
import random
import re
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import Browser, Locator, Page, async_playwright, expect
from sqlalchemy import Engine

from agent_hud.models.actions import Action, ActionKind, Author, Link
from agent_hud.models.board import Card, Point
from agent_hud.models.events import Edit
from agent_hud.settings import find_static_dir
from tests.conversation import TOKEN, Agent, open_agent, open_page, serve
from tests.factories import (
    BOARD,
    BoardExchange,
    as_json,
    comment,
    link,
    move,
    put,
    read_board,
    remove,
    resize,
    restore,
    say,
    unlink,
)

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
    await page.goto(f"http://{host}:{port}/?board={BOARD}&token={TOKEN}")
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


def card(page: Page, card_id: str) -> Locator:
    """The card with the id on the board."""
    return page.locator(f'article[data-card="{card_id}"]')


async def select_words(page: Page, card_id: str, start: str, end: str | None = None) -> None:
    """
    Select the words of the card from the first place of start to the end of the first place of end after it, or of
    start, as a drag over them does, and wait for the toolbar of the selection.
    """
    await expect(card(page, card_id)).to_contain_text(start)
    await page.evaluate(
        """([card, start, end]) => {
          const root = document.querySelector(`article[data-card="${card}"] [data-text-root]`);
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
          const range = document.createRange();
          let begun = false;
          for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
            if (!begun) {
              const at = node.data.indexOf(start);
              if (at === -1) continue;
              range.setStart(node, at);
              begun = true;
              const until = node.data.indexOf(end, at);
              if (until !== -1) { range.setEnd(node, until + end.length); break; }
            } else {
              const until = node.data.indexOf(end);
              if (until !== -1) { range.setEnd(node, until + end.length); break; }
            }
          }
          getSelection().removeAllRanges();
          getSelection().addRange(range);
          document.dispatchEvent(new PointerEvent('pointerup'));
        }""",
        [card_id, start, end or start],
    )
    await expect(page.get_by_role("toolbar", name="On the selection")).to_be_visible()


async def comment_on(page: Page, card_id: str, words: str, text: str, end: str | None = None) -> None:
    """Select the words, or from them to the end words, comment on them with the toolbar and post the comment."""
    await select_words(page, card_id, words, end)
    await page.get_by_role("toolbar", name="On the selection").get_by_role("button", name="Comment").click()
    box = page.get_by_role("textbox", name="Comment")
    await expect(box).to_be_focused()
    await box.fill(text)
    await box.press("Enter")
    await expect(page.get_by_role("textbox", name="Reply")).to_be_visible()


async def select_card(page: Page, card_id: str) -> None:
    """Click the card's padding, clear of its words and its handles, which selects it."""
    box = await card(page, card_id).bounding_box()
    assert box is not None
    await page.mouse.click(box["x"] + box["width"] - 30, box["y"] + box["height"] - 6)


def thread_on(page: Page, quote: str) -> Locator:
    """The open thread on the words."""
    return page.get_by_role("region", name=f"Thread on “{quote}”", exact=True)


def bubble(page: Page, card_id: str) -> Locator:
    """The bubbles of the threads of the card."""
    return card(page, card_id).locator("button[data-thread]")


async def test_the_user_reviews_a_plan_in_the_browser(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a plan of three steps and asks the user to review it.
    Act: the user selects the words of step 2, comments on them and sends; the agent answers in the thread and puts a
    new plan without those words; the user opens the history and sends a chat message.
    Assert: the agent hears the comment with its quote, the bubble counts the agent's answer, the new plan moves the
    thread to the history with its card; a screenshot of each turn goes in tmp_path."""
    await agent.write(put("plan", "1. parse\n2. rewrite the cache\n3. render"), say("Review the plan"))
    await expect(card(page, "plan")).to_contain_text("rewrite the cache")
    await expect(page.get_by_label("Chat with the agent")).to_contain_text("Review the plan")
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("your turn")
    await snap(page, tmp_path / "1-plan.png")

    await comment_on(page, "plan", "rewrite the cache", "the cache is shared")
    await expect(page.get_by_label("1 unsent")).to_be_visible()
    await send(page)
    assert await agent.hear() == [comment("plan", "the cache is shared", "rewrite the cache", 0)]
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("working on your turn")
    await page.keyboard.press("Escape")
    await snap(page, tmp_path / "2-review.png")

    await agent.write(comment("plan", "Who else reads it?", "rewrite the cache"))
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("Agent connected · your turn")
    await expect(bubble(page, "plan")).to_have_attribute("aria-label", re.compile("1 new from the agent"))
    await bubble(page, "plan").click()
    thread = thread_on(page, "rewrite the cache")
    await expect(thread).to_contain_text("Who else reads it?")
    await expect(bubble(page, "plan")).not_to_have_attribute("aria-label", re.compile("new from the agent"))
    await expect(
        page.get_by_label("Chat with the agent").get_by_label("Show the thread on “rewrite the cache”")
    ).to_have_count(2)
    await snap(page, tmp_path / "3-answer.png")

    await agent.write(put("plan", "1. parse\n2. keep the cache\n3. render"), say("I kept the cache"))
    await expect(card(page, "plan")).to_contain_text("keep the cache")
    await expect(thread).to_have_count(0)
    await expect(bubble(page, "plan")).to_have_count(0)
    await page.get_by_label("History of plan").click()
    old = page.get_by_label("plan version 1")
    await expect(old).to_contain_text("rewrite the cache")
    await expect(old).to_contain_text("the cache is shared")
    await snap(page, tmp_path / "4-history.png")

    await page.get_by_label("Close the history").click()
    await page.get_by_label("Message the agent").fill("go ahead")
    await page.get_by_label("Message the agent").press("Enter")
    assert await agent.hear() == [say("go ahead")]
    await expect(page.get_by_label("Chat with the agent")).to_contain_text("go ahead")
    await snap(page, tmp_path / "5-go.png")


async def test_a_box_of_a_table_is_a_checkbox_that_the_agent_hears_as_an_edit(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: the agent puts a table whose first column is boxes, with no header, and an empty cell.
    Act: the user checks the box of the first row and sends.
    Assert: the boxes show as checkboxes, the header over them is empty, the empty cell shows a dash; the agent hears
    an edit whose diff checks the box, and reads the markdown with it; a screenshot goes in tmp_path."""
    await agent.write(put("tasks", "| | Task | Hours |\n|---|---|---|\n| [ ] | parse | 4 |\n| [x] | render | |"))
    boxes_ = card(page, "tasks").get_by_role("checkbox", name="Done")
    await expect(boxes_).to_have_count(2)
    await expect(boxes_.nth(1)).to_be_checked()
    await expect(card(page, "tasks").locator("th").first).to_have_text("")
    await expect(card(page, "tasks").locator("td").last).to_have_text("—")
    await boxes_.first.click()
    await expect(boxes_.first).to_be_checked()
    await expect(page.get_by_label("1 unsent")).to_be_visible()
    await send(page)
    match await agent.hear():
        case [Edit(id="tasks", diff=diff)]:
            assert "-| [ ] | parse | 4 |" in diff
            assert "+| [x] | parse | 4 |" in diff
        case other:
            pytest.fail(f"the agent heard {other}, not an edit of tasks")
    assert "| [x] | parse | 4 |" in (await read_board(agent.tools)).cards["tasks"].md
    await snap(page, tmp_path / "1-checked.png")


async def test_the_user_draws_an_arrow_from_words_to_a_card_and_removes_it_with_undo(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: a card of options and a card of questions side by side.
    Act: the user selects the words of option 2, clicks the arrow button, moves over the questions card and clicks it,
    and sends; the agent labels the arrow; the user clicks the label, presses Delete, clicks Undo, and sends.
    Assert: the questions card shows the drop ring under the pointer; the agent hears a link from the words to the card
    and reads it with the label; Delete removes it with a toast, Undo links it again, and the agent hears both."""
    await agent.write(
        put("options", "1. highlight on the server\n2. highlight in the browser"),
        put("questions", "1. Which languages?"),
        move("options", 0, 0),
        move("questions", 600, 0),
    )
    await expect(card(page, "questions")).to_be_visible()
    await settled(page)
    await select_words(page, "options", "highlight in the browser")
    await page.get_by_label("Draw an arrow from here").click()
    goal = await card(page, "questions").bounding_box()
    assert goal is not None
    await page.mouse.move(goal["x"] + goal["width"] / 2, goal["y"] + goal["height"] / 2, steps=5)
    await expect(card(page, "questions")).to_have_class(re.compile(r"--draw"))
    await page.mouse.click(goal["x"] + goal["width"] / 2, goal["y"] + goal["height"] / 2)
    await expect(card(page, "questions")).not_to_have_class(re.compile(r"--draw"))
    await snap(page, tmp_path / "1-arrow.png")
    await send(page)
    match await agent.hear():
        case [
            Link(
                kind=ActionKind.link,
                id=arrow_id,
                card="options",
                quote="highlight in the browser",
                occurrence=0,
                dst="questions",
            )
        ]:
            pass
        case other:
            pytest.fail(f"the agent heard {other}, not a link from the words to questions")

    await agent.write(link(arrow_id, "options", "questions", "decides", "highlight in the browser"))
    await expect(page.get_by_label(f"Text of arrow {arrow_id}")).to_have_value("decides")
    arrow = (await read_board(agent.tools)).arrows[arrow_id]
    assert (arrow.card, arrow.quote, arrow.dst, arrow.text, arrow.author) == (
        "options",
        "highlight in the browser",
        "questions",
        "decides",
        Author.agent,
    )
    await page.keyboard.press("Escape")
    await page.keyboard.press("Escape")
    label = page.get_by_label(f"Arrow {arrow_id}: decides")
    await expect(label).to_be_visible()
    await label.click()
    await expect(page.get_by_label(f"Text of arrow {arrow_id}")).to_have_value("decides")
    await page.keyboard.press("Escape")
    await page.keyboard.press("Delete")
    toast = page.locator('[role="status"]', has_text="Removed the arrow")
    await expect(toast).to_be_visible()
    await expect(label).to_have_count(0)
    await toast.get_by_role("button", name="Undo").click()
    await expect(page.get_by_label(f"Arrow {arrow_id}: decides")).to_be_visible()
    await send(page)
    assert await agent.hear() == [
        unlink(arrow_id),
        link(arrow_id, "options", "questions", "decides", "highlight in the browser", 0),
    ]


async def test_the_user_reviews_a_line_of_code_in_the_browser(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a card with inline code and a code block of a file from line 10.
    Act: the user selects words of line 11, comments on them and sends.
    Assert: the inline code shows no backticks, the block shows the file above it and the line numbers in the ghost
    ink, its lines do not wrap, and the agent hears the comment on the words without the line number; a screenshot goes
    in tmp_path."""
    await agent.write(
        put(
            "code",
            "Call `render` once.\n\n```python file=src/render.py start=10\ndef render(md: str) -> str:\n    return md\n```",
        )
    )
    code = card(page, "code")
    await expect(code.locator("pre span[style]").first).to_be_visible()
    await expect(code.locator("figcaption")).to_have_text("src/render.py")
    await expect(code.locator("[data-code-line]").nth(1)).to_have_text(re.compile(r"^11\s+return md$"))
    assert await code.locator("[data-code-line]").nth(1).evaluate("line => getComputedStyle(line).whiteSpace") == "pre"
    inline = code.locator("p code")
    assert await inline.evaluate("code => getComputedStyle(code, '::before').content") == "none"

    # The colours split the line into a token for each word.
    await comment_on(page, "code", "return", "md is not html", end="md")
    await send(page)
    assert await agent.hear() == [comment("code", "md is not html", "return md", 0)]
    await snap(page, tmp_path / "1-line.png")


async def test_a_comment_in_the_chat_opens_its_thread(page: Page, agent: Agent, tmp_path: Path) -> None:
    """Assemble: the agent puts a plan of two steps and comments on the words of step 2.
    Act: the user clicks the comment's words in the chat; then the agent's monitor ends.
    Assert: the page opens the thread on those words, and the pill shows that no agent listens; a screenshot goes in tmp_path."""
    await agent.write(put("plan", "1. parse\n2. render"), comment("plan", "Is it needed?", "render"))
    await page.get_by_label("Chat with the agent").get_by_label("Show the thread on “render”").click()
    await expect(thread_on(page, "render")).to_contain_text("Is it needed?")
    await agent.monitor.close()
    await expect(page.get_by_role("status", name="Agent")).to_contain_text("No agent connected")
    await snap(page, tmp_path / "1-thread.png")


async def drag(page: Page, handle: Locator, dx: float, dy: float) -> None:
    """Drag the handle by the distance in screen pixels."""
    box = await handle.bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x + dx, y + dy, steps=10)
    await page.mouse.up()


async def test_a_corner_drag_sets_the_width_and_the_height_which_the_board_keeps(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: the agent puts a plan, and the user writes a note.
    Act: the user drags the bottom right corner of the plan 200 pixels right and 100 down, and reloads the page.
    Assert: the card shows its markdown from its first line, with no strip above it; the plan is 200 pixels wider and
    100 taller after the reload, the agent reads its size, and the user's turn does not carry the resize; a screenshot
    goes in tmp_path."""
    await agent.write(put("plan", "# Plan\n\n1. parse\n2. render"), move("plan", 0, 0))
    plan = card(page, "plan")
    await expect(plan.locator("header")).to_have_count(0)
    await page.mouse.dblclick(300, 600)
    await page.get_by_role("textbox", name="New note").fill("check the docs")
    await page.get_by_role("textbox", name="New note").press("Control+Enter")
    await expect(page.locator("article").filter(has_text="check the docs")).to_be_visible()
    await expect(page.get_by_label("1 unsent")).to_be_visible()

    await settled(page)
    before = await plan.bounding_box()
    assert before is not None
    heading = await plan.locator("h1").bounding_box()
    assert heading is not None and heading["y"] - before["y"] < 20, "the heading is the card's first line"
    await plan.hover()
    await drag(page, page.get_by_label("Resize plan from the bottom right"), 200, 100)
    size = (await read_board(agent.tools)).sizes["plan"]
    assert size.width is not None and size.height is not None
    assert (round(size.width), round(size.height)) == (round(before["width"] + 200), round(before["height"] + 100))
    await page.reload()
    await expect(plan).to_be_visible()
    await settled(page)
    after = await plan.bounding_box()
    assert after is not None
    assert (round(after["width"]), round(after["height"])) == (
        round(before["width"] + 200),
        round(before["height"] + 100),
    )
    await expect(page.get_by_label("1 unsent")).to_be_visible()
    await snap(page, tmp_path / "1-size.png")


async def test_an_edge_drag_sets_one_side_and_a_card_shorter_than_its_text_scrolls(page: Page, agent: Agent) -> None:
    """Assemble: a plan of twenty steps, which the agent makes 160 pixels tall.
    Act: the user drags the plan's left edge 100 pixels left, and turns the wheel over the plan.
    Assert: the card is 160 pixels tall and its text scrolls inside it; the left drag widens the card and moves its
    left edge, which the agent reads as a width and a place, with the height as it was."""
    await agent.write(
        put("plan", "\n".join(f"{n}. step {n}" for n in range(1, 21))), move("plan", 200, 0), resize("plan", height=160)
    )
    plan = card(page, "plan")
    await expect(plan).to_be_visible()
    await settled(page)
    box = await plan.bounding_box()
    assert box is not None and round(box["height"]) == 160
    scroller = plan.locator("div").first
    assert await scroller.evaluate("element => element.scrollHeight > element.clientHeight")
    await page.mouse.move(box["x"] + 60, box["y"] + 80)
    await page.mouse.wheel(0, 200)
    await expect(scroller).not_to_have_js_property("scrollTop", 0)

    await plan.hover()
    await drag(page, page.get_by_label("Resize plan from the left"), -100, 0)
    board = await read_board(agent.tools)
    size = board.sizes["plan"]
    assert size.height == 160
    assert size.width is not None and round(size.width) == round(box["width"] + 100)
    assert round(board.positions["plan"].x) == 100


async def test_a_card_is_as_wide_as_its_content_up_to_a_column(page: Page, agent: Agent) -> None:
    """Assemble: a short note, a table with a long step, and a long paragraph.
    Assert: the note is narrower than 300 pixels; the table's row is one line tall, with its step text on one line and
    wider than 200 pixels; the paragraph's card is a column wide, 640 pixels."""
    step = "Bump the version in the plugin and the server"
    await agent.write(
        put("note", "ok"),
        put("tasks", f"| Step | Owner | Hours |\n|---|---|---|\n| {step} | agent | 2 |"),
        put("prose", " ".join(f"word{n}" for n in range(80))),
    )
    shown = await boxes(page, "note", "tasks", "prose")
    assert shown["note"][2] < 300
    assert shown["prose"][2] == 640
    row = await card(page, "tasks").locator("tbody tr").first.bounding_box()
    text = await card(page, "tasks").locator("tbody td").first.bounding_box()
    assert row is not None and text is not None
    assert row["height"] < 48, "the step is on one line"
    assert text["width"] > 200


async def on_top(page: Page, x: float, y: float) -> str | None:
    """The id of the card that shows at the point of the screen, or None when no card does."""
    found = await page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.closest('article[data-card]')?.dataset.card ?? null", [x, y]
    )
    return None if found is None else str(found)


async def boxes(page: Page, *ids: str) -> dict[str, tuple[int, int, int, int]]:
    """The screen rect of each card, by id, in whole pixels, once the cards have settled."""
    await settled(page)
    rects = {}
    for card_id in ids:
        box = await card(page, card_id).bounding_box()
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
        await other.goto(f"http://{host}:{port}/?board={BOARD}&token={TOKEN}")
        for card_id in "abcd":
            await expect(card(other, card_id)).to_be_visible()
        assert await boxes(other, "a", "b", "c", "d") == first
        await other.close()

        await agent.write(put("a", "\n".join(f"{n}. step {n}" for n in range(1, 13))))
        await expect(card(page, "a")).to_contain_text("step 12")
        tall = await boxes(page, "a", "d")
        assert tall["a"][3] > first["a"][3] + 48, "the taller first card reaches the fourth"
        assert (await read_board(agent.tools)).positions["d"] == board.positions["d"]
        assert tall["d"] == first["d"]
        assert await on_top(page, tall["d"][0] + 40, tall["d"][1] + 10) == "a"


async def test_an_edit_does_not_replace_a_newer_version_unless_the_user_says_so(page: Page, agent: Agent) -> None:
    """Assemble: the agent's plan on the board.
    Act: the user double-clicks the card and types; the agent puts a new version; the user saves with Ctrl+Enter, then clicks Save over it.
    Assert: the editor says the card changed and stays open with the agent's version on the board; after Save over it the card
    has the user's text and keeps the agent's author with edited true."""
    await agent.write(put("plan", "1. parse\n2. render"))
    plan = card(page, "plan")
    await plan.get_by_text("render").dblclick()
    box = page.get_by_label("Markdown of plan")
    await box.fill("1. parse\n2. render\n3. ship")
    await agent.write(put("plan", "1. parse\n2. cache\n3. render"))
    await expect(page.get_by_role("alert")).to_contain_text("new version of this card")
    await box.press("Control+Enter")
    await expect(box).to_be_visible()
    assert (await read_board(agent.tools)).cards["plan"].md == "1. parse\n2. cache\n3. render"
    await page.get_by_role("button", name="Save over it").click()
    await expect(plan).to_contain_text("ship")
    await expect(box).to_have_count(0)
    board = await read_board(agent.tools)
    assert board.cards["plan"] == Card(md="1. parse\n2. render\n3. ship", author=Author.agent, edited=True)


async def test_the_editor_shows_the_save_key_alone_and_asks_only_when_a_question_applies(
    page: Page, agent: Agent
) -> None:
    """Assemble: a plan of two steps, with a thread of the agent on the words of step 2.
    Act: the user opens the editor with E on the selected card, rewords step 2 and saves with Ctrl+Enter, then Keep
    editing, then Ctrl+Enter and Save anyway; opens it again, changes step 1 and clicks outside, then Discard; opens it
    again, changes step 1 and saves with Ctrl+Enter.
    Assert: the editor has the accent ring, the hint names the key and there is no Save or Cancel button; the first save
    asks once, naming one thread whose words go, and Save anyway moves the thread to the history; a click outside with
    changes asks about them, and Discard keeps the card; a change that keeps every quote saves at once."""
    await agent.write(put("plan", "1. parse\n2. render"), comment("plan", "why?", "render"))
    plan = card(page, "plan")
    await expect(bubble(page, "plan")).to_have_count(1)
    await select_card(page, "plan")
    await page.keyboard.press("e")
    box = page.get_by_label("Markdown of plan")
    await expect(box).to_be_focused()
    await expect(plan).to_have_class(re.compile(r"0_0_0_2px_var\(--accent-ring\)"))
    await expect(plan.locator("#editor-keys")).to_have_text(re.compile(r"Ctrl\s*↵\s*save"))
    await expect(plan.get_by_role("button", name="Save", exact=True)).to_have_count(0)
    await expect(plan.get_by_role("button", name="Cancel")).to_have_count(0)
    await expect(plan.get_by_role("alert")).to_have_count(0)

    await box.fill("1. parse\n2. draw")
    await box.press("Control+Enter")
    await expect(plan.get_by_role("alert")).to_contain_text("moves 1 thread or arrow on words you changed")
    await plan.get_by_role("button", name="Keep editing").click()
    await expect(plan.get_by_role("alert")).to_have_count(0)
    await box.press("Control+Enter")
    await plan.get_by_role("button", name="Save anyway").click()
    await expect(plan).to_contain_text("draw")
    await expect(bubble(page, "plan")).to_have_count(0)

    await plan.get_by_text("parse").dblclick()
    await box.fill("1. parse it\n2. draw")
    await page.mouse.click(700, 700)
    await expect(plan.get_by_role("alert")).to_contain_text("Unsaved changes")
    await plan.get_by_role("button", name="Discard").click()
    await expect(box).to_have_count(0)
    assert (await read_board(agent.tools)).cards["plan"].md == "1. parse\n2. draw"

    await plan.get_by_text("parse").dblclick()
    await box.fill("1. parse the config\n2. draw")
    await box.press("Control+Enter")
    await expect(plan).to_contain_text("parse the config")
    await expect(box).to_have_count(0)


async def test_a_note_lands_in_view_saves_on_a_click_outside_and_opens_no_thread(page: Page, agent: Agent) -> None:
    """Assemble: an empty board with the chat at the bottom right.
    Act: the user double-clicks near the bottom right of the free space, types a note and clicks elsewhere on the board.
    Assert: the draft is whole inside the viewport and left of the chat; the click outside saves the note as a card by
    the user, with no thread open."""
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
    board = await read_board(agent.tools)
    assert [found.author for found in board.cards.values()] == [Author.user]
    await expect(page.locator('section[aria-label^="Thread on"]')).to_have_count(0)


async def test_a_removed_card_comes_back_with_undo_or_from_the_history(page: Page, agent: Agent) -> None:
    """Assemble: two cards of the agent, placed, the first with a title.
    Act: the user selects the first and presses Delete, then clicks Undo in the toast; then selects the second, presses
    Backspace and clicks Restore in the history; then sends.
    Assert: the toast names the first card by its title; the first card is back where it was, the second is back, and
    the agent hears the removes and restores."""
    await agent.write(put("a", "# Risks\n\nfirst"), put("b", "second"))
    await expect(card(page, "b")).to_be_visible()
    before = await boxes(page, "a")
    await select_card(page, "a")
    await page.keyboard.press("Delete")
    toast = page.locator('[role="status"]', has_text="Removed “Risks”")
    await expect(toast).to_be_visible()
    await toast.get_by_role("button", name="Undo").click()
    await expect(card(page, "a")).to_be_visible()
    assert await boxes(page, "a") == before
    await select_card(page, "b")
    await page.keyboard.press("Backspace")
    await expect(card(page, "b")).to_have_count(0)
    await page.keyboard.press("h")
    await page.get_by_label("Restore b").click()
    await expect(card(page, "b")).to_be_visible()
    await send(page)
    assert await agent.hear() == [remove("a"), restore("a"), remove("b"), restore("b")]


async def test_a_half_written_comment_survives_the_agents_new_version(page: Page, agent: Agent) -> None:
    """Assemble: the agent's plan.
    Act: the user selects the words of step 2, starts a comment without posting it; the agent puts a new version that
    keeps those words; the user selects them again and clicks Comment.
    Assert: the thread closed with the new version, and when it opens again the box has the text and says the card changed."""
    await agent.write(put("plan", "1. parse\n2. render"))
    await select_words(page, "plan", "render")
    await page.keyboard.press("c")
    await page.get_by_role("textbox", name="Comment").fill("what about the cache")
    await agent.write(put("plan", "1. parse\n2. render\n3. ship"))
    thread = thread_on(page, "render")
    await expect(thread).to_have_count(0)
    await select_words(page, "plan", "render")
    await page.get_by_role("toolbar", name="On the selection").get_by_role("button", name="Comment").click()
    await expect(page.get_by_role("textbox", name="Comment")).to_have_value("what about the cache")
    await expect(thread).to_contain_text("The card changed since you started this comment")


async def test_the_page_keeps_the_board_and_a_draft_while_the_server_is_away(
    browser: Browser, static_dir: Path, tmp_path: Path, engine: Engine, exchange: BoardExchange
) -> None:
    """Assemble: a page on a board with a card, and a half-written chat message.
    Act: stop the server; then start it again on the same port.
    Assert: while the server is away the page shows a banner and still the card; once it is back the banner goes,
    the draft is still in the box, and a message reaches the board."""
    exchange.act([Action(id="a", author=Author.agent, body=put("plan", "1. parse"))])
    async with serve(engine, {}, static_dir, tmp_path) as (host, port):
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(f"http://{host}:{port}/?board={BOARD}&token={TOKEN}")
        await expect(card(page, "plan")).to_be_visible()
        await page.get_by_label("Message the agent").fill("half a thought")
    await expect(page.get_by_role("alert")).to_contain_text("not reachable")
    await expect(card(page, "plan")).to_be_visible()
    async with serve(engine, {}, static_dir, tmp_path, port=port):
        await expect(page.get_by_role("alert")).to_have_count(0, timeout=15000)
        await expect(page.get_by_label("Message the agent")).to_have_value("half a thought")
        await page.get_by_label("Message the agent").press("Enter")
        await expect(page.get_by_label("Chat with the agent")).to_contain_text("half a thought")
    await page.close()
    assert [said.text for said in exchange.board.messages] == ["half a thought"]


async def test_the_shortcut_sheet_names_the_keys_for_the_platform(page: Page) -> None:
    """Act: press ?, then Esc.
    Assert: a dialog of shortcuts opens, with the modifier of the platform and the comment key, and closes."""
    await page.keyboard.press("?")
    sheet = page.get_by_role("dialog", name="Shortcuts")
    await expect(sheet).to_be_visible()
    await expect(sheet).to_contain_text("Ctrl + Enter")
    await expect(sheet).to_contain_text("Comment on the selected words")
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
    await page.goto(f"http://{host}:{port}/?board={BOARD}&token={TOKEN}")
    await expect(card(page, "plan")).to_be_visible()
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


async def test_a_thread_stays_in_the_viewport_at_every_zoom(page: Page, agent: Agent) -> None:
    """Assemble: a code card near the right of the view, with a thread of the agent on a line, and the chat at the right.
    Act: the user opens the thread with its bubble; then zooms out to a third.
    Assert: the thread is 220 pixels wide, inside the viewport and clear of the card; zoomed out, it has the same size
    and still sits inside the viewport, clear of the card."""
    await agent.write(
        put("code", "```python\nx = 1\ny = 2\n```"), move("code", 700, 0), comment("code", "why 2?", "y = 2")
    )
    await bubble(page, "code").click()
    thread = thread_on(page, "y = 2")
    await expect(thread).to_be_visible()
    await settled(page)
    viewport = {"x": 0, "y": 0, "width": 1440, "height": 900}
    before = await thread.bounding_box()
    shown = await card(page, "code").bounding_box()
    assert before is not None and shown is not None
    assert round(before["width"]) == 220
    assert inside(before, viewport)
    assert not overlaps(before, shown)
    for _ in range(5):
        await page.keyboard.press("-")
    await settled(page)
    after = await thread.bounding_box()
    shown = await card(page, "code").bounding_box()
    assert after is not None and shown is not None
    assert round(shown["width"]) < 300, "the card is a third of its size"
    assert (round(after["width"]), round(after["height"])) == (round(before["width"]), round(before["height"]))
    assert inside(after, viewport)
    assert not overlaps(after, shown)


def overlaps(a: dict[str, float], b: dict[str, float]) -> bool:
    """Whether two bounding boxes cross."""
    return (
        a["x"] < b["x"] + b["width"]
        and a["x"] + a["width"] > b["x"]
        and a["y"] < b["y"] + b["height"]
        and a["y"] + a["height"] > b["y"]
    )


async def test_the_wheel_over_the_comments_scrolls_them_and_not_the_board(page: Page, agent: Agent) -> None:
    """Assemble: a plan whose first step has thirty comments from the agent.
    Act: the user opens the thread and turns the wheel over the comments.
    Assert: the comments scroll, and the card stays where it was."""
    await agent.write(put("plan", "1. parse\n2. render"), *(comment("plan", f"note {n}", "parse") for n in range(30)))
    await bubble(page, "plan").click()
    comments = thread_on(page, "parse").get_by_label("Comments")
    await expect(comments).to_be_visible()
    await settled(page)
    shown = await boxes(page, "plan")
    box = await comments.bounding_box()
    assert box is not None
    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await page.mouse.wheel(0, 400)
    await expect(comments).not_to_have_js_property("scrollTop", 0)
    assert await boxes(page, "plan") == shown


async def test_selected_words_open_the_toolbar_and_c_starts_a_thread_on_them(page: Page, agent: Agent) -> None:
    """Assemble: the agent puts a card with a heading, a paragraph and a list, where "step" occurs twice.
    Act: the user selects words across the heading and the paragraph and presses C, comments and sends; then selects
    the second "step" and comments with the toolbar's button, and sends.
    Assert: the toolbar has Comment and Arrow, the comment box takes the focus, and the agent hears each comment with
    its quote as the card shows it and its place, the second at occurrence 1; the words of each thread show a bubble."""
    await agent.write(put("doc", "# Title\n\nSome prose here.\n\n1. a step\n2. another step"))
    await select_words(page, "doc", "Title", "Some prose")
    toolbar = page.get_by_role("toolbar", name="On the selection")
    await expect(toolbar.get_by_role("button")).to_have_count(2)
    await page.keyboard.press("c")
    box = page.get_by_role("textbox", name="Comment")
    await expect(box).to_be_focused()
    await box.fill("merge these")
    await box.press("Enter")
    await send(page)
    assert await agent.hear() == [comment("doc", "merge these", "Title Some prose", 0)]

    await page.keyboard.press("Escape")
    await page.evaluate(
        """() => {
          const items = document.querySelectorAll('article[data-card="doc"] li');
          const node = [...items[1].childNodes].find((child) => child.nodeType === Node.TEXT_NODE);
          const at = node.data.indexOf('step');
          const range = document.createRange();
          range.setStart(node, at);
          range.setEnd(node, at + 4);
          getSelection().removeAllRanges();
          getSelection().addRange(range);
          document.dispatchEvent(new PointerEvent('pointerup'));
        }"""
    )
    await toolbar.get_by_role("button", name="Comment").click()
    await page.get_by_role("textbox", name="Comment").fill("which step?")
    await page.get_by_role("textbox", name="Comment").press("Enter")
    await send(page)
    assert await agent.hear() == [comment("doc", "which step?", "step", 1)]
    await expect(bubble(page, "doc")).to_have_count(2)


async def test_a_click_selects_a_card_which_the_keys_move_and_edit(page: Page, agent: Agent) -> None:
    """Assemble: a plan at a place.
    Act: the user clicks the card's padding, presses ArrowRight and Shift+ArrowDown, then E, then Esc.
    Assert: the click selects the card, with its frame and handles; the keys move it 8 pixels right and 32 down, as
    the agent reads; E opens the editor and Esc closes it."""
    await agent.write(put("plan", "1. parse\n2. render"), move("plan", 100, 100))
    plan = card(page, "plan")
    await expect(plan).to_be_visible()
    await select_card(page, "plan")
    await expect(page.get_by_label("Resize plan from the top left")).to_be_visible()
    await page.mouse.move(700, 700)
    await expect(page.get_by_label("Resize plan from the top left")).to_be_visible()
    await page.keyboard.press("ArrowRight")
    await page.keyboard.press("Shift+ArrowDown")
    positions = await positions_once(agent, lambda found: found.get("plan") == Point(x=108, y=132))
    assert positions["plan"] == Point(x=108, y=132)
    await page.keyboard.press("e")
    box = page.get_by_label("Markdown of plan")
    await expect(box).to_be_visible()
    await page.keyboard.press("Escape")
    await expect(box).to_have_count(0)


async def test_escape_closes_the_thread_then_the_selection_and_the_pending_list(page: Page, agent: Agent) -> None:
    """Assemble: a plan with a comment of the user on its words, not sent.
    Act: the user opens the thread and presses Esc in its reply box; selects words and presses Esc; opens the list of
    what Send carries and presses Esc; opens it again and clicks the empty board.
    Assert: Esc closes the thread, Esc ends the selection of words and its toolbar, and Esc and a click outside close
    the list."""
    await agent.write(put("plan", "1. parse\n2. render"))
    await comment_on(page, "plan", "render", "fast?")
    thread = thread_on(page, "render")
    await page.get_by_role("textbox", name="Reply").focus()
    await page.keyboard.press("Escape")
    await expect(thread).to_have_count(0)
    await bubble(page, "plan").click()
    await expect(thread).to_be_visible()
    await page.keyboard.press("Escape")
    await expect(thread).to_have_count(0)

    await select_words(page, "plan", "parse")
    await page.keyboard.press("Escape")
    await expect(page.get_by_role("toolbar", name="On the selection")).to_have_count(0)

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


async def test_a_thread_keeps_clear_of_the_cards(page: Page, agent: Agent) -> None:
    """Assemble: two cards side by side at the left edge of the view, with a gap narrower than a thread, and a thread
    of the agent on a step of the left card.
    Act: the user opens the thread.
    Assert: the thread is inside the viewport and covers neither card."""
    await agent.write(
        put("a", "1. parse\n2. render"),
        put("b", "\n".join(f"{n}. step {n}" for n in range(1, 9))),
        move("a", 0, 0),
        move("b", 430, 0),
        comment("a", "why?", "parse"),
    )
    await bubble(page, "a").click()
    thread = thread_on(page, "parse")
    await expect(thread).to_be_visible()
    await settled(page)
    panel = await thread.bounding_box()
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
    shown = await card(page, "far").bounding_box()
    assert shown is not None
    assert inside(shown, {"x": 0, "y": 0, "width": chat["x"], "height": 900})


async def test_fit_all_keeps_the_cards_clear_of_the_chat(page: Page, agent: Agent) -> None:
    """Assemble: two cards far apart, and the chat open at the right.
    Act: the user presses 1.
    Assert: both cards are inside the viewport to the left of the chat."""
    await agent.write(put("a", "1. one"), put("b", "1. two"), move("a", 0, 0), move("b", 2600, 1800))
    await expect(card(page, "b")).to_be_attached()
    await page.keyboard.press("1")
    for card_id in "ab":
        await expect(card(page, card_id)).to_be_in_viewport()
    await settled(page)
    chat = await page.get_by_label("Chat with the agent").bounding_box()
    assert chat is not None
    for card_id in "ab":
        shown = await card(page, card_id).bounding_box()
        assert shown is not None
        assert inside(shown, {"x": 0, "y": 0, "width": chat["x"], "height": 900}), card_id


async def test_fit_all_takes_a_card_that_the_resize_observer_has_not_measured_yet(
    browser: Browser, address: tuple[str, int], agent: Agent
) -> None:
    """Assemble: a page whose ResizeObserver reports a card 400 ms late.
    Act: the agent puts two cards far apart, and the user presses 1 as soon as the second card is on the page.
    Assert: both cards come into the viewport."""
    host, port = address
    page = await browser.new_page(viewport={"width": 1440, "height": 900})
    await page.add_init_script(
        "window.ResizeObserver = class extends window.ResizeObserver {"
        " constructor(report) { super((entries, observer) =>"
        " entries.some((entry) => entry.target.matches('article[data-card]'))"
        " ? setTimeout(() => report(entries, observer), 400) : report(entries, observer)); } }"
    )
    await page.goto(f"http://{host}:{port}/?board={BOARD}&token={TOKEN}")
    await expect(page.get_by_label("Message the agent")).to_be_visible()
    await agent.write(put("a", "1. one"), put("b", "1. two"), move("a", 0, 0), move("b", 2600, 1800))
    await expect(card(page, "b")).to_be_attached()
    await page.keyboard.press("1")
    for card_id in "ab":
        await expect(card(page, card_id)).to_be_in_viewport()
    await page.close()


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


async def test_the_page_lists_the_boards_and_opens_another(page: Page, agent: Agent) -> None:
    """Assemble: the agent creates a board demo and puts a card on it, and puts another card on the page's board.
    Act: the user opens the menu of boards and clicks demo.
    Assert: the menu names the page's board as the page's, and demo with one card; the page then shows demo with its
    card, and names it."""
    await agent.tools.call_tool("create_board", {"name": "demo"})
    await agent.tools.call_tool("write", {"name": "demo", "actions": as_json(put("plan", "1. a"))})
    await agent.write(put("here", "1. b"))
    await expect(card(page, "here")).to_be_visible()
    await page.get_by_label("Boards").click()
    menu = page.get_by_role("menu", name="Other boards")
    await expect(menu.get_by_role("menuitem", name=re.compile(f"^{BOARD}"))).to_have_attribute("aria-current", "page")
    item = menu.get_by_role("menuitem", name=re.compile("^demo 1 card$"))
    await expect(item).to_be_visible()
    await item.click()
    await expect(card(page, "plan")).to_be_visible()
    await expect(card(page, "here")).to_have_count(0)
    assert "board=demo" in page.url
    await expect(page.get_by_label("Boards")).to_have_text("demo")


async def test_the_page_without_a_board_lists_the_boards(page: Page, address: tuple[str, int]) -> None:
    """Act: open the page with the token and no board.
    Assert: the page lists the boards, and a click on one opens its page."""
    host, port = address
    await page.goto(f"http://{host}:{port}/?token={TOKEN}")
    boards = page.get_by_role("region", name="Boards")
    await boards.get_by_role("link", name=re.compile(f"^{BOARD}")).click()
    assert f"board={BOARD}" in page.url
    await expect(page.get_by_label("Boards")).to_have_text(BOARD)


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
    Act: the user clicks the code card's padding; then the agent puts a new version of the plan.
    Assert: the plan stays where the agent put it, in the agent's read and on the page, and shows over the code card
    where they cross; after the click the code card shows on top there; after the new version the plan does again."""
    code = "```python\n" + "\n".join(f"line_{n} = {n}" for n in range(1, 12)) + "\n```"
    await agent.write(put("code", code), put("plan", "1. parse\n2. render"), move("code", 0, 0), move("plan", 0, 200))
    await expect(card(page, "plan")).to_contain_text("render")
    shown = await boxes(page, "code", "plan")
    assert shown["code"][3] > 200, "the plan at 200 is on the code card"
    assert (await read_board(agent.tools)).positions["plan"] == Point(x=0, y=200)
    assert shown["plan"][1] == shown["code"][1] + 200
    x, y = shown["plan"][0] + 40, shown["plan"][1] + 10
    assert await on_top(page, x, y) == "plan"

    await page.mouse.click(shown["code"][0] + 6, shown["code"][1] + 40)
    assert await on_top(page, x, y) == "code"
    assert (await read_board(agent.tools)).positions["plan"] == Point(x=0, y=200), "a touch moves nothing"

    await agent.write(put("plan", "1. parse\n2. render\n3. ship"))
    await expect(card(page, "plan")).to_contain_text("ship")
    assert await on_top(page, x, y) == "plan"


async def test_a_bubble_counts_the_agents_new_comments_until_the_user_opens_the_thread(
    page: Page, agent: Agent, browser: Browser, address: tuple[str, int]
) -> None:
    """Assemble: a plan, where the agent commented twice on the words of step 2.
    Act: the user opens the thread with its bubble and closes it; reloads the page; the agent comments again.
    Assert: the bubble is filled with the count 2 and sits in the card's right margin, level with the words; once
    opened it counts nothing new, also after the reload; the agent's next comment counts 1."""
    await agent.write(
        put("plan", "1. parse\n2. render the page"),
        comment("plan", "the cache is shared", "render"),
        comment("plan", "and slow", "render"),
    )
    mark = bubble(page, "plan")
    await expect(mark).to_have_attribute("aria-label", "Thread on “render”, 2 new from the agent")
    await expect(mark).to_have_text("2")
    await settled(page)
    place = await mark.bounding_box()
    shown = await card(page, "plan").bounding_box()
    words = await card(page, "plan").locator("li").nth(1).bounding_box()
    assert place is not None and shown is not None and words is not None
    assert shown["x"] + shown["width"] - 44 <= place["x"] <= shown["x"] + shown["width"]
    assert words["y"] - 4 <= place["y"] <= words["y"] + words["height"]

    await mark.click()
    await expect(thread_on(page, "render")).to_contain_text("and slow")
    await page.keyboard.press("Escape")
    await expect(mark).to_have_attribute("aria-label", "Thread on “render”")
    await page.reload()
    await expect(mark).to_have_attribute("aria-label", "Thread on “render”")
    await agent.write(comment("plan", "still?", "render"))
    await expect(mark).to_have_attribute("aria-label", "Thread on “render”, 1 new from the agent")


async def test_a_thread_on_a_table_cell_has_its_bubble_level_with_the_row(page: Page, agent: Agent) -> None:
    """Assemble: a table of three rows, with a thread of the agent on the hours of the second row.
    Assert: the hours have the bubble in the margin, level with the second row, and numbers are tabular."""
    await agent.write(
        put("tasks", "| Step | Hours |\n|---|---|\n| parse | 1 |\n| render | 25 |\n| ship | 3 |"),
        comment("tasks", "so many?", "25"),
    )
    mark = bubble(page, "tasks")
    await expect(mark).to_be_visible()
    await settled(page)
    row = await card(page, "tasks").locator("tbody tr").nth(1).bounding_box()
    place = await mark.bounding_box()
    assert row is not None and place is not None
    assert row["y"] - 4 <= place["y"] and place["y"] + place["height"] <= row["y"] + row["height"] + 4
    numbers = await card(page, "tasks").locator("table").evaluate("table => getComputedStyle(table).fontVariantNumeric")
    assert numbers == "tabular-nums"


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
                rows = "\n".join(f"| [ ] | task {i} | {i} |" for i in range(chance.randint(1, 8)))
                return f"| | Task | Hours |\n|---|---|---|\n{rows}"

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


def crossing(shown: dict[str, tuple[int, int, int, int]]) -> list[tuple[str, str]]:
    """The pairs of cards whose screen rects cross."""
    found = list(shown.items())
    return [
        (a, b)
        for i, (a, (ax, ay, aw, ah)) in enumerate(found)
        for b, (bx, by, bw, bh) in found[i + 1 :]
        if ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by
    ]


async def test_one_send_in_the_chat_lists_the_changes_by_card_and_marks_them_unsent_until_sent(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: a checklist table with boxes, and a plan.
    Act: the user checks a box and comments on words of the plan; closes and opens the chat; opens the list of what
    Send carries; sends.
    Assert: the toolbar has no Send and keeps its size through all of it; the chat's Send counts 2, and the closed chat
    says so; the thread's bubble and the comment's chat bubble are marked unsent; the list has one line per action,
    the edit under the table's title and the comment under its words under the plan's title; after Send nothing is
    marked unsent, Send is disabled, and the agent hears the two actions; a screenshot goes in tmp_path."""
    await agent.write(
        put("checklist", "| | Task |\n|---|---|\n| [ ] | Build the UI |\n| [ ] | Run make check |"),
        put("plan", "# The plan\n\n1. parse\n2. render"),
    )
    toolbar = page.get_by_role("navigation", name="Tools")
    await expect(toolbar).to_be_visible()
    await expect(toolbar.get_by_label("Send to the agent")).to_have_count(0)
    before = await toolbar.bounding_box()
    await card(page, "checklist").get_by_role("checkbox", name="Done").nth(1).click()
    await comment_on(page, "plan", "render", "fast, please")
    await page.keyboard.press("Escape")
    chat = page.get_by_label("Chat with the agent")
    await expect(chat.get_by_label("2 unsent")).to_be_visible()
    await expect(bubble(page, "plan")).to_have_attribute("data-unsent", "")
    await expect(chat.locator("li[data-unsent]")).to_have_text("“render”fast, pleaseunsent")
    assert await toolbar.bounding_box() == before

    await page.get_by_label("Close the chat").click()
    await expect(page.get_by_label("Open the chat")).to_contain_text("2 to send")
    await page.get_by_label("Open the chat").click()
    await page.get_by_label("What goes to the agent").click()
    pending = page.get_by_label("Pending actions")
    await expect(pending.locator("li")).to_have_count(2)
    await expect(pending.get_by_label("Task").locator("li")).to_have_text(["edited"])
    await expect(pending.get_by_label("The plan").locator("li")).to_have_text(["render“fast, please”"])
    await snap(page, tmp_path / "1-pending.png")

    await send(page)
    match await agent.hear():
        case [Edit(id="checklist"), second]:
            assert second == comment("plan", "fast, please", "render", 0)
        case other:
            pytest.fail(f"the agent heard {other}")
    await expect(page.locator("[data-unsent]")).to_have_count(0)
    await expect(page.locator('[aria-label$=" unsent"]')).to_have_count(0)
    await expect(chat.get_by_label("Send to the agent")).to_be_disabled()
    assert await toolbar.bounding_box() == before
    await snap(page, tmp_path / "2-sent.png")


async def test_the_toolbar_labels_its_controls_and_clear_asks_in_the_board_menu(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: two cards with an arrow between them.
    Act: the user reads the toolbar, fits the cards and resets the view; opens the board menu, chooses Clear this board
    and keeps the board; chooses it again and clears.
    Assert: Note, History, Shortcuts, Look and Fit show their names, and the toolbar has no Clear; after Fit the zoom
    button reads another percentage and resets the view to 100 %, where it is disabled; the confirm is in the page and
    names the board, 2 cards and 1 arrow; Keep leaves the cards; Clear empties the board; screenshots go in tmp_path."""
    await agent.write(
        put("a", "1. parse"),
        put("b", "1. render"),
        move("a", 0, 0),
        move("b", 1400, 0),
        link("ab", "a", "b", quote="parse"),
    )
    await expect(page.locator("article")).to_have_count(2)
    toolbar = page.get_by_role("navigation", name="Tools")
    for name, text in [
        ("New note", "Note"),
        ("History", "History"),
        ("Shortcuts", "Shortcuts"),
        ("Look", "Look"),
        ("Fit all cards", "Fit"),
    ]:
        await expect(toolbar.get_by_role("button", name=name, exact=True)).to_have_text(text)
    await expect(toolbar.get_by_role("button", name="Clear")).to_have_count(0)
    reset = toolbar.get_by_role("button", name="Reset the view")
    await expect(reset).to_have_text("100%")
    await expect(reset).to_be_disabled()
    await toolbar.get_by_role("button", name="Fit all cards").click()
    await expect(reset).not_to_have_text("100%")
    await expect(reset).to_be_enabled()
    await snap(page, tmp_path / "1-fit.png")
    await reset.click()
    await expect(reset).to_have_text("100%")
    await expect(reset).to_be_disabled()

    await page.get_by_role("button", name="Boards").click()
    await page.get_by_role("menuitem", name="Clear this board").click()
    dialog = page.get_by_role("dialog", name="Clear this board?")
    await expect(dialog).to_contain_text("Clear test?")
    await expect(dialog).to_contain_text(
        "2 cards go to the history with their feedback. 1 arrow and 0 messages go for good."
    )
    await snap(page, tmp_path / "2-confirm.png")
    await dialog.get_by_role("button", name="Keep").click()
    await expect(dialog).to_have_count(0)
    await expect(page.locator("article")).to_have_count(2)
    await page.get_by_role("button", name="Boards").click()
    await page.get_by_role("menuitem", name="Clear this board").click()
    await dialog.get_by_role("button", name="Clear the board").click()
    await expect(page.locator("article")).to_have_count(0)
    assert (await read_board(agent.tools)).cards == {}
    await page.get_by_role("button", name="Boards").click()
    await expect(page.get_by_role("menuitem", name="Clear this board")).to_be_disabled()


async def test_the_agents_new_version_shows_a_word_diff_until_the_user_hides_it(
    page: Page, agent: Agent, tmp_path: Path
) -> None:
    """Assemble: the agent's plan of a paragraph and three steps.
    Act: the agent puts a version that rewords step 2, replaces step 3 and adds a step; the user clicks Hide changes,
    then Show changes, then picks the line style in the Look menu.
    Assert: "Hide changes · History" sits on the title line and the card has no strip above it; the removed words show
    struck through and the added words tinted, and step 1 is plain; Hide changes shows the new text plain, with Show
    changes in its place; the line style shows the old lines before the new ones; a screenshot goes in tmp_path."""
    await agent.write(put("plan", "# Plan\n\n1. parse\n2. render the page\n3. test"))
    plan = card(page, "plan")
    await expect(plan.get_by_role("button", name="Hide changes")).to_have_count(0)
    await agent.write(put("plan", "# Plan\n\n1. parse\n2. render the whole page\n3. ship\n4. announce"))
    hide = plan.get_by_role("button", name="Hide changes")
    await expect(hide).to_be_visible()
    await expect(plan.locator("header")).to_have_count(0)
    await settled(page)
    title = await plan.locator("h1").bounding_box()
    link_box = await hide.bounding_box()
    history = await plan.get_by_label("History of plan").bounding_box()
    assert title is not None and link_box is not None and history is not None
    assert title["y"] <= link_box["y"] + link_box["height"] / 2 <= title["y"] + title["height"]
    assert link_box["x"] < history["x"]
    await expect(plan.locator("ins.diff-ins")).to_have_text(["whole", "ship", "announce"])
    await expect(plan.locator("del.diff-del")).to_have_text(["test"])
    await expect(plan.locator("li").first).to_have_text("parse")
    await snap(page, tmp_path / "1-diff.png")

    await hide.click()
    await expect(plan.locator("ins, del")).to_have_count(0)
    await expect(plan.locator("li")).to_have_text(["parse", "render the whole page", "ship", "announce"])
    await plan.get_by_role("button", name="Show changes").click()
    await expect(plan.locator("del.diff-del")).to_have_count(1)

    await page.get_by_role("button", name="Look", exact=True).click()
    await page.get_by_role("dialog", name="Look").get_by_role("radio", name="lines").click()
    await page.keyboard.press("Escape")
    await expect(plan.locator(".dl-del")).to_have_count(2)
    await expect(plan.locator(".dl-ins")).to_have_count(3)
    await snap(page, tmp_path / "2-lines.png")


async def test_the_dark_theme_and_the_look_survive_a_reload(page: Page, agent: Agent) -> None:
    """Assemble: a card on the board.
    Act: the user opens the Look menu, picks the dark theme, the violet accent, the compact density and the 16 radius,
    and reloads the page.
    Assert: the root element names each choice, the card's ground is the dark surface, the browser keeps the look under
    agent-hud-look, and all of it holds after the reload."""
    await agent.write(put("plan", "1. parse"))
    await expect(card(page, "plan")).to_be_visible()
    await page.get_by_role("button", name="Look", exact=True).click()
    look = page.get_by_role("dialog", name="Look")
    for group, option in [("Theme", "dark"), ("Accent", "violet"), ("Density", "compact"), ("Radius", "16")]:
        await look.get_by_role("radiogroup", name=group).get_by_role("radio", name=option, exact=True).click()
    root = page.locator("html")
    expected = {"data-theme": "dark", "data-accent": "violet", "data-density": "compact", "data-radius": "16"}
    for _ in range(2):
        for name, value in expected.items():
            await expect(root).to_have_attribute(name, value)
        ground = await card(page, "plan").evaluate("article => getComputedStyle(article).backgroundColor")
        assert ground == "rgb(28, 25, 23)"
        kept = await page.evaluate("JSON.parse(localStorage.getItem('agent-hud-look'))")
        assert {key: kept[key] for key in ("theme", "accent", "density", "radius")} == {
            "theme": "dark",
            "accent": "violet",
            "density": "compact",
            "radius": "16",
        }
        await page.reload()
        await expect(card(page, "plan")).to_be_visible()


async def test_the_history_docks_beside_the_board_and_an_arrow_the_agent_removes_shows(
    page: Page, agent: Agent
) -> None:
    """Assemble: two cards side by side, and an arrow the user draws from words of the first to the second.
    Act: the user opens and closes the history; the agent removes the arrow; the user puts it back; the user collapses
    the chat by its header.
    Assert: while the history is open the card sits to the right of it, moved by the history's width and gap, and it
    is back once the history closes; a toast names the removed arrow by its words and its card, and Put it back links
    it again, after which the toast goes; the chat collapses to its button."""
    await agent.write(put("a", "1. parse"), put("b", "# Render\n\n1. render"), move("a", 0, 0), move("b", 500, 0))
    first = card(page, "a")
    await expect(first).to_be_visible()
    await settled(page)
    before = await first.bounding_box()
    assert before is not None
    await page.keyboard.press("h")
    drawer = page.get_by_role("complementary", name="History")
    await expect(drawer).to_be_visible()
    await settled(page)
    box = await drawer.bounding_box()
    moved = await first.bounding_box()
    assert box is not None and moved is not None
    assert moved["x"] == before["x"] + box["x"] + box["width"] + 16
    await page.get_by_label("Close the history").click()
    await expect(drawer).to_have_count(0)
    await settled(page)
    assert await first.bounding_box() == before

    await select_words(page, "a", "parse")
    await page.get_by_label("Draw an arrow from here").click()
    goal = await card(page, "b").bounding_box()
    assert goal is not None
    await page.mouse.click(goal["x"] + goal["width"] / 2, goal["y"] + goal["height"] / 2)
    arrows = (await read_board(agent.tools)).arrows
    assert len(arrows) == 1
    (arrow_id,) = arrows
    await agent.write(unlink(arrow_id))
    toast = page.get_by_role("status", name="Arrow removed by the agent")
    await expect(toast).to_contain_text("The agent removed your arrow from “parse” to “Render”")
    await toast.get_by_role("button", name="Put it back").click()
    await expect(toast).to_have_count(0)
    assert set((await read_board(agent.tools)).arrows) == {arrow_id}

    await page.get_by_role("button", name="Collapse the chat").click()
    await expect(page.get_by_label("Open the chat")).to_be_visible()
