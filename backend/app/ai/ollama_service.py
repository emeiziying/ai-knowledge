"""
Ollama local model service implementation.
"""
import time
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
import ollama

from .interfaces import (
    BaseAIService, AIServiceType, AIServiceStatus,
    EmbeddingRequest, EmbeddingResponse,
    ChatRequest, ChatResponse, ChatMessage,
    HealthCheckResponse
)


class OllamaService(BaseAIService):
    """Ollama local model service implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(AIServiceType.OLLAMA, config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.default_chat_model = config.get("default_chat_model", "llama2")
        self.default_embedding_model = config.get("default_embedding_model", "nomic-embed-text")
        self.timeout = config.get("timeout", 60)
        
        # Initialize Ollama client
        self.client = ollama.AsyncClient(host=self.base_url)
    
    async def generate_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate text embedding using Ollama."""
        try:
            model = request.model or self.default_embedding_model
            
            response = await self.client.embeddings(
                model=model,
                prompt=request.text
            )
            
            embedding = response['embedding']
            
            return EmbeddingResponse(
                embedding=embedding,
                model=model,
                usage=None  # Ollama doesn't provide usage stats
            )
            
        except Exception as e:
            self.set_health_status(False)
            raise Exception(f"Ollama embedding failed: {str(e)}")
    
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Generate chat completion using Ollama."""
        try:
            model = request.model or self.default_chat_model
            
            # Convert ChatMessage objects to dict format
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            
            response = await self.client.chat(
                model=model,
                messages=messages,
                stream=False,
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens
                } if request.max_tokens else {"temperature": request.temperature}
            )
            
            content = response['message']['content']
            
            return ChatResponse(
                content=content,
                model=model,
                usage=None,  # Ollama doesn't provide detailed usage stats
                finish_reason="stop"
            )
            
        except Exception as e:
            self.set_health_status(False)
            raise Exception(f"Ollama chat completion failed: {str(e)}")
    
    async def chat_completion_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Generate streaming chat completion using Ollama."""
        try:
            model = request.model or self.default_chat_model
            
            # Convert ChatMessage objects to dict format
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            
            stream = await self.client.chat(
                model=model,
                messages=messages,
                stream=True,
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens
                } if request.max_tokens else {"temperature": request.temperature}
            )
            
            async for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']
                    
        except Exception as e:
            self.set_health_status(False)
            raise Exception(f"Ollama streaming failed: {str(e)}")
    
    async def health_check(self) -> HealthCheckResponse:
        """Check Ollama service health."""
        start_time = time.time()
        
        try:
            # Test connection by listing models
            models = await self.client.list()
            
            response_time = (time.time() - start_time) * 1000
            self.set_health_status(True)
            
            available_models = [model['name'] for model in models.get('models', [])]
            
            return HealthCheckResponse(
                status=AIServiceStatus.HEALTHY,
                service_type=self.service_type,
                model_info={
                    "chat_model": self.default_chat_model,
                    "embedding_model": self.default_embedding_model,
                    "available_models": available_models
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.set_health_status(False)
            
            return HealthCheckResponse(
                status=AIServiceStatus.UNHEALTHY,
                service_type=self.service_type,
                error=str(e),
                response_time_ms=response_time
            )
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Ollama models."""
        try:
            response = await self.client.list()
            return response.get('models', [])
        except Exception as e:
            raise Exception(f"Failed to list Ollama models: {str(e)}")
    
    async def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama registry."""
        try:
            await self.client.pull(model_name)
            return True
        except Exception as e:
            raise Exception(f"Failed to pull model {model_name}: {str(e)}")
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama."""
        try:
            await self.client.delete(model_name)
            return True
        except Exception as e:
            raise Exception(f"Failed to delete model {model_name}: {str(e)}")


class OllamaEmbeddingService:
    """Dedicated Ollama embedding service."""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
    
    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        """Embed single text using Ollama."""
        request = EmbeddingRequest(text=text, model=model)
        response = await self.ollama_service.generate_embedding(request)
        return response.embedding
    
    async def embed_texts(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Embed multiple texts using Ollama."""
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text, model)
            embeddings.append(embedding)
        return embeddings


class OllamaChatService:
    """Dedicated Ollama chat service."""
    
    def __init__(self, ollama_service: OllamaService):
        self.ollama_service = ollama_service
    
    async def generate_response(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate chat response using Ollama."""
        request = ChatRequest(
            messages=messages,
            model=model,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens")
        )
        response = await self.ollama_service.chat_completion(request)
        return response.content
    
    async def generate_response_stream(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming chat response using Ollama."""
        request = ChatRequest(
            messages=messages,
            model=model,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
            stream=True
        )
        async for chunk in self.ollama_service.chat_completion_stream(request):
            yield chunk