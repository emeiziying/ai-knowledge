#!/usr/bin/env python3
"""
Demo script for document vectorization functionality.
This script demonstrates the complete vectorization pipeline without requiring database setup.
"""
import asyncio
import logging
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our modules
from app.processing.chunking import create_semantic_chunks, ChunkingConfig, ChunkingStrategy
from app.processing.embeddings import (
    EmbeddingConfig, 
    EmbeddingProvider, 
    SentenceTransformersEmbedding,
    DocumentVectorizer
)


async def demo_chunking():
    """Demonstrate document chunking functionality."""
    print("\n" + "="*60)
    print("DOCUMENT CHUNKING DEMONSTRATION")
    print("="*60)
    
    # Sample document content
    sample_content = """# AI Knowledge Base System

## Introduction
This document describes the AI Knowledge Base system, which provides intelligent document management and query capabilities using RAG (Retrieval Augmented Generation) architecture.

## Architecture Overview
The system consists of several key components:

### Backend Services
- FastAPI web server for REST API endpoints
- PostgreSQL database for structured data storage
- Qdrant vector database for semantic search
- MinIO object storage for file management
- Redis for caching and task queues

### Document Processing Pipeline
The document processing pipeline handles multiple file formats including PDF, Word documents, text files, and Markdown. Each document goes through several stages:

1. **File Upload and Validation**: Documents are uploaded and validated for format and size
2. **Content Extraction**: Text content is extracted using format-specific parsers
3. **Text Preprocessing**: Content is cleaned and normalized
4. **Semantic Chunking**: Documents are split into meaningful chunks while preserving context
5. **Vectorization**: Text chunks are converted to embeddings using transformer models
6. **Storage**: Vectors are stored in Qdrant for efficient similarity search

### AI Integration
The system integrates with various AI services for text generation and embedding:
- OpenAI GPT models for text generation
- Sentence Transformers for local embeddings
- Support for local models via Ollama

## Conclusion
This architecture provides a scalable and flexible foundation for building intelligent knowledge management systems."""

    print(f"Original document length: {len(sample_content)} characters")
    print(f"Word count: {len(sample_content.split())} words")
    
    # Test different chunking strategies
    strategies = [
        (ChunkingStrategy.FIXED_SIZE, "Fixed Size Chunking"),
        (ChunkingStrategy.SEMANTIC, "Semantic Chunking"),
        (ChunkingStrategy.HYBRID, "Hybrid Chunking")
    ]
    
    for strategy, name in strategies:
        print(f"\n--- {name} ---")
        
        config = ChunkingConfig(
            strategy=strategy,
            chunk_size=400,
            chunk_overlap=50,
            min_chunk_size=50,
            max_chunk_size=800
        )
        
        chunks = create_semantic_chunks(sample_content, config=config)
        
        print(f"Number of chunks created: {len(chunks)}")
        
        for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
            metadata = chunk["metadata"]
            print(f"\nChunk {i+1}:")
            print(f"  Size: {metadata['character_count']} chars, {metadata['word_count']} words")
            print(f"  Content preview: {chunk['content'][:100]}...")
        
        if len(chunks) > 3:
            print(f"\n  ... and {len(chunks) - 3} more chunks")


