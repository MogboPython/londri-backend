# alembic init alembic
# alembic revision --autogenerate -m "your message"
# alembic upgrade head

# Define variables
PYTHON := python3
VENV := .venv
BIN := $(VENV)/bin
UV := $(shell command -v uv 2> /dev/null)

.PHONY: help install dev run lint format test clean docker-up docker-down db-init db-migrate db-upgrade db-downgrade

help:
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies using uv if available, or pip as fallback
ifdef UV
	@echo "Installing with uv..."
	uv venv $(VENV)
	uv pip install -r requirements.txt
else
	@echo "uv not found, installing with traditional pip..."
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
endif

dev:
	$(BIN)/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

run:
	$(BIN)/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test:
	PYTHONPATH=. $(BIN)/pytest -v --cov=app tests/

db-init:
	$(BIN)/alembic init alembic

db-migrate: ## Generate a new automatic migration script (Usage: make db-migrate m="migration message")
	@if [ -z "$(m)" ]; then echo "Error: Please provide a message. Example: make db-migrate m='add user table'"; exit 1; fi
	$(BIN)/alembic revision --autogenerate -m "$(m)"

db-upgrade:
	$(BIN)/alembic upgrade head

db-downgrade:
	$(BIN)/alembic downgrade -1

clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -exec rm -f {} +
	rm -rf .pytest_cache .coverage .ruff_cache

docker-up:
	docker-compose up -d --build

docker-down:
	docker-compose down -v
