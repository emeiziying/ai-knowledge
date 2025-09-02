"""
OpenAI API service implementation.
"""
import time
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
import openai
from openai import AsyncOpenAI

from .interfaces import (
    BaseAIService, AIServiceType, AIServiceStatus,
    EmbeddingRequest, EmbeddingResponse,
    ChatRequest, ChatResponse, ChatMessage,
    HealthCheckResponse
)


class OpenAIService(BaseAIService):
    """OpenAI API service implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(AIServiceType.OPENAI, config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url")
        self.organization = config.get("organization")
        self.default_chat_model = config.get("default_chat_model", "gpt-3.5-turbo")
        self.default_embedding_model = config.get("default_embedding_model", "text-embedding-ada-002")
        
        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            organization=self.organization
        )
    
    async def generate_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate text embedding using OpenAI API."""
        try:
            model = request.model or self.default_embedding_model
            
            response = await self.client.embeddings.create(
                input=request.text,
                model=model
            )
            
            embedding = response.data[0].embedding
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return EmbeddingResponse(
                embedding=embedding,
                model=model,
                usage=usage
            )
            
        except Exception as e:
            self.set_health_status(False)
            raise Exception(f"OpenAI embedding failed: {str(e)}")
    
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Generate chat completion using OpenAI API."""
        try:
            model = request.model or self.default_chat_model
            
            # Convert ChatMessage objects to dict format
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False
            )
            
            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return ChatResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=response.choices[0].finish_reason
            )
            
        except Exception as e:
            self.set_health_status(False)
            raise Exception(f"OpenAI chat completion failed: {str(e)}")
    
    async def chat_completion_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Generate streaming chat completion using OpenAI API."""
        try:
            model = request.model or self.default_chat_model
            
            # Convert ChatMessage objects to dict format
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            self.set_health_status(False)
            raise Exception(f"OpenAI streaming failed: {str(e)}")
    
    async def health_check(self) -> HealthCheckResponse:
        """Check OpenAI service health."""
        start_time = time.time()
        
        try:
            # Test with a simple embedding request
            response = await self.client.embeddings.create(
                input="health check",
                model=self.default_embedding_model
            )
            
            response_time = (time.time() - start_time) * 1000
            self.set_health_status(True)
            
            return HealthCheckResponse(
                status=AIServiceStatus.HEALTHY,
                service_type=self.service_type,
                model_info={
                    "chat_model": self.default_chat_model,
                    "embedding_model": self.default_embedding_model
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
        """List available OpenAI models."""
        try:
            models = await self.client.models.list()
            return [
                {
                    "id": model.id,
                    "object": model.object,
                    "created": model.created,
                    "owned_by": model.owned_by
                }
                for model in models.data
            ]
        except Exception as e:
            raise Exception(f"Failed to list OpenAI models: {str(e)}")


class OpenAIEmbeddingService:
    """Dedicated OpenAI embedding service."""
    
    def __init__(self, openai_service: OpenAIService):
        self.openai_service = openai_service
    
    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        """Embed single text using OpenAI."""
        request = EmbeddingRequest(text=text, model=model)
        response = await self.openai_service.generate_embedding(request)
        return response.embedding
    
    async def embed_texts(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Embed multiple texts using OpenAI."""
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text, model)
            embeddings.append(embedding)
        return embeddings


class OpenAIChatService:
    """Dedicated OpenAI chat service."""
    
    def __init__(self, openai_service: OpenAIService):
        self.openai_service = openai_service
    
    async def generate_response(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate chat response using OpenAI."""
        request = ChatRequest(
            messages=messages,
            model=model,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens")
        )
        response = await self.openai_service.chat_completion(request)
        return response.content
    
    async def generate_response_stream(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming chat response using OpenAI."""
        request = ChatRequest(
            messages=messages,
            model=model,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
            stream=True
        )
        async for chunk in self.openai_service.chat_completion_stream(request):
            yield chunk