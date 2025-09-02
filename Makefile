.PHONY: help dev-up dev-down prod-up prod-down backend-dev frontend-dev install-backend install-frontend clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dev-up: ## Start development environment (databases only)
	docker-compose -f docker-compose.dev.yml up -d

dev-down: ## Stop development environment
	docker-compose -f docker-compose.dev.yml down

prod-up: ## Start production environment (all services)
	docker-compose up -d

prod-down: ## Stop production environment
	docker-compose down

backend-dev: ## Start backend in development mode
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev: ## Start frontend in development mode
	cd frontend && npm run dev

install-backend: ## Install backend dependencies
	cd backend && pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

init-db: ## Initialize database with migrations and test data
	cd backend && python scripts/init_db.py

health-check: ## Run health check for all services
	cd backend && python scripts/health_check.py

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MESSAGE="description")
	cd backend && alembic revision --autogenerate -m "$(MESSAGE)"

migrate-downgrade: ## Downgrade database by one migration
	cd backend && alembic downgrade -1

clean: ## Clean up containers and volumes
	docker-compose down -v
	docker-compose -f docker-compose.dev.yml down -v
	docker system prune -f