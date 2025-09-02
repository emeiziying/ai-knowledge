"""
嵌入模型集成，用于文本向量化。
Embedding model integration for text vectorization.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(Enum):
    """嵌入模型提供商"""
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"


@dataclass
class EmbeddingConfig:
    """嵌入配置"""
    provider: EmbeddingProvider = EmbeddingProvider.SENTENCE_TRANSFORMERS
    model_name: str = "all-MiniLM-L6-v2"  # 默认使用轻量级模型
    batch_size: int = 32
    max_length: int = 512
    normalize_embeddings: bool = True
    device: str = "cpu"  # "cpu" or "cuda"
    api_key: Optional[str] = None  # For API-based providers


class EmbeddingService(ABC):
    """嵌入服务抽象基类"""
    
    @abstractmethod
    async def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """编码文本为向量"""
        pass
    
    @abstractmethod
    async def encode_single_text(self, text: str) -> List[float]:
        """编码单个文本为向量"""
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """获取嵌入向量维度"""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化嵌入服务"""
        pass


class SentenceTransformersEmbedding(EmbeddingService):
    """基于 Sentence Transformers 的嵌入服务"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model = None
        self._dimension = None
    
    async def initialize(self) -> bool:
        """初始化模型"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # 在线程池中加载模型以避免阻塞
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, 
                lambda: SentenceTransformer(
                    self.config.model_name,
                    device=self.config.device
                )
            )
            
            # 获取嵌入维度
            test_embedding = self.model.encode(["test"], normalize_embeddings=False)
            self._dimension = test_embedding.shape[1]
            
            logger.info(f"Initialized SentenceTransformers model: {self.config.model_name}")
            logger.info(f"Embedding dimension: {self._dimension}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SentenceTransformers model: {e}")
            return False
    
    async def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """批量编码文本"""
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        if not texts:
            return []
        
        try:
            # 预处理文本
            processed_texts = [self._preprocess_text(text) for text in texts]
            
            # 在线程池中执行编码以避免阻塞
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.model.encode(
                    processed_texts,
                    batch_size=self.config.batch_size,
                    normalize_embeddings=self.config.normalize_embeddings,
                    show_progress_bar=False
                )
            )
            
            # 转换为列表格式
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise
    
    async def encode_single_text(self, text: str) -> List[float]:
        """编码单个文本"""
        embeddings = await self.encode_texts([text])
        return embeddings[0] if embeddings else []
    
    def get_embedding_dimension(self) -> int:
        """获取嵌入维度"""
        return self._dimension or 384  # 默认维度
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        # 移除过多的空白字符
        text = " ".join(text.split())
        
        # 截断过长的文本
        if len(text) > self.config.max_length * 4:  # 粗略估计字符数
            text = text[:self.config.max_length * 4]
        
        return text