async def demo_embeddings():
    """Demonstrate embedding functionality."""
    print("\n" + "="*60)
    print("EMBEDDING DEMONSTRATION")
    print("="*60)
    
    # Sample chunks for embedding
    sample_chunks = [
        {
            "content": "The AI Knowledge Base system provides intelligent document management capabilities.",
            "metadata": {"chunk_index": 0, "character_count": 85, "word_count": 11}
        },
        {
            "content": "FastAPI serves as the web framework for building REST API endpoints with high performance.",
            "metadata": {"chunk_index": 1, "character_count": 89, "word_count": 14}
        },
        {
            "content": "Qdrant vector database enables efficient similarity search for semantic document retrieval.",
            "metadata": {"chunk_index": 2, "character_count": 88, "word_count": 12}
        }
    ]
    
    print(f"Sample chunks to vectorize: {len(sample_chunks)}")
    
    try:
        # Initialize embedding service
        config = EmbeddingConfig(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
            model_name="all-MiniLM-L6-v2",  # Lightweight model
            batch_size=8,
            normalize_embeddings=True
        )
        
        print(f"Initializing embedding service with model: {config.model_name}")
        
        embedding_service = SentenceTransformersEmbedding(config)
        
        # Initialize the service
        success = await embedding_service.initialize()
        
        if not success:
            print("❌ Failed to initialize embedding service")
            return
        
        print("✅ Embedding service initialized successfully")
        print(f"Embedding dimension: {embedding_service.get_embedding_dimension()}")
        
        # Create vectorizer
        vectorizer = DocumentVectorizer(embedding_service)
        
        # Vectorize chunks
        print("\nVectorizing chunks...")
        vectorized_chunks = await vectorizer.vectorize_chunks(sample_chunks)
        
        print(f"✅ Successfully vectorized {len(vectorized_chunks)} chunks")
        
        # Show results
        for i, chunk in enumerate(vectorized_chunks):
            vector = chunk["vector"]
            print(f"\nChunk {i+1}:")
            print(f"  Content: {chunk['content'][:60]}...")
            print(f"  Vector dimension: {len(vector)}")
            print(f"  Vector sample: [{vector[0]:.4f}, {vector[1]:.4f}, {vector[2]:.4f}, ...]")
        
        # Demonstrate similarity calculation
        print("\n--- Similarity Demonstration ---")
        
        # Calculate similarity between first two chunks
        import numpy as np
        
        vec1 = np.array(vectorized_chunks[0]["vector"])
        vec2 = np.array(vectorized_chunks[1]["vector"])
        vec3 = np.array(vectorized_chunks[2]["vector"])
        
        # Cosine similarity
        similarity_1_2 = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        similarity_1_3 = np.dot(vec1, vec3) / (np.linalg.norm(vec1) * np.linalg.norm(vec3))
        similarity_2_3 = np.dot(vec2, vec3) / (np.linalg.norm(vec2) * np.linalg.norm(vec3))
        
        print(f"Similarity between chunk 1 and 2: {similarity_1_2:.4f}")
        print(f"Similarity between chunk 1 and 3: {similarity_1_3:.4f}")
        print(f"Similarity between chunk 2 and 3: {similarity_2_3:.4f}")
        
        # Test query vectorization
        print("\n--- Query Vectorization ---")
        
        test_queries = [
            "How does the document management system work?",
            "What database is used for vector storage?",
            "Tell me about the API framework"
        ]
        
        for query in test_queries:
            query_vector = await vectorizer.vectorize_query(query)
            print(f"\nQuery: {query}")
            print(f"Query vector dimension: {len(query_vector)}")
            
            # Find most similar chunk
            best_similarity = -1
            best_chunk_idx = -1
            
            query_vec = np.array(query_vector)
            
            for i, chunk in enumerate(vectorized_chunks):
                chunk_vec = np.array(chunk["vector"])
                similarity = np.dot(query_vec, chunk_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec))
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_chunk_idx = i
            
            print(f"Most similar chunk: {best_chunk_idx + 1} (similarity: {best_similarity:.4f})")
            print(f"Content: {vectorized_chunks[best_chunk_idx]['content'][:80]}...")
        
    except Exception as e:
        print(f"❌ Error in embedding demonstration: {e}")
        logger.exception("Embedding demo failed")


