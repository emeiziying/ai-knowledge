"""
Qdrant vector database integration for semantic search.
"""
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from .config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Qdrant vector database client wrapper."""
    
    def __init__(self):
        self.client = None
        self.collection_name = "document_chunks"
        self.vector_size = 1536  # Default for OpenAI embeddings, adjust based on model
        
    async def connect(self):
        """Initialize connection to Qdrant."""
        try:
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=30
            )
            
            # Test connection
            collections = self.client.get_collections()
            logger.info(f"Connected to Qdrant successfully. Collections: {len(collections.collections)}")
            
            # Create collection if it doesn't exist
            await self._ensure_collection_exists()
            
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise
    
    async def _ensure_collection_exists(self):
        """Create the document chunks collection if it doesn't exist."""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise
    
    async def add_vectors(self, vectors: List[Dict[str, Any]]) -> bool:
        """
        Add vectors to the collection.
        
        Args:
            vectors: List of dictionaries containing:
                - id: unique identifier
                - vector: embedding vector
                - payload: metadata (document_id, chunk_index, content, etc.)
        """
        try:
            points = []
            for vector_data in vectors:
                point = PointStruct(
                    id=vector_data["id"],
                    vector=vector_data["vector"],
                    payload=vector_data["payload"]
                )
                points.append(point)
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"Added {len(points)} vectors to collection")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add vectors: {e}")
            return False
    
    async def search_similar(
        self, 
        query_vector: List[float], 
        limit: int = 10,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Optional filter conditions
            
        Returns:
            List of similar documents with scores and metadata
        """
        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=models.Filter(**filter_conditions) if filter_conditions else None
            )
            
            results = []
            for scored_point in search_result:
                results.append({
                    "id": scored_point.id,
                    "score": scored_point.score,
                    "payload": scored_point.payload
                })
            
            logger.info(f"Found {len(results)} similar vectors")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search vectors: {e}")
            return []
    
    async def delete_vectors(self, document_id: str) -> bool:
        """
        Delete all vectors for a specific document.
        
        Args:
            document_id: Document ID to delete vectors for
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
            
            logger.info(f"Deleted vectors for document: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors for document {document_id}: {e}")
            return False
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": info.config.params.vectors.size,
                "vectors_count": info.vectors_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "points_count": info.points_count
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
    
    async def close(self):
        """Close the Qdrant client connection."""
        try:
            if self.client:
                self.client.close()
                logger.info("Qdrant connection closed")
        except Exception as e:
            logger.error(f"Error closing Qdrant connection: {e}")


# Global vector store instance
vector_store = VectorStore()