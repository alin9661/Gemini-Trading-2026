.PHONY: dev test lint format docker-up docker-down migrate clean

# Install dependencies
dev:
	uv sync --extra dev

# Run tests
test:
	uv run pytest -v

# Lint
lint:
	uv run ruff check .
	uv run mypy config core scripts tests

# Format
format:
	uv run ruff format .
	uv run ruff check --fix .

# Docker infrastructure
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-reset:
	docker compose down -v
	docker compose up -d

# Database
migrate:
	uv run python -m scripts.db_migrate

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist build *.egg-info