async def demo_complete_pipeline():
    """Demonstrate the complete vectorization pipeline."""
    print("\n" + "="*60)
    print("COMPLETE PIPELINE DEMONSTRATION")
    print("="*60)
    
    # Sample document
    document_content = """# Machine Learning in Healthcare

## Overview
Machine learning is revolutionizing healthcare by enabling more accurate diagnoses, personalized treatments, and efficient drug discovery processes.

## Applications

### Medical Imaging
AI algorithms can analyze medical images such as X-rays, MRIs, and CT scans to detect abnormalities with high accuracy. Deep learning models have shown remarkable performance in identifying cancerous tissues, fractures, and other medical conditions.

### Drug Discovery
Machine learning accelerates drug discovery by predicting molecular behavior, identifying potential drug targets, and optimizing compound structures. This reduces the time and cost associated with traditional drug development processes.

### Personalized Medicine
By analyzing patient data including genetic information, medical history, and lifestyle factors, ML models can recommend personalized treatment plans that are more effective for individual patients.

## Challenges
Despite the promising applications, there are several challenges including data privacy concerns, regulatory compliance, and the need for interpretable AI models in critical healthcare decisions.

## Future Directions
The future of ML in healthcare includes federated learning for privacy-preserving collaboration, explainable AI for transparent decision-making, and integration with IoT devices for continuous health monitoring."""
    
    try:
        print("Step 1: Document Chunking")
        print("-" * 30)
        
        # Create chunks
        chunks = create_semantic_chunks(
            document_content,
            config=ChunkingConfig(
                strategy=ChunkingStrategy.HYBRID,
                chunk_size=300,
                chunk_overlap=50
            )
        )
        
        print(f"✅ Created {len(chunks)} chunks")
        
        print("\nStep 2: Initialize Embedding Service")
        print("-" * 30)
        
        # Initialize embedding service
        config = EmbeddingConfig(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
            model_name="all-MiniLM-L6-v2"
        )
        
        embedding_service = SentenceTransformersEmbedding(config)
        success = await embedding_service.initialize()
        
        if not success:
            print("❌ Failed to initialize embedding service")
            return
        
        print("✅ Embedding service initialized")
        
        print("\nStep 3: Vectorize Chunks")
        print("-" * 30)
        
        vectorizer = DocumentVectorizer(embedding_service)
        vectorized_chunks = await vectorizer.vectorize_chunks(chunks)
        
        print(f"✅ Vectorized {len(vectorized_chunks)} chunks")
        
        print("\nStep 4: Simulate Vector Storage")
        print("-" * 30)
        
        # Simulate storing vectors (without actual Qdrant)
        vector_storage_data = []
        
        for i, chunk in enumerate(vectorized_chunks):
            vector_point = {
                "id": f"chunk_{i}",
                "vector": chunk["vector"],
                "payload": {
                    "content": chunk["content"],
                    "metadata": chunk["metadata"]
                }
            }
            vector_storage_data.append(vector_point)
        
        print(f"✅ Prepared {len(vector_storage_data)} vector points for storage")
        
        print("\nStep 5: Query Simulation")
        print("-" * 30)
        
        # Simulate queries
        test_queries = [
            "What are the applications of machine learning in medical imaging?",
            "How does ML help with drug discovery?",
            "What challenges exist in healthcare AI?"
        ]
        
        import numpy as np
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            
            # Vectorize query
            query_vector = await vectorizer.vectorize_query(query)
            
            # Find most similar chunks
            similarities = []
            query_vec = np.array(query_vector)
            
            for point in vector_storage_data:
                chunk_vec = np.array(point["vector"])
                similarity = np.dot(query_vec, chunk_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec)
                )
                similarities.append((similarity, point))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[0], reverse=True)
            
            # Show top 2 results
            print("Top results:")
            for i, (score, point) in enumerate(similarities[:2]):
                print(f"  {i+1}. Score: {score:.4f}")
                print(f"     Content: {point['payload']['content'][:80]}...")
        
        print(f"\n✅ Complete pipeline demonstration finished successfully!")
        
    except Exception as e:
        print(f"❌ Error in complete pipeline: {e}")
        logger.exception("Complete pipeline demo failed")


async def main():
    """Run all demonstrations."""
    print("AI Knowledge Base - Document Vectorization Demo")
    print("=" * 60)
    
    try:
        await demo_chunking()
        await demo_embeddings()
        await demo_complete_pipeline()
        
        print("\n" + "="*60)
        print("🎉 ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.exception("Demo failed")


if __name__ == "__main__":
    asyncio.run(main())