# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas. The user approves, rejects or questions each item, and the agent reads that feedback
over MCP.

## Run

```sh
cd ui && npm install && npm run build && cd ..
uv run --project server agent-hud
```

The second command starts the MCP server on stdio and the board page at <http://127.0.0.1:7676>.
The page shows each card and updates when the agent writes. `AGENT_HUD_PORT` sets a different port.

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
| `cd ui && npm run build` | build the UI into `server/src/agent_hud/static` |
| `cd ui && npm run dev` | Vite on port 5173, with `/ws` sent to the running server |
