"""
异步任务队列处理文档向量化。
Async task queue for document vectorization processing.
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID
from celery import Celery
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Document
from .processor import DocumentProcessor, ProcessingStatus
from .chunking import create_semantic_chunks, ChunkingConfig, ChunkingStrategy
from .embeddings import get_default_vectorizer, initialize_default_embedding_service
from .vector_storage import vector_storage_service, initialize_vector_storage
from ..storage import storage
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# 创建 Celery 应用
celery_app = Celery(
    "document_processing",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/0"
)

# Celery 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 分钟超时
    task_soft_time_limit=25 * 60,  # 25 分钟软超时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


class DocumentVectorizationTask:
    """文档向量化任务处理器"""
    
    def __init__(self):
        self.processor = DocumentProcessor()
        self.vectorizer = None
        self.initialized = False
    
    async def initialize(self):
        """初始化任务处理器"""
        if self.initialized:
            return True
        
        try:
            # 初始化嵌入服务
            embedding_success = await initialize_default_embedding_service()
            if not embedding_success:
                logger.error("Failed to initialize embedding service")
                return False
            
            # 初始化向量存储
            vector_storage_success = await initialize_vector_storage()
            if not vector_storage_success:
                logger.error("Failed to initialize vector storage")
                return False
            
            # 获取向量化器
            self.vectorizer = get_default_vectorizer()
            if not self.vectorizer:
                logger.error("Failed to get vectorizer")
                return False
            
            self.initialized = True
            logger.info("Document vectorization task processor initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize task processor: {e}")
            return False
    
    async def process_document_vectorization(
        self,
        document_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理文档向量化的完整流程
        
        Args:
            document_id: 文档ID
            user_id: 用户ID
            
        Returns:
            处理结果
        """
        result = {
            "document_id": document_id,
            "user_id": user_id,
            "status": "started",
            "steps_completed": [],
            "error": None,
            "stats": {}
        }
        
        db = None
        try:
            # 初始化（如果需要）
            if not self.initialized:
                init_success = await self.initialize()
                if not init_success:
                    result["status"] = "failed"
                    result["error"] = "Failed to initialize task processor"
                    return result
            
            # 获取数据库会话
            db = next(get_db())
            
            # 获取文档记录
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                result["status"] = "failed"
                result["error"] = f"Document {document_id} not found"
                return result
            
            # 更新文档状态
            document.status = ProcessingStatus.PROCESSING.value
            db.commit()
            
            # 步骤1: 下载文件内容
            logger.info(f"Step 1: Downloading file content for document {document_id}")
            file_content = await storage.download_file(document.file_path)
            if not file_content:
                raise Exception("Failed to download file content")
            
            result["steps_completed"].append("file_download")
            
            # 步骤2: 文档解析和预处理
            logger.info(f"Step 2: Processing document {document_id}")
            self.processor.db_session = db
            
            processing_result = self.processor.process_document(
                document_id=document_id,
                file_content=file_content,
                filename=document.original_name,
                mime_type=document.mime_type
            )
            
            if processing_result["status"] != ProcessingStatus.COMPLETED.value:
                raise Exception(f"Document processing failed: {processing_result.get('error', 'Unknown error')}")
            
            result["steps_completed"].append("document_processing")
            result["stats"]["processing"] = processing_result.get("processing_stats", {})
            
            # 步骤3: 智能分块
            logger.info(f"Step 3: Creating semantic chunks for document {document_id}")
            
            # 配置分块策略
            chunking_config = ChunkingConfig(
                strategy=ChunkingStrategy.HYBRID,
                chunk_size=800,  # 适中的分块大小
                chunk_overlap=150,
                min_chunk_size=100,
                max_chunk_size=1500,
                preserve_sentences=True,
                preserve_paragraphs=True,
                respect_structure=True
            )
            
            semantic_chunks = create_semantic_chunks(
                content=processing_result["content"],
                structure_metadata=processing_result["metadata"],
                config=chunking_config
            )
            
            if not semantic_chunks:
                raise Exception("No chunks created from document content")
            
            result["steps_completed"].append("semantic_chunking")
            result["stats"]["chunking"] = {
                "chunk_count": len(semantic_chunks),
                "total_characters": sum(len(chunk["content"]) for chunk in semantic_chunks),
                "average_chunk_size": sum(len(chunk["content"]) for chunk in semantic_chunks) / len(semantic_chunks)
            }
            
            # 步骤4: 向量化
            logger.info(f"Step 4: Vectorizing {len(semantic_chunks)} chunks for document {document_id}")
            
            vectorized_chunks = await self.vectorizer.vectorize_chunks(semantic_chunks)
            
            if not vectorized_chunks:
                raise Exception("Failed to vectorize chunks")
            
            result["steps_completed"].append("vectorization")
            result["stats"]["vectorization"] = {
                "vectorized_chunks": len(vectorized_chunks),
                "vector_dimension": len(vectorized_chunks[0]["vector"]) if vectorized_chunks else 0
            }
            
            # 步骤5: 存储向量
            logger.info(f"Step 5: Storing vectors for document {document_id}")
            
            storage_result = await vector_storage_service.store_document_vectors(
                db=db,
                document_id=document_id,
                vectorized_chunks=vectorized_chunks
            )
            
            if not storage_result["success"]:
                raise Exception(f"Failed to store vectors: {storage_result.get('error', 'Unknown error')}")
            
            result["steps_completed"].append("vector_storage")
            result["stats"]["storage"] = {
                "vectors_stored": storage_result["vectors_stored"],
                "vector_ids": storage_result["vector_ids"]
            }
            
            # 更新文档状态为完成
            document.status = ProcessingStatus.COMPLETED.value
            document.processing_metadata = {
                "vectorization_completed_at": result["stats"],
                "total_chunks": len(vectorized_chunks),
                "total_vectors": storage_result["vectors_stored"]
            }
            db.commit()
            
            result["status"] = "completed"
            logger.info(f"Document vectorization completed for {document_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Document vectorization failed for {document_id}: {e}")
            
            # 更新文档状态为失败
            if db:
                try:
                    document = db.query(Document).filter(Document.id == document_id).first()
                    if document:
                        document.status = ProcessingStatus.FAILED.value
                        document.processing_error = str(e)
                        db.commit()
                except Exception as db_error:
                    logger.error(f"Failed to update document status: {db_error}")
            
            result["status"] = "failed"
            result["error"] = str(e)
            return result
            
        finally:
            if db:
                db.close()


