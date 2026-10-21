#!/bin/sh
# Start the board server unless one already answers on its port.
curl -sf -o /dev/null http://127.0.0.1:7676/ && exit 0
cd "${CLAUDE_PLUGIN_ROOT}/server" || exit 1
nohup uv run --quiet uvicorn agent_hud.web:create_app --factory --port 7676 >/dev/null 2>&1 &
