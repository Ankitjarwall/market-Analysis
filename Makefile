.PHONY: help dev stop build test lint migrate seed logs clean

help:
	@echo "Market Intelligence Platform — Dev Commands"
	@echo ""
	@echo "  make dev        Start all services (Docker)"
	@echo "  make stop       Stop all services"
	@echo "  make build      Rebuild Docker images"
	@echo "  make test       Run all tests"
	@echo "  make migrate    Run Alembic migrations"
	@echo "  make seed       Seed initial admin user"
	@echo "  make logs       Tail all service logs"
	@echo "  make clean      Remove containers + volumes"

dev:
	docker compose up -d
	@echo "Services started. Dashboard: http://localhost:5173"

stop:
	docker compose stop

build:
	docker compose build --no-cache

test:
	cd backend && python -m pytest tests/ -v --cov=. --cov-report=term-missing

test-unit:
	cd backend && python -m pytest tests/unit/ -v

test-api:
	cd backend && python -m pytest tests/api/ -v

test-security:
	cd backend && python -m pytest tests/security/ -v

migrate:
	cd backend && alembic upgrade head

migrate-new:
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && python -c "from db.seed import seed_admin; import asyncio; asyncio.run(seed_admin())"

logs:
	docker compose logs -f

backend-shell:
	docker compose exec backend bash

db-shell:
	docker compose exec postgres psql -U market_user -d market_platform

redis-cli:
	docker compose exec redis redis-cli

clean:
	docker compose down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
