---
name: board
description: Show plans, options, tables and questions to the user on the agent-hud board in the browser, and read the user's feedback. Use when a plan, a choice between options, or a table of values needs the user's review, or when the user asks for the board.
---

# Board

The board is a page in the browser that you and the user share. Its MCP tools are `write`, `read` and `listen`. Each project directory has its own board, which the plugin names in each request, so another session in another project has another board; the shared board `shared` takes the requests of clients that name none.

## Show content

Call `write` with a list of actions. They run in order, all or nothing.

- `put {id, md, version?}` adds a card of markdown, or replaces the card with that id. The feedback, values and arrows on the parts whose text is unchanged stay with them, so fix one step without losing the user's reactions on the others. The feedback on the parts that changed goes to the card's history, and the arrows at them drop. A replaced card keeps its first author, and `edited` is true on it when the other author put the latest version. With `version`, the number of earlier versions the card has, the put is refused when the card changed since you read it.
  - A fenced code block with a language name, such as ```` ```python ````, shows in colour. A block with an unknown language shows as plain text.
  - Put `file=` and `start=` after the language, such as ```` ```python file=src/app.py start=40 ````, to show the file name and the line numbers. Then the user's feedback on a code line names its file and line.
  - A ```` ```diff ```` block tints its added and removed lines.
- `remove {id}` removes a card. `restore {id}` puts a removed card back as its last version was.
- `clear` starts over: every card goes to its history with its feedback, and the board, its arrows and the chat empty. Use it when the user moves to a new task, rather than a `remove` per card.
- `say {text}` sends a message to the user. It shows in the chat on the page.
- `move {id, x, y}` places a card on the board, in pixels. A card with no place goes to the free space below the others, on a grid of three columns 688 pixels apart, once the page shows it, and `read` has its place. A new card lands clear of every card; after that cards may cross, and the card last touched, by a `move` or a new version too, shows on top.
- `resize {id, width}` sets the width of a card, in pixels. A card that no one resized is as wide as its content needs, between 256 pixels and a column of the grid, 640.
- `react {ref, reaction}`, `comment {ref, text}`, `fill {ref, value}` and `link {id, src, dst, text}` act on cards as the user does. A comment also shows in the chat, with a link to its part.

`write` returns the cards it added and replaced, the parts whose feedback went to the history, the arrows it dropped, and the parts of each card it put, by number: `{"added": ["plan"], "replaced": [], "retired": [], "dropped": [], "parts": {"plan": {"1": "parse", "2": "render"}}}`. Take the numbers for refs from there, not from the markdown. Put each card at most once in a batch.

When an action does not fit the board or its kind, `write` applies none of the actions, and its error names the action by number and kind, and the valid choices: the cards on the board, the parts of the card, the input columns of the row, or the values the column takes. Fix that action and send the list again.

Put one subject on each card, with a short id such as `plan` or `risks`. Write each step or option as a list item or a table body row, so that the user can give feedback on it; a paragraph of prose takes feedback as a whole.

## Refs

A ref is a card id (`plan`), a part of a card (`plan/2`), or an input cell (`plan/2/3`). Parts are the headings, paragraphs, list items, table body rows and code lines of the card, counted together from 1 in document order. Nested list items and the code lines inside a list item count too, and a paragraph inside a list item is text of the item, so in `# Plan`, then `1. a` with sub-items `a1` and `a2`, then `2. b`, the item `b` is part 5. The cell ref counts the row as a part and the column by its place in the table, with the plain columns, so the input column `size` of a table after three list items and a row is `plan/4/2`. `write` and `read` return the text of each part by its number, so take the numbers from there. A ref such as `plan/2` in a message or comment shows as a link to that part.

## Ask for values

A table header with a spec makes an input column that the user fills:

| Spec | Value |
|---|---|
| `{text}` | text |
| `{check}` | true or false |
| `{number}` | a number |
| `{S, M, L}` | one of the options |

