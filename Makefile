.PHONY: check check-server check-ui build fixtures demo dev

check: check-server check-ui

check-server:
	cd server && uv run ruff format --check src tests && uv run ruff check src tests && uv run basedpyright && uv run pytest -q

check-ui:
	cd ui && npm run check

# Rebuild the canvas UI into server/src/agent_hud/static (committed).
build:
	cd ui && npm run build

# Regenerate protocol/fixtures/server.json after a model change.
fixtures:
	cd server && AGENT_HUD_UPDATE_FIXTURES=1 uv run pytest -q tests/test_contract.py

# Canvas with sample cards and the /debug API, no MCP.
demo:
	cd server && uv run agent-hud --mode serve --demo

# Vite dev server with hot reload, proxied to a demo canvas on :7676.
dev:
	cd server && uv run agent-hud --mode serve --demo --no-open-browser --extra-origins '["http://localhost:5173"]' & \
	cd ui && npm run dev
