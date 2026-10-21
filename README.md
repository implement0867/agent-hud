# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas. The user approves, rejects or questions each item, and the agent reads that feedback
over MCP.

## Run

```sh
cd ui && npm install && npm run build && cd ..
make serve
```

`make serve` starts the app and prints its URL. The app serves MCP at `/mcp/` and the board page at
`/`. The page shows each card and updates when the agent writes. To connect Claude Code:

```sh
claude mcp add --transport http agent-hud <URL>/mcp/
```

## Tools

| Tool | Does |
|---|---|
| `write(actions)` | acts on the board as the agent, all or nothing. Each action is `put {id, md}`, `remove {id}`, `react {ref, reaction}`, `unreact {ref}`, `comment {ref, text}`, `say {text}` or `fill {ref, value}`, with a `kind`. A `ref` is a card id, or a card id and the number of a list item or table body row, counted together in document order, such as `plan/2`. A table header such as `cost {number}`, `done {check}`, `note {text}` or `size {S, M, L}` makes an input column, and `fill` sets its cell by row and column, such as `plan/2/3`. |
| `read()` | the board as JSON: `{"cards": {"plan": {"md": "1. a", "author": "agent"}}, "threads": {"plan/1": {"reaction": "approve", "comments": [{"id": "9f2c…", "author": "user", "text": "why a?"}]}}, "values": {"plan/2/3": 3.5}}` |
| `listen()` | the websocket URL of the user's actions, in the same shape with an `id` and `author`; open it with Claude Code's Monitor tool |

## Layout

```text
server/   Python 3.12 package (uv, ruff, basedpyright)
ui/       React + Vite + strict TypeScript (ESLint strictTypeChecked, Prettier)
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node 22.

| Command | Does |
|---|---|
| `make check` | ruff format and lint, basedpyright; tsc, eslint, prettier |
| `make serve` | start the app |
| `cd ui && npm run build` | build the UI into the server package |
| `cd ui && npm run dev` | Vite dev server, which sends `/ws` to the running server |
