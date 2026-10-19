# agent-hud server

Python package behind the agent-hud Claude Code plugin: a FastMCP stdio server with two tools
(`write`, `read`) and a FastAPI app that serves the canvas UI and its websocket.

```bash
uv run agent-hud                       # MCP over stdio (what the plugin runs)
uv run agent-hud --mode serve --demo   # canvas only, sample cards, /debug API
uv run agent-hud --help                # every flag; each also reads AGENT_HUD_<NAME>
```

See the repository README for the protocol, the primitives and how to add one.
