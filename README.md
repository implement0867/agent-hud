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
| `write(ops)` | `put {id, md}` creates or replaces a card, and a card of one numbered list gets its items; `remove {id}` deletes one. All or nothing. |
| `read()` | the board as JSON: `{"cards": {"plan": {"md": "1. a", "items": [{"md": "a"}], "reaction": "approve", "comments": [{"id": "9f2c…", "text": "why a?"}]}}}` |
| `listen()` | the websocket URL of the user's messages, reactions and comments; open it with Claude Code's Monitor tool |

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
