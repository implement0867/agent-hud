---
name: canvas
description: Put a plan, option set or trade-off table on the agent-hud canvas so the user can approve, reject, question and comment per item, then wait for their Send. Use when a reply would ask the user to approve several items, pick between options, or fill in values, or when the user asks for the canvas, HUD or whiteboard.
---

# agent-hud canvas

The canvas is a browser page shared with the user. Use it instead of a chat list when you need a verdict per item. Tools: `mcp__plugin_agent-hud_canvas__write` and `mcp__plugin_agent-hud_canvas__read`.

## Loop

1. `write` the cards in one call: `[{"op":"put","id":"plan","md":"## Plan\n1. ...\n2. ..."}]`.
2. Tell the user in one line what to review. The first write opens the browser.
3. `read` with `wait` (for example 600) blocks until the user presses Send. Each line is one part:
   `plan.3 approve`, `plan.2 question; "unclear"`, `plan.5 = "new text"` (user edit), `plan.7 added "..."`,
   `opts.r2.pick = yes`, `note n4 "..."`, `link l5 plan.6 -> plan.1 "entails?"`, `submit "message"`.
4. Act on it. Change only what the feedback touches: `set`, `insert`, `remove`, or `reply` to a comment.
   A re-`put` keeps feedback on items whose text did not change and marks edited ones `revised`.
5. Repeat until the parts you need are approved.

`read` without `wait` returns at once. If it reports `no Send within ...`, call it again or ask in chat.
`read` with `show: ["*"]` dumps every card with its feedback, for when you lost track.

## Card types

| Markdown in `md` | Card | User can |
|---|---|---|
| one list (`1.` or `-`) | list, item labels `plan.1`… | react, comment, edit, add, remove items |
| one table | table, labels `id.r2`, `id.r2.col`, `id.col` | react and comment on rows, cells, columns |
| table whose headers carry `{check}`, `{text}`, `{number}` or `{a,b,c}` | interactive table | fill those columns |
| anything else | markdown text | react, comment, rewrite |

A leading `# heading` becomes the card title. Column keys are the header text in lower snake case
(`Ops cost` → `ops_cost`). Force a kind with `"kind": "text"` to keep a list as prose.

## Token economy

- Keep ids short (`plan`, `opts`). Batch ops in one `write`.
- Prefer `set` on one item over re-putting a long card.
- Do not echo the card back in chat; the user sees it.
