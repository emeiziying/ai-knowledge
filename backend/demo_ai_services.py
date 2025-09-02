#!/usr/bin/env python3
"""
Demo script for AI services integration.
This script demonstrates how to use the AI service manager with different providers.
"""
import asyncio
import os
from typing import List

from app.ai.interfaces import ChatMessage
from app.ai.factory import AIServiceFactory
from app.ai.utils import (
    embed_text_with_fallback,
    generate_chat_response_with_fallback,
    generate_rag_response,
    check_ai_services_health
)
from app.config import Settings


async def demo_embedding_service():
    """Demo embedding functionality."""
    print("\n=== Embedding Service Demo ===")
    
    try:
        # Test embedding generation
        text = "This is a test document about artificial intelligence and machine learning."
        embedding = await embed_text_with_fallback(text)
        
        print(f"Text: {text}")
        print(f"Embedding dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
        
    except Exception as e:
        print(f"Embedding demo failed: {e}")


async def demo_chat_service():
    """Demo chat functionality."""
    print("\n=== Chat Service Demo ===")
    
    try:
        # Test simple chat
        messages = [
            ChatMessage(role="user", content="What is artificial intelligence?")
        ]
        
        response = await generate_chat_response_with_fallback(messages)
        print(f"User: What is artificial intelligence?")
        print(f"AI: {response}")
        
    except Exception as e:
        print(f"Chat demo failed: {e}")


async def demo_rag_functionality():
    """Demo RAG (Retrieval Augmented Generation) functionality."""
    print("\n=== RAG Service Demo ===")
    
    try:
        # Simulate retrieved documents
        context_documents = [
            "Artificial Intelligence (AI) is a branch of computer science that aims to create intelligent machines that can perform tasks that typically require human intelligence.",
            "Machine Learning is a subset of AI that enables computers to learn and improve from experience without being explicitly programmed.",
            "Deep Learning is a subset of machine learning that uses neural networks with multiple layers to model and understand complex patterns in data."
        ]
        
        user_question = "What is the relationship between AI, ML, and Deep Learning?"
        
        response = await generate_rag_response(
            user_question=user_question,
            context_documents=context_documents,
            temperature=0.7
        )
        
        print(f"Question: {user_question}")
        print(f"AI Response: {response}")
        
    except Exception as e:
        print(f"RAG demo failed: {e}")


async def demo_service_health():
    """Demo service health monitoring."""
    print("\n=== Service Health Demo ===")
    
    try:
        health_status = await check_ai_services_health()
        
        print("AI Services Health Status:")
        for service_name, status in health_status.items():
            if hasattr(status, 'status'):
                print(f"  {service_name}: {status.status}")
                if hasattr(status, 'error') and status.error:
                    print(f"    Error: {status.error}")
                if hasattr(status, 'response_time_ms') and status.response_time_ms:
                    print(f"    Response Time: {status.response_time_ms:.2f}ms")
            else:
                print(f"  {service_name}: {status}")
        
    except Exception as e:
        print(f"Health check demo failed: {e}")


async def demo_service_manager():
    """Demo direct service manager usage."""
    print("\n=== Service Manager Demo ===")
    
    try:
        # Create service manager
        settings = Settings()
        service_manager = AIServiceFactory.create_service_manager(settings)
        
        # Start health monitoring
        await service_manager.start_health_monitoring()
        
        # Get available services
        preferred_service = service_manager.get_preferred_service()
        print(f"Preferred service: {preferred_service}")
        
        # List models (if services are available)
        try:
            models = await service_manager.list_all_models()
            print("Available models:")
            for service_type, model_list in models.items():
                print(f"  {service_type}: {len(model_list)} models")
        except Exception as e:
            print(f"Could not list models: {e}")
        
        # Stop health monitoring
        await service_manager.stop_health_monitoring()
        
    except Exception as e:
        print(f"Service manager demo failed: {e}")


async def main():
    """Run all demos."""
    print("AI Services Integration Demo")
    print("=" * 40)
    
    # Check if any AI services are configured
    settings = Settings()
    has_openai = bool(settings.openai_api_key)
    has_ollama = bool(settings.ollama_base_url)
    
    print(f"OpenAI configured: {has_openai}")
    print(f"Ollama configured: {has_ollama}")
    
    if not (has_openai or has_ollama):
        print("\nNo AI services configured. Please set:")
        print("- OPENAI_API_KEY environment variable for OpenAI")
        print("- OLLAMA_BASE_URL environment variable for Ollama")
        print("\nRunning limited demos...")
    
    # Run demos
    await demo_service_health()
    await demo_service_manager()
    
    if has_openai or has_ollama:
        await demo_embedding_service()
        await demo_chat_service()
        await demo_rag_functionality()
    else:
        print("\nSkipping embedding, chat, and RAG demos (no services configured)")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    # Set up basic configuration for demo
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
    
    asyncio.run(main())