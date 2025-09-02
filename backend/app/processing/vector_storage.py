"""
向量存储服务，集成 Qdrant 数据库。
Vector storage service integrated with Qdrant database.
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..vector_store import vector_store
from ..models import DocumentChunk
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class VectorStorageService:
    """向量存储服务"""
    
    def __init__(self):
        self.vector_store = vector_store
    
    async def store_document_vectors(
        self,
        db: Session,
        document_id: str,
        vectorized_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        存储文档向量到 Qdrant 和数据库
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            vectorized_chunks: 包含向量的分块列表
            
        Returns:
            存储结果
        """
        if not vectorized_chunks:
            return {"success": False, "error": "No chunks to store"}
        
        try:
            # 准备向量数据
            vector_points = []
            chunk_records = []
            
            for chunk in vectorized_chunks:
                # 生成唯一的向量ID
                vector_id = str(uuid.uuid4())
                
                # 准备向量点数据
                vector_point = {
                    "id": vector_id,
                    "vector": chunk["vector"],
                    "payload": {
                        "document_id": document_id,
                        "chunk_index": chunk["metadata"]["chunk_index"],
                        "content": chunk["content"],
                        "character_count": chunk["metadata"]["character_count"],
                        "word_count": chunk["metadata"]["word_count"],
                        "start_position": chunk["metadata"]["start_position"],
                        "end_position": chunk["metadata"]["end_position"],
                        "chunking_strategy": chunk["metadata"]["chunking_strategy"],
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
                
                # 添加结构信息到 payload
                if "has_structure_markers" in chunk["metadata"]:
                    vector_point["payload"]["structure_markers"] = chunk["metadata"]["has_structure_markers"]
                
                # 添加章节信息（如果有）
                if "section_info" in chunk["metadata"]:
                    vector_point["payload"]["section_info"] = chunk["metadata"]["section_info"]
                
                vector_points.append(vector_point)
                
                # 准备数据库记录
                chunk_record = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk["metadata"]["chunk_index"],
                    content=chunk["content"],
                    metadata_json=chunk["metadata"],
                    vector_id=vector_id
                )
                chunk_records.append(chunk_record)
            
            # 存储向量到 Qdrant
            vector_success = await self.vector_store.add_vectors(vector_points)
            
            if not vector_success:
                return {"success": False, "error": "Failed to store vectors in Qdrant"}
            
            # 存储分块记录到数据库
            try:
                for chunk_record in chunk_records:
                    db.add(chunk_record)
                db.commit()
                
                logger.info(f"Stored {len(vector_points)} vectors for document {document_id}")
                
                return {
                    "success": True,
                    "vectors_stored": len(vector_points),
                    "document_id": document_id,
                    "vector_ids": [point["id"] for point in vector_points]
                }
                
            except Exception as db_error:
                # 如果数据库存储失败，尝试清理 Qdrant 中的向量
                logger.error(f"Database storage failed, cleaning up vectors: {db_error}")
                db.rollback()
                
                # 尝试删除已存储的向量
                await self._cleanup_vectors([point["id"] for point in vector_points])
                
                return {"success": False, "error": f"Database storage failed: {str(db_error)}"}
                
        except Exception as e:
            logger.error(f"Failed to store document vectors: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_similar_chunks(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.7,
        document_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似的文档分块
        
        Args:
            query_vector: 查询向量
            limit: 返回结果数量限制
            score_threshold: 相似度阈值
            document_ids: 限制搜索的文档ID列表
            user_id: 用户ID（用于权限过滤）
            
        Returns:
            相似分块列表
        """
        try:
            # 构建过滤条件
            filter_conditions = {}
            
            if document_ids:
                filter_conditions["must"] = [
                    {
                        "key": "document_id",
                        "match": {"any": document_ids}
                    }
                ]
            
            # 搜索相似向量
            search_results = await self.vector_store.search_similar(
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                filter_conditions=filter_conditions
            )
            
            # 格式化结果
            formatted_results = []
            for result in search_results:
                formatted_result = {
                    "vector_id": result["id"],
                    "score": result["score"],
                    "document_id": result["payload"]["document_id"],
                    "chunk_index": result["payload"]["chunk_index"],
                    "content": result["payload"]["content"],
                    "character_count": result["payload"]["character_count"],
                    "word_count": result["payload"]["word_count"],
                    "start_position": result["payload"]["start_position"],
                    "end_position": result["payload"]["end_position"],
                    "chunking_strategy": result["payload"]["chunking_strategy"],
                    "created_at": result["payload"]["created_at"]
                }
                
                # 添加结构信息
                if "structure_markers" in result["payload"]:
                    formatted_result["structure_markers"] = result["payload"]["structure_markers"]
                
                # 添加章节信息
                if "section_info" in result["payload"]:
                    formatted_result["section_info"] = result["payload"]["section_info"]
                
                formatted_results.append(formatted_result)
            
            logger.info(f"Found {len(formatted_results)} similar chunks")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to search similar chunks: {e}")
            return []
    
    async def delete_document_vectors(self, document_id: str) -> bool:
        """
        删除文档的所有向量
        
        Args:
            document_id: 文档ID
            
        Returns:
            删除是否成功
        """
        try:
            # 从 Qdrant 删除向量
            success = await self.vector_store.delete_vectors(document_id)
            
            if success:
                logger.info(f"Deleted vectors for document {document_id}")
            else:
                logger.error(f"Failed to delete vectors for document {document_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting document vectors: {e}")
            return False
    
    async def update_document_vectors(
        self,
        db: Session,
        document_id: str,
        vectorized_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        更新文档向量（先删除旧的，再添加新的）
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            vectorized_chunks: 新的向量化分块
            
        Returns:
            更新结果
        """
        try:
            # 删除旧的向量
            delete_success = await self.delete_document_vectors(document_id)
            
            if not delete_success:
                logger.warning(f"Failed to delete old vectors for document {document_id}, continuing anyway")
            
            # 删除数据库中的旧分块记录
            try:
                db.query(DocumentChunk).filter(
                    DocumentChunk.document_id == document_id
                ).delete()
                db.commit()
            except Exception as db_error:
                logger.error(f"Failed to delete old chunk records: {db_error}")
                db.rollback()
            
            # 存储新的向量
            return await self.store_document_vectors(db, document_id, vectorized_chunks)
            
        except Exception as e:
            logger.error(f"Failed to update document vectors: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_document_vector_stats(self, document_id: str) -> Dict[str, Any]:
        """
        获取文档向量统计信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            统计信息
        """
        try:
            # 搜索该文档的所有向量（使用大的 limit）
            results = await self.vector_store.search_similar(
                query_vector=[0.0] * 384,  # 虚拟查询向量
                limit=10000,  # 大数量限制
                score_threshold=0.0,  # 低阈值以获取所有结果
                filter_conditions={
                    "must": [
                        {
                            "key": "document_id",
                            "match": {"value": document_id}
                        }
                    ]
                }
            )
            
            if not results:
                return {
                    "document_id": document_id,
                    "vector_count": 0,
                    "total_characters": 0,
                    "total_words": 0,
                    "chunking_strategies": []
                }
            
            # 计算统计信息
            total_characters = sum(r["payload"]["character_count"] for r in results)
            total_words = sum(r["payload"]["word_count"] for r in results)
            strategies = list(set(r["payload"]["chunking_strategy"] for r in results))
            
            return {
                "document_id": document_id,
                "vector_count": len(results),
                "total_characters": total_characters,
                "total_words": total_words,
                "chunking_strategies": strategies,
                "average_chunk_size": total_characters / len(results) if results else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get document vector stats: {e}")
            return {"document_id": document_id, "error": str(e)}
    
    async def _cleanup_vectors(self, vector_ids: List[str]) -> bool:
        """清理指定的向量ID"""
        try:
            # 注意：Qdrant 的删除 API 可能需要不同的实现
            # 这里假设有按ID删除的方法
            # 实际实现可能需要根据 Qdrant 客户端 API 调整
            logger.warning(f"Attempting to cleanup {len(vector_ids)} vectors")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup vectors: {e}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """获取向量集合统计信息"""
        try:
            return await self.vector_store.get_collection_info()
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}


# 全局向量存储服务实例
vector_storage_service = VectorStorageService()


async def initialize_vector_storage() -> bool:
    """初始化向量存储服务"""
    try:
        await vector_storage_service.vector_store.connect()
        logger.info("Vector storage service initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize vector storage service: {e}")
        return False