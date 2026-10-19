.PHONY: check check-server check-ui

check: check-server check-ui

check-server:
	cd server && uv run ruff format --check && uv run ruff check --ignore-noqa && uv run basedpyright

check-ui:
	cd ui && npm run check
