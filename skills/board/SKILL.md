---
name: board
description: Show plans, options, tables and questions to the user on the agent-hud board in the browser, and read the user's feedback. Use when a plan, a choice between options, or a table of values needs the user's review, or when the user asks for the board.
---

# Board

The board is a page in the browser that you and the user share. Its MCP tools are `write`, `read` and `listen`.

## Show content

Call `write` with a list of actions. They run in order, all or nothing.

- `put {id, md}` adds a card of markdown, or replaces the card with that id. A replaced card loses its feedback, values and arrows.
- `remove {id}` removes a card.
- `say {text}` sends a message to the user.
- `react {ref, reaction}`, `comment {ref, text}`, `fill {ref, value}` and `link {id, src, dst, text}` act on cards as the user does.

Put one subject on each card, with a short id such as `plan` or `risks`. Write each step or option as a list item or a table body row, so that the user can give feedback on it.

## Refs

A ref is a card id (`plan`), a part of a card (`plan/2`), or an input cell (`plan/2/3`). Parts are the list items and table body rows of the card, counted together from 1 in document order.

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

- `read` returns the board: the cards, the threads of reactions and comments by ref, the values by cell ref, and the arrows. Cards with the author `user` are notes from the user.
- `listen` returns the websocket URL of the user's actions. Open it with the Monitor tool to get each action when the user makes it, and open it again when the monitor ends.

After you show content for review, tell the user what to review, then wait for their actions. Read the board before you act on the feedback.
