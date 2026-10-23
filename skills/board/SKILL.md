---
name: board
description: Show plans, options, tables and questions to the user on the agent-hud board in the browser, and read the user's feedback. Use when a plan, a choice between options, or a table of values needs the user's review, or when the user asks for the board.
---

# Board

The board is a page in the browser that you and the user share. Its MCP tools are `write`, `read` and `listen`.

## Show content

Call `write` with a list of actions. They run in order, all or nothing.

- `put {id, md}` adds a card of markdown, or replaces the card with that id. The feedback, values and arrows on the parts whose text is unchanged stay with them, so fix one step without losing the user's reactions on the others. The feedback on the parts that changed goes to the card's history, and the arrows at them drop.
  - A fenced code block with a language name, such as ```` ```python ````, shows in colour. A block with an unknown language shows as plain text.
  - Put `file=` and `start=` after the language, such as ```` ```python file=src/app.py start=40 ````, to show the file name and the line numbers. Then the user's feedback on a code line names its file and line.
  - A ```` ```diff ```` block tints its added and removed lines.
- `remove {id}` removes a card.
- `clear` starts over: every card goes to its history with its feedback, and the board, its arrows and the chat empty. Use it when the user moves to a new task, rather than a `remove` per card.
- `say {text}` sends a message to the user. It shows in the chat on the page.
- `move {id, x, y}` places a card on the board, in pixels. A card with no place goes below the others.
- `react {ref, reaction}`, `comment {ref, text}`, `fill {ref, value}` and `link {id, src, dst, text}` act on cards as the user does. A comment also shows in the chat, with a link to its part.

`write` returns the cards it added and replaced, the parts whose feedback went to the history, the arrows it dropped, and the parts of each card it put, by number: `{"added": ["plan"], "replaced": [], "retired": [], "dropped": [], "parts": {"plan": {"1": "parse", "2": "render"}}}`. Take the numbers for refs from there, not from the markdown. Put each card at most once in a batch.

When an action does not fit the board or its kind, `write` applies none of the actions, and its error names the action by number and kind, and the valid choices: the cards on the board, the parts of the card, the input columns of the row, or the values the column takes. Fix that action and send the list again.

Put one subject on each card, with a short id such as `plan` or `risks`. Write each step or option as a list item or a table body row, so that the user can give feedback on it.

## Refs

A ref is a card id (`plan`), a part of a card (`plan/2`), or an input cell (`plan/2/3`). Parts are the list items, table body rows and code lines of the card, counted together from 1 in document order. Nested list items and the code lines inside a list item count too, so in `1. a` with sub-items `a1` and `a2`, then `2. b`, the item `b` is part 4. The cell ref counts the row as a part and the column by its place in the table, with the plain columns, so the input column `size` of a table after three list items and a row is `plan/4/2`. `write` and `read` return the text of each part by its number, so take the numbers from there. A ref such as `plan/2` in a message or comment shows as a link to that part.

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

## Read feedback

- `read` returns the board: the cards and the parts of each by number, the threads by ref, each with the reaction of each author and the comments, the values by cell ref, the arrows, the chat messages and comments, and the card positions. `read` with `history` true also returns the earlier versions of each card with their feedback. `read` with `cards` returns those cards alone, with what is on them, and with `since` the messages after the message or comment with that id: use them to read less when the board is large. Cards with the author `user` are notes from the user, or cards that the user edited. Cards that the user placed near each other belong together for the user.
- `listen` returns the websocket URL of the user's turns. Open it with the Monitor tool, and open it again when the monitor ends. The user's reactions, comments, fills and edits collect until the user clicks Send or sends a chat message. Then the monitor gets one line with all of them, and each action has the text of the parts it names, as the user saw them.

Each turn has only the changes, as an edit of a file has only a diff. A `put` of the user on a card that was on the board comes as an `edit` with a unified diff of the card's markdown. Read the board once, then follow the turns, and read it again only when you are not sure what the board shows.

While your monitor is open, the page shows the user that an agent is connected. After you get a turn, the page shows that you work on it until you write an action.

After you show content for review, tell the user what to review and to click Send, then wait for their turn.