class OpenAIEmbedding(EmbeddingService):
    """基于 OpenAI API 的嵌入服务"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.client = None
        self._dimension = 1536  # OpenAI text-embedding-ada-002 的维度
    
    async def initialize(self) -> bool:
        """初始化 OpenAI 客户端"""
        try:
            import openai
            
            if not self.config.api_key:
                logger.error("OpenAI API key not provided")
                return False
            
            self.client = openai.AsyncOpenAI(api_key=self.config.api_key)
            
            # 测试连接
            test_response = await self.client.embeddings.create(
                model=self.config.model_name or "text-embedding-ada-002",
                input="test"
            )
            
            self._dimension = len(test_response.data[0].embedding)
            
            logger.info(f"Initialized OpenAI embedding model: {self.config.model_name}")
            logger.info(f"Embedding dimension: {self._dimension}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI embedding: {e}")
            return False
    
    async def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """批量编码文本"""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        
        if not texts:
            return []
        
        try:
            # OpenAI API 支持批量处理
            response = await self.client.embeddings.create(
                model=self.config.model_name or "text-embedding-ada-002",
                input=texts
            )
            
            # 提取嵌入向量
            embeddings = [data.embedding for data in response.data]
            
            # 归一化（如果需要）
            if self.config.normalize_embeddings:
                embeddings = [self._normalize_vector(emb) for emb in embeddings]
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to encode texts with OpenAI: {e}")
            raise
    
    async def encode_single_text(self, text: str) -> List[float]:
        """编码单个文本"""
        embeddings = await self.encode_texts([text])
        return embeddings[0] if embeddings else []
    
    def get_embedding_dimension(self) -> int:
        """获取嵌入维度"""
        return self._dimension
    
    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """归一化向量"""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return (np.array(vector) / norm).tolist()


class EmbeddingServiceFactory:
    """嵌入服务工厂"""
    
    @staticmethod
    def create_service(config: EmbeddingConfig) -> EmbeddingService:
        """创建嵌入服务实例"""
        if config.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
            return SentenceTransformersEmbedding(config)
        elif config.provider == EmbeddingProvider.OPENAI:
            return OpenAIEmbedding(config)
        else:
            raise ValueError(f"Unsupported embedding provider: {config.provider}")


class DocumentVectorizer:
    """文档向量化器"""
    
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
    
    async def vectorize_chunks(
        self, 
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        对文档分块进行向量化
        
        Args:
            chunks: 文档分块列表
            
        Returns:
            包含向量的分块列表
        """
        if not chunks:
            return []
        
        try:
            # 提取文本内容
            texts = [chunk["content"] for chunk in chunks]
            
            # 批量生成嵌入向量
            embeddings = await self.embedding_service.encode_texts(texts)
            
            # 将向量添加到分块中
            vectorized_chunks = []
            for i, chunk in enumerate(chunks):
                vectorized_chunk = chunk.copy()
                vectorized_chunk["vector"] = embeddings[i]
                vectorized_chunk["metadata"]["vector_dimension"] = len(embeddings[i])
                vectorized_chunk["metadata"]["embedding_model"] = self.embedding_service.config.model_name
                
                vectorized_chunks.append(vectorized_chunk)
            
            logger.info(f"Vectorized {len(vectorized_chunks)} chunks")
            return vectorized_chunks
            
        except Exception as e:
            logger.error(f"Failed to vectorize chunks: {e}")
            raise
    
    async def vectorize_query(self, query: str) -> List[float]:
        """
        对查询文本进行向量化
        
        Args:
            query: 查询文本
            
        Returns:
            查询向量
        """
        try:
            return await self.embedding_service.encode_single_text(query)
        except Exception as e:
            logger.error(f"Failed to vectorize query: {e}")
            raise


class EmbeddingManager:
    """嵌入管理器 - 管理多个嵌入服务"""
    
    def __init__(self):
        self.services: Dict[str, EmbeddingService] = {}
        self.default_service: Optional[str] = None
    
    async def add_service(self, name: str, config: EmbeddingConfig) -> bool:
        """添加嵌入服务"""
        try:
            service = EmbeddingServiceFactory.create_service(config)
            
            if await service.initialize():
                self.services[name] = service
                
                # 设置第一个成功初始化的服务为默认服务
                if not self.default_service:
                    self.default_service = name
                
                logger.info(f"Added embedding service: {name}")
                return True
            else:
                logger.error(f"Failed to initialize embedding service: {name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add embedding service {name}: {e}")
            return False
    
    def get_service(self, name: Optional[str] = None) -> Optional[EmbeddingService]:
        """获取嵌入服务"""
        service_name = name or self.default_service
        return self.services.get(service_name)
    
    def get_vectorizer(self, service_name: Optional[str] = None) -> Optional[DocumentVectorizer]:
        """获取文档向量化器"""
        service = self.get_service(service_name)
        return DocumentVectorizer(service) if service else None
    
    def list_services(self) -> List[str]:
        """列出所有可用的服务"""
        return list(self.services.keys())
    
    async def health_check(self) -> Dict[str, bool]:
        """检查所有服务的健康状态"""
        health_status = {}
        
        for name, service in self.services.items():
            try:
                # 尝试编码一个测试文本
                await service.encode_single_text("health check")
                health_status[name] = True
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                health_status[name] = False
        
        return health_status


# 全局嵌入管理器实例
embedding_manager = EmbeddingManager()


async def initialize_default_embedding_service() -> bool:
    """初始化默认嵌入服务"""
    try:
        # 尝试初始化 Sentence Transformers 服务
        config = EmbeddingConfig(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
            model_name="all-MiniLM-L6-v2",  # 轻量级模型
            batch_size=16,
            normalize_embeddings=True
        )
        
        success = await embedding_manager.add_service("default", config)
        
        if success:
            logger.info("Default embedding service initialized successfully")
        else:
            logger.error("Failed to initialize default embedding service")
        
        return success
        
    except Exception as e:
        logger.error(f"Error initializing default embedding service: {e}")
        return False


def get_default_vectorizer() -> Optional[DocumentVectorizer]:
    """获取默认的文档向量化器"""
    return embedding_manager.get_vectorizer()