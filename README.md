# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas. The user approves, rejects or questions each item, and the agent reads that feedback
over MCP.

## Run

```sh
cd ui && npm install && npm run build && cd ..
uv run --project server agent-hud
```

The second command starts the MCP server on stdio and serves the board page, which shows each card
and updates when the agent writes. `server/src/agent_hud/settings.py` sets the address.

## Tools

| Tool | Does |
|---|---|
| `write(ops)` | `put {id, md}` creates or replaces a card; `remove {id}` deletes one. All or nothing. |
| `read()` | the board as JSON: `{"cards": {"plan": {"md": "1. a"}}}` |

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
| `cd ui && npm run build` | build the UI into the server package |
| `cd ui && npm run dev` | Vite dev server, which sends `/ws` to the running server |
