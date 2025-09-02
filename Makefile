# AI Knowledge Base Makefile

# Default environment
ENV ?= development
COMPOSE_FILE ?= docker-compose.yml
ENV_FILE ?= .env

.PHONY: help dev-up dev-down prod-up prod-down backend-dev frontend-dev install-backend install-frontend clean
.PHONY: docker-build docker-up docker-down docker-logs docker-health backup restore deploy env-setup

help: ## Show this help message
	@echo 'AI Knowledge Base - Available Commands'
	@echo '======================================'
	@echo ''
	@echo 'Development:'
	@echo '  install-backend      Install backend dependencies'
	@echo '  install-frontend     Install frontend dependencies'
	@echo '  install              Install all dependencies'
	@echo '  dev-up               Start development environment (databases only)'
	@echo '  dev-down             Stop development environment'
	@echo '  backend-dev          Start backend in development mode'
	@echo '  frontend-dev         Start frontend in development mode'
	@echo '  test                 Run all tests'
	@echo ''
	@echo 'Docker Operations:'
	@echo '  docker-build         Build Docker images'
	@echo '  docker-up            Start all Docker services'
	@echo '  docker-down          Stop all Docker services'
	@echo '  docker-restart       Restart all Docker services'
	@echo '  docker-logs          Show Docker service logs'
	@echo '  docker-health        Check service health'
	@echo '  docker-clean         Clean Docker resources'
	@echo ''
	@echo 'Data Management:'
	@echo '  backup               Create system backup'
	@echo '  restore              Show restore options'
	@echo '  init-db              Initialize database'
	@echo '  migrate              Run database migrations'
	@echo '  migrate-create       Create new migration'
	@echo '  db-reset             Reset database (WARNING: deletes data)'
	@echo ''
	@echo 'Deployment:'
	@echo '  env-setup            Setup environment files'
	@echo '  deploy-dev           Deploy development environment'
	@echo '  deploy-prod          Deploy production environment'
	@echo '  deploy-services      Deploy only infrastructure services'
	@echo ''
	@echo 'Variables:'
	@echo '  ENV=development      Set environment (development|production)'
	@echo '  COMPOSE_FILE=...     Set Docker Compose file'
	@echo '  ENV_FILE=...         Set environment file'

# Development
install-backend: ## Install backend dependencies
	cd backend && pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

install: install-backend install-frontend ## Install all dependencies

dev-up: ## Start development environment (databases only)
	docker-compose -f docker-compose.dev.yml up -d

dev-down: ## Stop development environment
	docker-compose -f docker-compose.dev.yml down

backend-dev: ## Start backend in development mode
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev: ## Start frontend in development mode
	cd frontend && npm run dev

test: ## Run all tests
	cd backend && python -m pytest tests/ -v
	cd frontend && npm test -- --run

# Docker Operations
docker-build: ## Build Docker images
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) build

docker-up: ## Start all Docker services
	./scripts/deploy.sh --env $(ENV) --env-file $(ENV_FILE)

docker-down: ## Stop all Docker services
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down

docker-restart: ## Restart all Docker services
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) restart

docker-logs: ## Show Docker service logs
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

docker-health: ## Check service health
	./scripts/health-check.sh --env $(ENV)

docker-clean: ## Clean Docker resources
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v --remove-orphans
	docker system prune -f

# Data Management
backup: ## Create system backup
	./scripts/backup.sh --env $(ENV)

restore: ## Show restore options
	@echo "Available backups:"
	./scripts/backup.sh --list
	@echo "Use: ./scripts/backup.sh --restore <backup-file>"

init-db: ## Initialize database with migrations and test data
	cd backend && python scripts/init_db.py

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MESSAGE="description")
	cd backend && alembic revision --autogenerate -m "$(MESSAGE)"

migrate-downgrade: ## Downgrade database by one migration
	cd backend && alembic downgrade -1

db-reset: ## Reset database (WARNING: deletes all data)
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ]
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) stop postgres
	docker volume rm ai_kb_postgres_data || docker volume rm ai_kb_postgres_data_prod || true
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d postgres

# Deployment
env-setup: ## Setup environment files
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env"; fi
	@if [ ! -f .env.prod ]; then cp .env.prod.example .env.prod; echo "Created .env.prod"; fi
	@echo "Please edit the environment files with your configuration!"

deploy-dev: env-setup ## Deploy development environment
	$(MAKE) ENV=development COMPOSE_FILE=docker-compose.yml ENV_FILE=.env docker-up
	@echo "Development deployment completed!"
	@echo "Frontend: http://localhost:3000"
	@echo "Backend API: http://localhost:8000"

deploy-prod: ## Deploy production environment
	@if [ ! -f .env.prod ]; then echo "ERROR: .env.prod not found!"; exit 1; fi
	$(MAKE) ENV=production COMPOSE_FILE=docker-compose.prod.yml ENV_FILE=.env.prod docker-up
	@echo "Production deployment completed!"

deploy-services: ## Deploy only infrastructure services
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Infrastructure services deployed!"

# Legacy aliases for backward compatibility
prod-up: ## Start production environment (all services)
	docker-compose up -d

prod-down: ## Stop production environment
	docker-compose down

health-check: docker-health ## Run health check for all services

clean: docker-clean ## Clean up containers and volumes

# Quick commands
up: docker-up
down: docker-down
logs: docker-logs
health: docker-health
build: docker-build

status: ## Show service status
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

# Development helpers
shell-backend: ## Open backend container shell
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec backend bash

shell-postgres: ## Open PostgreSQL shell
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres psql -U postgres -d ai_knowledge_base

shell-redis: ## Open Redis CLI
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec redis redis-cli

# Monitoring
top: ## Show resource usage
	docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

update: ## Update Docker images
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) pull
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d