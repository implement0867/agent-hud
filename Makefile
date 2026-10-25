.PHONY: check check-server check-ui check-live serve

check: check-server check-ui

check-server:
	cd server && uv run ruff format --check && uv run ruff check --ignore-noqa && uv run basedpyright && uv run pytest

check-ui:
	cd ui && npm run check

check-live:
	cd server && AGENT_HUD_LIVE=1 uv run pytest tests/test_live.py -s

serve:
	cd server && uv run uvicorn agent_hud.web:create_app --factory --port $${AGENT_HUD_PORT:-7676}
