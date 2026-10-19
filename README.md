# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas. The user approves, rejects or questions each item, and the agent reads that feedback
over MCP.

## Install

Requires [uv](https://docs.astral.sh/uv/) on `PATH`. In Claude Code:

```text
/plugin install agent-hud --marketplace implement0867/agent-hud
```

To try a local checkout: `claude --plugin-dir /path/to/agent-hud`.

## Tools

| Tool | Does |
|---|---|
| `write(ops)` | `put {id, md}` creates or replaces a card; `remove {id}` deletes one. All or nothing. |
| `read()` | every card with its markdown |

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
| `cd ui && npm run build` | build the UI |
