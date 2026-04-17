.DEFAULT_GOAL := help

COMPOSE := docker compose
UV      := uv

.PHONY: help up down restart build dev logs shell test lint lint-fix setup-dev bootstrap nuke

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

backup: ## Trigger a manual backup now
	$(COMPOSE) exec backup /usr/local/bin/backup.sh --now

bootstrap: ## Interactive setup wizard (writes .env and optional override)
	@bash scripts/bootstrap.sh

nuke: ## DESTROY the database and all data (irreversible)
	@printf "\033[31m\033[1mWARNING: This will permanently delete all your data.\033[0m\n"
	@printf "\033[31mType YES to continue: \033[0m" && read ans && [ "$$ans" = "YES" ] || (echo "Aborted."; exit 1)
	@$(COMPOSE) down
	@HOST_DIR=$$(grep -s 'cadencia:/data' docker-compose.override.yml | awk -F: '{print $$1}' | xargs); \
	 if [ -n "$$HOST_DIR" ] && [ -f "$$HOST_DIR/em.db" ]; then \
	   rm -f "$$HOST_DIR/em.db" && printf "\033[31mDeleted $$HOST_DIR/em.db\033[0m\n"; \
	 else \
	   docker volume rm cadencia_data 2>/dev/null && printf "\033[31mDeleted Docker volume cadencia_data\033[0m\n" || printf "\033[33mNo database found to remove.\033[0m\n"; \
	 fi
	@$(COMPOSE) up -d

setup-dev: ## Install dev dependencies and git hooks (run once)
	$(UV) pip install -e "app/[dev]"
	@bash scripts/setup-dev.sh
