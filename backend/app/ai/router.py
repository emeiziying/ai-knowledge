"""
AI service management API endpoints.
"""
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth.dependencies import get_current_user
from ..models import User
from .interfaces import ChatMessage, HealthCheckResponse
from .service_manager import AIServiceManager
from .factory import AIServiceFactory
from ..config import get_settings

router = APIRouter(prefix="/ai", tags=["AI Services"])


# Request/Response models
class EmbeddingRequest(BaseModel):
    text: str
    model: Optional[str] = None


class EmbeddingResponse(BaseModel):
    embedding: List[float]
    model: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatResponse(BaseModel):
    content: str
    model: str


class ServiceStatusResponse(BaseModel):
    services: Dict[str, HealthCheckResponse]
    preferred_service: Optional[str]


class ModelsResponse(BaseModel):
    models: Dict[str, List[Dict[str, Any]]]


# Dependency to get AI service manager
async def get_ai_service_manager() -> AIServiceManager:
    """Get AI service manager instance."""
    settings = get_settings()
    return AIServiceFactory.create_service_manager(settings)


@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status(
    service_manager: AIServiceManager = Depends(get_ai_service_manager),
    current_user: User = Depends(get_current_user)
):
    """Get status of all AI services."""
    try:
        services_status = await service_manager.get_service_status()
        preferred_service = service_manager.get_preferred_service()
        
        return ServiceStatusResponse(
            services=services_status,
            preferred_service=preferred_service.value if preferred_service else None
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service status: {str(e)}"
        )


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    service_manager: AIServiceManager = Depends(get_ai_service_manager),
    current_user: User = Depends(get_current_user)
):
    """List available models from all AI services."""
    try:
        models = await service_manager.list_all_models()
        return ModelsResponse(models=models)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )


@router.post("/embed", response_model=EmbeddingResponse)
async def generate_embedding(
    request: EmbeddingRequest,
    service_manager: AIServiceManager = Depends(get_ai_service_manager),
    current_user: User = Depends(get_current_user)
):
    """Generate text embedding."""
    try:
        embedding = await service_manager.generate_embedding(
            text=request.text,
            model=request.model
        )
        
        # Get the preferred service for response
        preferred_service = service_manager.get_preferred_service()
        model_name = request.model or "default"
        
        return EmbeddingResponse(
            embedding=embedding,
            model=model_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embedding: {str(e)}"
        )


@router.post("/chat", response_model=ChatResponse)
async def generate_chat_response(
    request: ChatRequest,
    service_manager: AIServiceManager = Depends(get_ai_service_manager),
    current_user: User = Depends(get_current_user)
):
    """Generate chat response."""
    try:
        if request.stream:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use /ai/chat/stream endpoint for streaming responses"
            )
        
        response = await service_manager.generate_chat_response(
            messages=request.messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Get the preferred service for response
        preferred_service = service_manager.get_preferred_service()
        model_name = request.model or "default"
        
        return ChatResponse(
            content=response,
            model=model_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chat response: {str(e)}"
        )


@router.post("/chat/stream")
async def generate_chat_response_stream(
    request: ChatRequest,
    service_manager: AIServiceManager = Depends(get_ai_service_manager),
    current_user: User = Depends(get_current_user)
):
    """Generate streaming chat response."""
    from fastapi.responses import StreamingResponse
    import json
    
    async def generate():
        try:
            async for chunk in service_manager.generate_chat_response_stream(
                messages=request.messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_data = {"error": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/health-check")
async def trigger_health_check(
    service_manager: AIServiceManager = Depends(get_ai_service_manager),
    current_user: User = Depends(get_current_user)
):
    """Trigger manual health check for all services."""
    try:
        services_status = await service_manager.get_service_status()
        return {"message": "Health check completed", "services": services_status}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )