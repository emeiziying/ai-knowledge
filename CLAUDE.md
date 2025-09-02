# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Frontend (React + TypeScript + Vite)
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Start development server (port 3000)
npm run build        # Build for production
npm run lint         # Run ESLint
npm test             # Run Jest tests
npm run test:watch   # Run tests in watch mode
npm run test:coverage # Run tests with coverage
```

### Backend (FastAPI + Python)
```bash
cd backend
pip install -r requirements.txt  # Install dependencies
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # Start dev server
python -m pytest tests/ -v       # Run tests
alembic upgrade head              # Run database migrations
alembic revision --autogenerate -m "description"  # Create new migration
```

### Docker Development
```bash
# Infrastructure services only (recommended for development)
make dev-up          # Start PostgreSQL, Redis, Qdrant, MinIO
make dev-down        # Stop infrastructure services

# Full Docker deployment
make docker-up       # Start all services with Docker
make docker-down     # Stop all services
make docker-logs     # View service logs

# Makefile provides comprehensive commands - run `make help` for full list
```

### Testing
```bash
# Backend tests
cd backend && python -m pytest tests/ -v

# Frontend tests  
cd frontend && npm test

# Run all tests via Makefile
make test
```

## Architecture Overview

### High-Level Structure
This is a full-stack AI-powered knowledge base application with RAG (Retrieval-Augmented Generation) capabilities:

- **Frontend**: React 18 + TypeScript + Vite + Ant Design + Zustand
- **Backend**: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- **AI Integration**: OpenAI/Ollama for LLM, Sentence Transformers for embeddings
- **Vector Storage**: Qdrant vector database
- **File Storage**: MinIO object storage
- **Cache**: Redis
- **Deployment**: Docker + Docker Compose

### Backend Architecture (`backend/app/`)

**Core Application Structure:**
- `main.py`: FastAPI app creation with middleware, routers, and exception handlers
- `config.py`: Centralized configuration using Pydantic settings
- `database.py`: SQLAlchemy database connection and session management
- `models.py`: SQLAlchemy ORM models for users, documents, conversations
- `startup.py`: Application lifecycle management and service initialization
- `vector_store.py`: Qdrant vector database integration
- `storage.py`: MinIO file storage operations

**Feature Modules:**
- `auth/`: JWT-based authentication with user management
- `documents/`: Document upload, processing, and management
- `processing/`: File parsing (PDF, Word, Markdown) and text chunking
- `ai/`: LLM integration (OpenAI/Ollama) with service health monitoring
- `chat/`: Conversation management and RAG query processing
- `middleware/`: CORS, security headers, logging, error handling

**Key Service Classes:**
- `AIService`: Abstract base for AI providers with health checks and circuit breakers
- `OpenAIService`/`OllamaService`: Concrete AI service implementations
- `VectorStore`: Qdrant operations for semantic search
- `StorageService`: MinIO file operations
- `DocumentProcessor`: File parsing and text extraction
- `ConversationManager`: Chat history and context management

### Frontend Architecture (`frontend/src/`)

**Core Structure:**
- `App.tsx`: Root component with routing and i18n configuration
- `main.tsx`: Application entry point with React 18 root
- `router/`: React Router configuration
- `stores/`: Zustand state management stores
- `services/`: API client services matching backend endpoints

**Components:**
- `components/Auth/`: Login, registration, authentication forms
- `components/Documents/`: Document upload, list, and management UI
- `components/Chat/`: Conversation interface with message history
- `components/Layout/`: Application shell and navigation
- `components/common/`: Reusable UI components

**State Management:**
- `stores/authStore`: User authentication state
- `stores/documentStore`: Document management state
- `stores/chatStore`: Conversation and message state

### Key Integration Patterns

**RAG Pipeline:**
1. Document upload → File storage (MinIO)
2. Text extraction → Processing service
3. Chunking → Semantic chunks with metadata
4. Vectorization → Sentence Transformers embeddings
5. Storage → Qdrant vector database
6. Query → Vector similarity search + LLM generation

**Authentication Flow:**
1. JWT tokens with refresh mechanism
2. Middleware-based route protection
3. Frontend auth guards and state management

**Error Handling:**
- Structured API errors with monitoring
- Circuit breaker pattern for AI services
- Comprehensive logging with request correlation

## Environment Setup

Copy environment files and customize:
```bash
cp .env.example .env
cp .env.prod.example .env.prod
```

Key environment variables:
- `DATABASE_URL`: PostgreSQL connection
- `REDIS_URL`: Redis connection  
- `QDRANT_HOST/PORT`: Vector database
- `MINIO_*`: Object storage credentials
- `OPENAI_API_KEY`: OpenAI API key (optional)
- `OLLAMA_BASE_URL`: Local Ollama endpoint (optional)

## Development Workflow

1. **Start infrastructure**: `make dev-up`
2. **Backend development**: `cd backend && uvicorn app.main:app --reload`
3. **Frontend development**: `cd frontend && npm run dev`
4. **Run tests**: `make test` or individually per service
5. **Database changes**: Use Alembic migrations in `backend/`

## Service Dependencies

**Required for development:**
- PostgreSQL (port 5432)
- Redis (port 6379)
- Qdrant (port 6333)
- MinIO (ports 9000/9001)

**Optional AI services:**
- OpenAI API (configured via env vars)
- Local Ollama (http://localhost:11434)

The application gracefully handles AI service unavailability and provides health monitoring endpoints.