# 全局任务处理器实例
task_processor = DocumentVectorizationTask()


@celery_app.task(bind=True, name="process_document_vectorization")
def process_document_vectorization_task(self, document_id: str, user_id: Optional[str] = None):
    """
    Celery 任务：处理文档向量化
    
    Args:
        document_id: 文档ID
        user_id: 用户ID
        
    Returns:
        处理结果
    """
    import asyncio
    
    # 更新任务状态
    self.update_state(
        state="PROGRESS",
        meta={"current": 0, "total": 5, "status": "Starting document vectorization"}
    )
    
    try:
        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            task_processor.process_document_vectorization(document_id, user_id)
        )
        
        loop.close()
        
        # 更新最终状态
        if result["status"] == "completed":
            self.update_state(
                state="SUCCESS",
                meta={
                    "current": 5,
                    "total": 5,
                    "status": "Document vectorization completed",
                    "result": result
                }
            )
        else:
            self.update_state(
                state="FAILURE",
                meta={
                    "current": len(result.get("steps_completed", [])),
                    "total": 5,
                    "status": f"Document vectorization failed: {result.get('error', 'Unknown error')}",
                    "result": result
                }
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Celery task failed for document {document_id}: {e}")
        
        self.update_state(
            state="FAILURE",
            meta={
                "current": 0,
                "total": 5,
                "status": f"Task execution failed: {str(e)}",
                "error": str(e)
            }
        )
        
        return {
            "document_id": document_id,
            "user_id": user_id,
            "status": "failed",
            "error": str(e),
            "steps_completed": []
        }


@celery_app.task(name="reprocess_document_vectorization")
def reprocess_document_vectorization_task(document_id: str, user_id: Optional[str] = None):
    """
    Celery 任务：重新处理文档向量化
    
    Args:
        document_id: 文档ID
        user_id: 用户ID
        
    Returns:
        处理结果
    """
    import asyncio
    
    try:
        # 首先清理旧的向量数据
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 删除旧向量
        cleanup_success = loop.run_until_complete(
            vector_storage_service.delete_document_vectors(document_id)
        )
        
        if cleanup_success:
            logger.info(f"Cleaned up old vectors for document {document_id}")
        
        # 重新处理
        result = loop.run_until_complete(
            task_processor.process_document_vectorization(document_id, user_id)
        )
        
        loop.close()
        return result
        
    except Exception as e:
        logger.error(f"Reprocessing task failed for document {document_id}: {e}")
        return {
            "document_id": document_id,
            "user_id": user_id,
            "status": "failed",
            "error": str(e),
            "steps_completed": []
        }


def submit_document_for_vectorization(document_id: str, user_id: Optional[str] = None) -> str:
    """
    提交文档进行向量化处理
    
    Args:
        document_id: 文档ID
        user_id: 用户ID
        
    Returns:
        任务ID
    """
    try:
        task = process_document_vectorization_task.delay(document_id, user_id)
        logger.info(f"Submitted document {document_id} for vectorization, task ID: {task.id}")
        return task.id
    except Exception as e:
        logger.error(f"Failed to submit document {document_id} for vectorization: {e}")
        raise


def submit_document_for_reprocessing(document_id: str, user_id: Optional[str] = None) -> str:
    """
    提交文档进行重新向量化处理
    
    Args:
        document_id: 文档ID
        user_id: 用户ID
        
    Returns:
        任务ID
    """
    try:
        task = reprocess_document_vectorization_task.delay(document_id, user_id)
        logger.info(f"Submitted document {document_id} for reprocessing, task ID: {task.id}")
        return task.id
    except Exception as e:
        logger.error(f"Failed to submit document {document_id} for reprocessing: {e}")
        raise


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    获取任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态信息
    """
    try:
        task = celery_app.AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "status": task.status,
            "result": task.result,
            "info": task.info,
            "successful": task.successful(),
            "failed": task.failed(),
            "ready": task.ready()
        }
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        return {
            "task_id": task_id,
            "status": "UNKNOWN",
            "error": str(e)
        }


def cancel_task(task_id: str) -> bool:
    """
    取消任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        是否成功取消
    """
    try:
        celery_app.control.revoke(task_id, terminate=True)
        logger.info(f"Cancelled task {task_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        return False