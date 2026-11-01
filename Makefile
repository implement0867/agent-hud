.PHONY: check build-ui check-bundle check-server check-ui check-live serve

check: build-ui check-bundle check-server check-ui

# The server serves the UI from a bundle in its package, which the repository keeps: a check builds it, then fails
# until the build is staged, so that a commit cannot leave the bundle behind the sources.
build-ui:
	cd ui && npm run build

check-bundle:
	git diff --quiet -- server/src/agent_hud/static || { echo "the UI bundle is stale: git add server/src/agent_hud/static" >&2; exit 1; }
	test -z "$$(git ls-files --others --exclude-standard server/src/agent_hud/static)" || { echo "the UI bundle has new files: git add server/src/agent_hud/static" >&2; exit 1; }

check-server:
	cd server && uv run ruff format --check && uv run ruff check --ignore-noqa && uv run basedpyright && uv run pytest

check-ui:
	cd ui && npm run check

check-live:
	cd server && AGENT_HUD_LIVE=1 uv run pytest tests/test_live.py -s

serve:
	cd server && uv run uvicorn agent_hud.web:make_app --factory --port $${AGENT_HUD_PORT:-7676}
