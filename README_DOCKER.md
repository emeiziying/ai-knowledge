# Docker Setup - AI Knowledge Base

This document provides a quick reference for Docker operations in the AI Knowledge Base project.

## Quick Start

### 1. Setup Environment
```bash
# Copy environment files
cp .env.example .env
cp .env.prod.example .env.prod

# Edit configuration
nano .env
```

### 2. Development Deployment
```bash
# Using deployment script (recommended)
./scripts/deploy.sh

# Using Makefile
make deploy-dev

# Using docker-compose directly
docker-compose up -d
```

### 3. Production Deployment
```bash
# Edit production environment
nano .env.prod

# Deploy production
./scripts/deploy.sh --env production --env-file .env.prod

# Using Makefile
make deploy-prod
```

## Available Scripts

| Script | Purpose |
|--------|---------|
| `./scripts/deploy.sh` | Main deployment script with options |
| `./scripts/backup.sh` | Backup and restore operations |
| `./scripts/health-check.sh` | Service health monitoring |

## Docker Compose Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Main development/production setup |
| `docker-compose.prod.yml` | Production-optimized configuration |
| `docker-compose.dev.yml` | Infrastructure services only |

## Service Ports

| Service | Development | Production |
|---------|-------------|------------|
| Frontend | 3000 | 80/443 |
| Backend API | 8000 | Internal |
| PostgreSQL | 5432 | Internal |
| Redis | 6379 | Internal |
| Qdrant | 6333 | Internal |
| MinIO | 9000/9001 | Internal |
| Ollama | 11434 | Internal |

## Common Commands

```bash
# Start services
make docker-up

# View logs
make docker-logs

# Check health
make docker-health

# Create backup
make backup

# Stop services
make docker-down

# Clean up
make docker-clean
```

## Environment Variables

Key variables to configure in `.env`:

```bash
# Required
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
MINIO_ROOT_PASSWORD=your_minio_password
SECRET_KEY=your_jwt_secret_key_32_chars_minimum

# AI Services (at least one)
OPENAI_API_KEY=your_openai_api_key
```

## Troubleshooting

### Port Conflicts
```bash
# Check port usage
sudo netstat -tulpn | grep :8000

# Change ports in .env
BACKEND_PORT=8001
FRONTEND_PORT=3001
```

### Service Health Issues
```bash
# Check service status
make status

# View specific service logs
docker-compose logs backend

# Restart services
make docker-restart
```

### Data Issues
```bash
# Reset database
make db-reset

# Restore from backup
./scripts/backup.sh --restore backups/postgres_20240101.sql.gz
```

## Production Considerations

1. **Security**: Change all default passwords
2. **SSL**: Configure HTTPS certificates
3. **Monitoring**: Set up health checks and alerts
4. **Backups**: Schedule regular backups
5. **Updates**: Keep images updated

For detailed information, see [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md).