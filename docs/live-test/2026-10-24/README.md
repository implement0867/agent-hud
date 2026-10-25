# Live test of 2026-10-24: two agents on one board

Two agents used agent-hud at the same time, with no script for what they did, for three rounds, until they agreed on a release checklist. Each logged what was awkward as it went. Every entry has a screenshot in `shots/`.

- **The agent side** was a nested Claude Code session with the plugin (`claude --plugin-dir . -p`), on its own project directory and board. It reached the user only through the MCP tools `write`, `read` and `listen`, and the Monitor tool. Its brief is `harness/agent_brief.md`, its log `agent_findings.md`, and `agent_transcript.md` has every tool call and result.
- **The user side** was a Claude subagent at a headless Chromium, acting only through the page: clicks, typing, drags, keys. It took a screenshot after every step and read it before the next. Its brief is `harness/user_brief.md`, its log `user_findings.md` (45 findings, what was good, and a verdict).
- **The owner** watched the screenshots and added `owner_findings.md`.
- `turns.log` has the four turns the user sent, as the agent's monitor got them. `board.json` is the final board with its history.

## How to run it again

`harness/` has what the run needs: the plugin's own hook starts the server (`hooks/serve.sh` with `AGENT_HUD_PORT`, `AGENT_HUD_TOKEN` and `XDG_STATE_HOME` set), `browser_host.py` keeps one Chromium open on the board with a CDP port, `ui.py` runs one step of Playwright against that page, and `watchdog.py` follows the board's turns as a second monitor and continues the agent session with a turn when the agent went idle (at most 3 times, for an hour). The agent side is `claude --plugin-dir <repo> -p "$(cat agent_brief.md)" --allowedTools "mcp__plugin_agent-hud_board__*,Monitor,Write,Read,Skill"` in the project directory; the user side is a subagent with `user_brief.md`.

The check of the monitor channel from this run, a nested session that gets a turn after the Monitor tool's cap, is `make check-live` at the root of the repository.

## What happened

| Round | User sent | Agent did | Time to answer |
|---|---|---|---|
| 1 | 3 reactions, 1 comment, 15 cell values, 1 note, 1 arrow, 1 card edit | answered the comment, filled a row, put 3 new steps, removed a risk | 40 s |
| 2 | 1 question, cell values on new rows, a reject | answered, moved values with their rows, renumbered the arrow | 30 s |
| 3 | approve, a chat message about a stale arrow and the hours | removed the arrow, corrected the total, said the checklist is agreed | 30 s |

The agent's Monitor expired at ten minutes, as the tool caps it; the expiry notice woke the agent, which re-armed it 30 seconds before the first turn came. The watchdog never had to step in.

## The two verdicts

User side, worst first:

1. F34: cell edits on a row the agent inserted are dropped from Send when they equal the old values of the row that had that number; the user's input is lost with no feedback.
2. F38 + F39: a click on an item's comment badge rejects the item, because the hover pill replaces the badges under the pointer; and the only way to open a thread is to set a verdict.
3. F18 + F41: a drag of the arrow dot at normal speed pans the board instead of drawing; a drawn arrow cannot be selected or deleted by the user.
4. F22 + F23: the pencil icon does nothing, so an edit needs the E key; a save drops the pending question and comment on the edited line with a 10 px footnote as the only warning.
5. F11 + F12 + F8: a popover opens on every cell click; three hidden reaction buttons sit in the Tab order per row; Escape closes neither popovers nor the pending list.

Agent side, worst first:

1. Monitor turns arrive truncated, so the user's message and most actions are cut off; every round needs a `read`, which cannot say what is new.
2. Each re-armed monitor delivers the same turn again under another task id, and the ten-minute cap forces the re-arming.
3. Unwritten conventions: the input-column syntax was not in any tool result, the part numbering (heading is part 1, header row is no part, cell refs are row/column) had to be inferred, and `write` returns an empty `parts` for a `fill`, so nothing confirms it.

Owner: the table in a card does not fill the card, and the cause is fixed pixel defaults where the content should be fluid (`owner_findings.md`).

## The issues filed from it

The findings are grouped into issues by the change that fixes them; each issue names its findings and embeds its screenshots.
