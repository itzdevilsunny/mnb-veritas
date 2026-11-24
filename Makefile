.PHONY: help env build up down logs ps migrate test test-local smoke workflow battery chain-verify clean-data all clean docker-build docker-up docker-down docker-logs

SHELL := /bin/bash
COMPOSE := docker compose
BACKEND_SVC := backend
FRONTEND_SVC := frontend
DB_SVC := postgres

help:
	@echo "MNB Veritas Operational Targets:"
	@echo "  make env          - Create .env from .env.example if missing"
	@echo "  make build        - Build Docker images for backend and frontend"
	@echo "  make up           - Start postgres (pgvector), redis, backend, and frontend"
	@echo "  make down         - Stop running containers"
	@echo "  make logs         - Tail backend and frontend logs"
	@echo "  make docker-build - Alias for make build"
	@echo "  make docker-up    - Alias for make up"
	@echo "  make docker-down  - Alias for make down"
	@echo "  make docker-logs  - Alias for make logs"
	@echo "  make migrate      - Ensure pgvector/pg_trgm extensions and create tables"
	@echo "  make test         - Run 82-test pytest suite inside docker container"
	@echo "  make test-local   - Run 82-test pytest suite locally (PYTHONPATH=backend)"
	@echo "  make smoke        - Run live smoke test battery (scripts/smoke_test.py)"
	@echo "  make workflow     - Run full 9-phase automated verification (scripts/test_full_workflow.py)"
	@echo "  make battery      - Run live multi-policy workbench battery (scripts/test_live_workbench_battery.py)"
	@echo "  make chain-verify - Check cryptographic SHA-256 audit chain integrity"
	@echo "  make clean-data   - Purge synthetic test sources and test audit logs"
	@echo "  make all          - Build, start stack, migrate, pytest, and smoke test"
	@echo "  make clean        - Stop containers and remove volumes"

env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example — add your provider API keys before running live checks."; \
	else \
		echo ".env already exists."; \
	fi

build:
	$(COMPOSE) build --pull

docker-build: build

up: env
	$(COMPOSE) up -d --wait

docker-up: up

down:
	$(COMPOSE) down

docker-down: down

logs:
	$(COMPOSE) logs -f $(BACKEND_SVC) $(FRONTEND_SVC)

docker-logs: logs

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec -T $(DB_SVC) psql -U $${POSTGRES_USER:-veritas_user} -d $${POSTGRES_DB:-mnb_veritas} \
		-c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
	$(COMPOSE) exec -T $(BACKEND_SVC) python -c "\
import asyncio; \
from app.core.database import engine; \
from app.models.db import Base; \
async def run(): \
    async with engine.begin() as conn: \
        await conn.run_sync(Base.metadata.create_all); \
asyncio.run(run()); \
print('Database tables synced cleanly.')"

test:
	$(COMPOSE) exec -T $(BACKEND_SVC) pytest backend/tests/ -v

test-local:
	PYTHONPATH=backend python -m pytest backend/tests/ -v

smoke:
	python scripts/smoke_test.py

workflow:
	python scripts/test_full_workflow.py

battery:
	python scripts/test_live_workbench_battery.py

chain-verify:
	curl -s "http://127.0.0.1:8000/v1/audits/verify-chain" -H "X-Veritas-Key: $${VERITAS_API_KEY:-veritas-local-dev-key-2026}"

clean-data:
	curl -s -X DELETE "http://127.0.0.1:8000/v1/sources/cleanup-test-data" -H "X-Veritas-Key: $${VERITAS_API_KEY:-veritas-local-dev-key-2026}"

all: build up migrate test smoke

clean:
	$(COMPOSE) down -v
