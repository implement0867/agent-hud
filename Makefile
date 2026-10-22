.PHONY: check check-server check-ui serve demo

check: check-server check-ui

check-server:
	cd server && uv run ruff format --check && uv run ruff check --ignore-noqa && uv run basedpyright && uv run pytest

check-ui:
	cd ui && npm run check

serve:
	cd server && uv run uvicorn agent_hud.web:create_app --factory --port 7676

demo:
	cd ui && npm run build
	cd server && uv run python -m tests.demo ../docs/demo.gif
