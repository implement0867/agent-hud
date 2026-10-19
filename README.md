# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas. The user approves, rejects or questions each item, and the agent reads that feedback
over MCP.

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
