.DEFAULT_GOAL := help

COMPOSE := docker compose
UV      := uv

.PHONY: help up down restart build dev logs shell test lint lint-fix setup-dev

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# --- Stack ---

up: ## Start the stack (detached)
	$(COMPOSE) up -d

down: ## Stop the stack
	$(COMPOSE) down

restart: ## Restart all containers
	$(COMPOSE) restart

build: ## Rebuild all images (no cache)
	$(COMPOSE) build --no-cache

dev: ## Start with hot reload (dev overlay)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up

logs: ## Follow container logs
	$(COMPOSE) logs -f

shell: ## Open a shell in the app container
	$(COMPOSE) exec app bash

# --- Quality ---

test: ## Run the test suite inside the app container
	$(COMPOSE) exec app python -m pytest /app/tests/ -v

lint: ## Run ruff linter
	ruff check app/src/

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix --unsafe-fixes app/src/

# --- Setup ---

setup-dev: ## Install dev dependencies and git hooks (run once)
	$(UV) pip install -e "app/[dev]"
	@bash scripts/setup-dev.sh
