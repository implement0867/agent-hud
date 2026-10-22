---
name: board
description: Show plans, options, tables and questions to the user on the agent-hud board in the browser, and read the user's feedback. Use when a plan, a choice between options, or a table of values needs the user's review, or when the user asks for the board.
---

# Board

The board is a page in the browser that you and the user share. Its MCP tools are `write`, `read` and `listen`.

## Show content

Call `write` with a list of actions. They run in order, all or nothing.

- `put {id, md}` adds a card of markdown, or replaces the card with that id. A replaced card loses its arrows, and its feedback and values go to the card's history.
  - A fenced code block with a language name, such as ```` ```python ````, shows in colour. A block with an unknown language shows as plain text.
  - Put `file=` and `start=` after the language, such as ```` ```python file=src/app.py start=40 ````, to show the file name and the line numbers. Then the user's feedback on a code line names its file and line.
  - A ```` ```diff ```` block tints its added and removed lines.
- `remove {id}` removes a card.
- `say {text}` sends a message to the user. It shows in the chat on the page.
- `move {id, x, y}` places a card on the board, in pixels. A card with no place goes below the others.
- `react {ref, reaction}`, `comment {ref, text}`, `fill {ref, value}` and `link {id, src, dst, text}` act on cards as the user does. A comment also shows in the chat, with a link to its part.

Put one subject on each card, with a short id such as `plan` or `risks`. Write each step or option as a list item or a table body row, so that the user can give feedback on it.

## Refs

A ref is a card id (`plan`), a part of a card (`plan/2`), or an input cell (`plan/2/3`). Parts are the list items, table body rows and code lines of the card, counted together from 1 in document order. A ref such as `plan/2` in a message or comment shows as a link to that part.

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

- `read` returns the board: the cards, the threads of reactions and comments by ref, the values by cell ref, the arrows, the chat messages and comments, and the card positions. `read` with `history` true also returns the earlier versions of each card with their feedback. Cards with the author `user` are notes from the user, or cards that the user edited. Cards that the user placed near each other belong together for the user.
- `listen` returns the websocket URL of the user's turns. Open it with the Monitor tool, and open it again when the monitor ends. The user's reactions, comments, fills and edits collect until the user clicks Send or sends a chat message. Then the monitor gets one line with all of them, and each action has the text of the parts it names, as the user saw them.

Each turn has only the changes, as an edit of a file has only a diff. A `put` of the user on a card that was on the board comes as an `edit` with a unified diff of the card's markdown. Read the board once, then follow the turns, and read it again only when you are not sure what the board shows.

While your monitor is open, the page shows the user that an agent is connected. After you get a turn, the page shows that you work on it until you write an action.

After you show content for review, tell the user what to review and to click Send, then wait for their turn.
