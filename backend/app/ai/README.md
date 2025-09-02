# AI Services Integration

This module provides a comprehensive AI service integration layer for the AI Knowledge Base application. It supports multiple AI service providers with automatic failover, health monitoring, and circuit breaker patterns.

## Features

- **Multiple AI Service Support**: OpenAI API, Ollama (local models)
- **Automatic Failover**: Seamless switching between services when one fails
- **Health Monitoring**: Continuous health checks with configurable intervals
- **Circuit Breaker Pattern**: Prevents cascading failures by temporarily disabling unhealthy services
- **Unified Interface**: Consistent API across different AI service providers
- **Streaming Support**: Real-time streaming responses for chat completions
- **RAG Integration**: Built-in support for Retrieval Augmented Generation

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Application   │───▶│  Service Manager │───▶│  AI Services    │
│     Layer       │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌──────────────┐         ┌─────────────┐
                       │ Health Check │         │   OpenAI    │
                       │   Monitor    │         │   Ollama    │
                       └──────────────┘         └─────────────┘
```

## Configuration

### Environment Variables

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1  # Optional
OPENAI_ORGANIZATION=your_org_id            # Optional
OPENAI_CHAT_MODEL=gpt-3.5-turbo           # Default model
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434     # Ollama server URL
OLLAMA_CHAT_MODEL=llama2                   # Default model
OLLAMA_EMBEDDING_MODEL=nomic-embed-text    # Default embedding model
OLLAMA_TIMEOUT=60                          # Request timeout

# Service Management
AI_HEALTH_CHECK_INTERVAL=300               # Health check interval (seconds)
AI_MAX_RETRY_ATTEMPTS=3                    # Max retry attempts
AI_CIRCUIT_BREAKER_THRESHOLD=5             # Failure threshold for circuit breaker
```

## Usage

### Basic Usage

```python
from app.ai.factory import AIServiceFactory
from app.ai.interfaces import ChatMessage
from app.config import get_settings

# Create service manager
settings = get_settings()
service_manager = AIServiceFactory.create_service_manager(settings)

# Start health monitoring
await service_manager.start_health_monitoring()

# Generate embedding
embedding = await service_manager.generate_embedding("Hello world")

# Generate chat response
messages = [ChatMessage(role="user", content="Hello!")]
response = await service_manager.generate_chat_response(messages)

# Stop health monitoring
await service_manager.stop_health_monitoring()
```

### Using Utility Functions

```python
from app.ai.utils import (
    embed_text_with_fallback,
    generate_chat_response_with_fallback,
    generate_rag_response
)

# Simple embedding
embedding = await embed_text_with_fallback("Text to embed")

# Simple chat
messages = [ChatMessage(role="user", content="Hello!")]
response = await generate_chat_response_with_fallback(messages)

# RAG response
context_docs = ["Document 1 content", "Document 2 content"]
rag_response = await generate_rag_response(
    user_question="What is AI?",
    context_documents=context_docs
)
```

### Streaming Responses

```python
# Streaming chat response
async for chunk in service_manager.generate_chat_response_stream(messages):
    print(chunk, end="", flush=True)
```

### Health Monitoring

```python
# Check service health
health_status = await service_manager.get_service_status()
for service_name, status in health_status.items():
    print(f"{service_name}: {status.status}")

# Get preferred service
preferred = service_manager.get_preferred_service()
print(f"Using: {preferred}")
```

## API Endpoints

The AI service provides REST API endpoints:

- `GET /api/v1/ai/status` - Get service health status
- `GET /api/v1/ai/models` - List available models
- `POST /api/v1/ai/embed` - Generate text embedding
- `POST /api/v1/ai/chat` - Generate chat response
- `POST /api/v1/ai/chat/stream` - Generate streaming chat response
- `POST /api/v1/ai/health-check` - Trigger manual health check

## Service Providers

### OpenAI

Supports:
- Chat completions (GPT models)
- Text embeddings
- Streaming responses
- Model listing

Requirements:
- Valid OpenAI API key
- Internet connection

### Ollama

Supports:
- Local model chat completions
- Local embeddings
- Streaming responses
- Model management (pull/delete)

Requirements:
- Ollama server running locally
- Models downloaded (e.g., `ollama pull llama2`)

## Error Handling

The service manager implements several error handling strategies:

1. **Retry Logic**: Automatic retries with exponential backoff
2. **Failover**: Automatic switching to backup services
3. **Circuit Breaker**: Temporary service disabling after repeated failures
4. **Graceful Degradation**: Fallback to available services

## Testing

Run the AI service tests:

```bash
cd backend
python -m pytest tests/test_ai_services.py -v
```

Run the demo script:

```bash
cd backend
python demo_ai_services.py
```

## Integration with Other Modules

### Document Processing

The AI services integrate with document processing for:
- Text embedding generation during document ingestion
- Vector storage in Qdrant

### Chat Module

The chat module uses AI services for:
- RAG-based question answering
- Conversation management
- Response generation

### Processing Pipeline

The processing pipeline uses AI services for:
- Document content vectorization
- Semantic search capabilities

## Performance Considerations

- **Connection Pooling**: HTTP clients use connection pooling
- **Async Operations**: All operations are asynchronous
- **Caching**: Consider implementing response caching for repeated queries
- **Rate Limiting**: Respect API rate limits for external services
- **Resource Management**: Proper cleanup of connections and resources

## Security

- **API Key Management**: Store API keys securely in environment variables
- **Input Validation**: All inputs are validated using Pydantic models
- **Error Sanitization**: Sensitive information is not exposed in error messages
- **Authentication**: API endpoints require user authentication

## Monitoring and Logging

- **Health Checks**: Continuous monitoring of service availability
- **Metrics**: Response times and success rates
- **Logging**: Comprehensive logging for debugging and monitoring
- **Alerts**: Circuit breaker events and service failures

## Troubleshooting

### Common Issues

1. **Service Unavailable**: Check if the service is running and accessible
2. **Authentication Errors**: Verify API keys and credentials
3. **Model Not Found**: Ensure the specified model is available
4. **Timeout Errors**: Increase timeout settings or check network connectivity
5. **Rate Limiting**: Implement backoff strategies for API rate limits

### Debug Mode

Enable debug logging to see detailed service interactions:

```python
import logging
logging.getLogger("app.ai").setLevel(logging.DEBUG)
```