```markdown
| Task | Size {S, M, L} | Done {check} |
|---|---|---|
| parse | | |
| render | | |
```

Write the options and the text as the user reads them: an owner column names the user as they name themselves, or "you", not `user`, and a column of numbers names its unit in its title, such as `Hours {number}`, which the page shows as the cell's placeholder. The page names a part to the user by its text, not its ref, so the ref is for you.

## Read feedback

- `read` returns the board: the cards and the parts of each by number, the threads by ref, each with the reaction of each author and the comments, the values by cell ref, the arrows, the chat messages and comments, and the card positions and widths. `read` with `history` true also returns the earlier versions of each card with their feedback. `read` with `cards` returns those cards alone, with what is on them, and with `since` the messages after the message or comment with that id: use them to read less when the board is large. Cards with the author `user` are notes from the user; a card with `edited` true has its latest version from the other author, so the user edited your card or you edited the user's note. Cards that the user placed near each other belong together for the user.
- `listen` returns the websocket `url` of the user's turns on this session's board, a shell `command` that prints each turn as its lines, the `board` id and the `monitors` already open on the board, your own included. When `monitors` counts one you did not open, another session already follows this board and would get each turn too: tell the user so before you open a monitor, and open one only when they want this session to take the turns. Open the `url` with the Monitor tool's `ws` source, or, when your Monitor tool takes a command only, run the `command` with it. Set the description `board` and nothing more, and `timeout_ms` as long as the tool allows. Without a monitor, the user's sends wait, and the page tells the user to run `/agent-hud:open`. The user's reactions, comments, fills and edits collect until the user clicks Send or sends a chat message. Then the monitor gets one turn with all of them. A turn carries the net of the user's actions: the last reaction on a part and the last value of a cell, only when they differ from the start of the turn, and no moves or resizes; `read` has the positions and widths. The page lists what the next turn carries, in the user's words, and marks each change as unsent until Send, so the user sees what you get. A turn sent while no monitor was open waits for the next monitor, across restarts, and the page says so.

## Keep one monitor open

The Monitor tool caps `timeout_ms`, at ten minutes in some versions of Claude Code and thirty in others, whatever you ask; its result says when the monitor expires. The expiry notice is the cue to open the monitor again, at once and in the same way; so is a notice that the socket closed. Nothing is lost meanwhile: a turn the user sends while no monitor is open waits for the next one, but the user waits with it. Open one monitor at a time. Each open monitor on the board gets each turn, so a second one brings you the same turn twice, once under each task id: before you open another, stop a monitor that still runs with `TaskStop`, or wait for its expiry notice. When a turn comes with the id of one you already have, it is that turn again, and needs nothing.

While your monitor is open, the page shows the user that an agent is connected. After you get a turn, the page shows that you work on it until you write an action.

## Read a turn

A turn is one event of lines. The first is its head, `{"turn": "9f2c…", "actions": 3}`: the id of the send or chat message that ended the turn, and its number of actions. Then one line per action, in order, as JSON with the action's fields, such as `{"kind": "react", "ref": "plan/2", "reaction": "reject", "parts": {"plan/2": "rewrite the cache"}}`; `parts` has the text of each part that the line is the first in the turn to name, as the user saw it. A `put` of the user on a card that was on the board comes as an `edit` with a unified diff of the card's markdown; a `put` of a new card is a note of the user. Each turn has only the changes, as an edit of a file has only a diff. Read the board once, then follow the turns, and read it again only when you are not sure what the board shows.

The Monitor shows 3000 characters of an event and 500 of a line. A turn with more lines than one event holds comes as several events, half a second apart, each with a head that counts them, `{"turn": "9f2c…", "actions": 24, "frame": 2, "of": 3}`; the actions keep their order across them, so wait for the last frame before you act. A line longer than 500 characters, such as a long message or a long diff, shows cut at its end: `read` has the message whole in the chat and the card whole.

After you show content for review, tell the user what to review and to click Send, then wait for their turn.
