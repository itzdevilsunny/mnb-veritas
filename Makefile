.PHONY: help env build up down logs ps migrate test smoke workflow clean-data all clean

SHELL := /bin/bash
COMPOSE := docker compose
BACKEND_SVC := backend
FRONTEND_SVC := frontend
DB_SVC := postgres

help:
	@echo "MNB Veritas Targets:"
	@echo "  make env      - Create .env from .env.example if missing"
	@echo "  make build    - Build Docker images for backend and frontend"
	@echo "  make up       - Start postgres (pgvector), redis, backend, and frontend"
	@echo "  make down     - Stop running containers"
	@echo "  make logs     - Tail backend and frontend logs"
	@echo "  make migrate  - Ensure pgvector/pg_trgm extensions and create tables"
	@echo "  make test     - Run backend pytest suite"
	@echo "  make smoke    - Run end-to-end API + /v1/verify smoke checks"
	@echo "  make all      - Build, start stack, run migrations, pytest, and smoke test"
	@echo "  make clean    - Stop containers and remove volumes"

env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example — add your LLM API keys before running live checks."; \
	else \
		echo ".env already exists."; \
	fi

build:
	$(COMPOSE) build --pull

up: env
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f $(BACKEND_SVC) $(FRONTEND_SVC)

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
	$(COMPOSE) exec -T $(BACKEND_SVC) pytest -v

smoke:
	python scripts/smoke_test.py

workflow:
	python scripts/test_full_workflow.py

clean-data:
	curl -s -X DELETE "http://127.0.0.1:8000/v1/sources/cleanup-test-data" -H "X-Veritas-Key: $${VERITAS_API_KEY:-veritas-local-dev-key-2026}"

all: build up migrate test smoke

clean:
	$(COMPOSE) down -v
