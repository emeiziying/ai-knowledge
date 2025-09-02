"""
Tests for RAG Answer Service functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.chat.answer_service import (
    RAGAnswerService, PromptTemplate, SourceExtractor, 
    AnswerQualityValidator, initialize_answer_service
)
from app.ai.interfaces import ChatMessage


class TestPromptTemplate:
    """Test prompt template functionality."""
    
    def test_format_context(self):
        """Test context formatting from search results."""
        search_results = [
            {
                "content": "This is test content 1",
                "document_metadata": {"original_name": "test1.pdf"},
                "score": 0.85,
                "final_score": 0.90
            },
            {
                "content": "This is test content 2",
                "document_metadata": {"original_name": "test2.pdf"},
                "score": 0.75
            }
        ]
        
        context = PromptTemplate.format_context(search_results)
        
        assert "test1.pdf" in context
        assert "test2.pdf" in context
        assert "This is test content 1" in context
        assert "This is test content 2" in context
        assert "0.90" in context
        assert "0.75" in context
    
    def test_format_context_empty(self):
        """Test context formatting with empty results."""
        context = PromptTemplate.format_context([])
        assert context == ""
    
    def test_format_conversation_history(self):
        """Test conversation history formatting."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        
        history = PromptTemplate.format_conversation_history(messages)
        
        assert "用户: Hello" in history
        assert "助手: Hi there!" in history
        assert "用户: How are you?" in history
    
    def test_format_conversation_history_limit(self):
        """Test conversation history with message limit."""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(15)]
        
        history = PromptTemplate.format_conversation_history(messages)
        
        # Should only include last 10 messages
        lines = history.split('\n')
        assert len(lines) == 10
        assert "Message 14" in history
        assert "Message 5" in history
        assert "Message 4" not in history


class TestSourceExtractor:
    """Test source extraction functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = SourceExtractor()
        self.search_results = [
            {
                "document_id": "doc1",
                "document_metadata": {
                    "original_name": "test_document.pdf",
                    "file_size": 1024,
                    "mime_type": "application/pdf",
                    "created_at": "2024-01-01T00:00:00Z"
                },
                "chunk_index": 0,
                "content": "This is the content of the first chunk",
                "score": 0.85
            },
            {
                "document_id": "doc2", 
                "document_metadata": {
                    "original_name": "another_doc.txt",
                    "file_size": 512,
                    "mime_type": "text/plain",
                    "created_at": "2024-01-02T00:00:00Z"
                },
                "chunk_index": 1,
                "content": "This is content from another document",
                "score": 0.75
            }
        ]
    
    def test_extract_sources_with_citations(self):
        """Test source extraction with explicit citations."""
        answer = "Based on [test_document.pdf], we can see that the information is relevant."
        
        processed_answer, sources = self.extractor.extract_sources(answer, self.search_results)
        
        assert len(sources) == 1
        assert sources[0]["document_name"] == "test_document.pdf"
        assert sources[0]["document_id"] == "doc1"
        assert "[1]" in processed_answer
    
    def test_extract_sources_without_citations(self):
        """Test source extraction without explicit citations."""
        answer = "This is an answer without explicit citations."
        
        processed_answer, sources = self.extractor.extract_sources(answer, self.search_results)
        
        # Should include all documents when no explicit citations
        assert len(sources) == 2
        assert any(s["document_name"] == "test_document.pdf" for s in sources)
        assert any(s["document_name"] == "another_doc.txt" for s in sources)
    
    def test_extract_sources_empty_results(self):
        """Test source extraction with empty search results."""
        answer = "This is an answer."
        
        processed_answer, sources = self.extractor.extract_sources(answer, [])
        
        assert processed_answer == answer
        assert sources == []


class TestAnswerQualityValidator:
    """Test answer quality validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = AnswerQualityValidator()
        self.search_results = [
            {
                "content": "Relevant content for testing",
                "document_metadata": {"original_name": "test.pdf"}
            }
        ]
    
    def test_validate_good_answer(self):
        """Test validation of a good quality answer."""
        answer = "This is a comprehensive answer that addresses the question with proper citations [test.pdf]."
        question = "What is the answer to the question?"
        
        result = self.validator.validate_answer(answer, question, self.search_results)
        
        assert result["is_valid"] is True
        assert result["quality_score"] > 0.7
        assert len(result["issues"]) == 0
    
    def test_validate_short_answer(self):
        """Test validation of a too-short answer."""
        answer = "No."
        question = "What is the answer?"
        
        result = self.validator.validate_answer(answer, question, self.search_results)
        
        assert result["quality_score"] < 1.0
        assert "答案过短" in result["issues"]
    
    def test_validate_poor_answer(self):
        """Test validation of a poor quality answer."""
        answer = "我不知道这个问题的答案。"
        question = "What is the answer?"
        
        result = self.validator.validate_answer(answer, question, self.search_results)
        
        assert result["quality_score"] < 0.7
        assert "答案质量可能较低" in result["issues"]
    
    def test_validate_answer_without_sources(self):
        """Test validation of answer without source citations."""
        answer = "This is a good answer but without source citations."
        question = "What is the answer to the question?"
        
        result = self.validator.validate_answer(answer, question, self.search_results)
        
        assert "建议在答案中添加文档来源引用" in result["suggestions"]


class TestRAGAnswerService:
    """Test RAG Answer Service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ai_service = Mock()
        self.mock_rag_service = Mock()
        self.mock_conversation_service = Mock()
        
        self.service = RAGAnswerService(
            ai_service_manager=self.mock_ai_service,
            rag_service=self.mock_rag_service,
            conversation_service=self.mock_conversation_service
        )
        
        self.mock_db = Mock(spec=Session)
    
    @pytest.mark.asyncio
    async def test_generate_answer_with_context(self):
        """Test answer generation with search context."""
        # Mock search results
        search_results = {
            "results": [
                {
                    "content": "This is relevant content",
                    "document_metadata": {"original_name": "test.pdf"},
                    "document_id": "doc1",
                    "score": 0.85
                }
            ],
            "total_results": 1,
            "search_time_ms": 50.0,
            "cached": False
        }
        
        # Mock RAG service
        self.mock_rag_service.search_documents = AsyncMock(return_value=search_results)
        
        # Mock AI service
        self.mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Based on the document [test.pdf], here is the answer."
        )
        
        # Mock conversation service
        self.mock_conversation_service.get_conversation_context = AsyncMock(return_value=[])
        
        # Test answer generation
        result = await self.service.generate_answer(
            db=self.mock_db,
            question="What is the answer?",
            user_id="user123"
        )
        
        assert "answer" in result
        assert "sources" in result
        assert "quality_validation" in result
        assert result["has_context"] is True
        assert result["context_chunks"] == 1
        
        # Verify service calls
        self.mock_rag_service.search_documents.assert_called_once()
        self.mock_ai_service.generate_chat_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_answer_without_context(self):
        """Test answer generation without search context."""
        # Mock empty search results
        search_results = {
            "results": [],
            "total_results": 0,
            "search_time_ms": 30.0,
            "cached": False
        }
        
        # Mock RAG service
        self.mock_rag_service.search_documents = AsyncMock(return_value=search_results)
        
        # Test answer generation
        result = await self.service.generate_answer(
            db=self.mock_db,
            question="What is the answer?",
            user_id="user123"
        )
        
        assert "answer" in result
        assert result["has_context"] is False
        assert result["context_chunks"] == 0
        assert "很抱歉，我在您的知识库中没有找到" in result["answer"]
        
        # AI service should not be called for no-context answers
        self.mock_ai_service.generate_chat_response.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_generate_answer_with_conversation_context(self):
        """Test answer generation with conversation context."""
        # Mock search results
        search_results = {
            "results": [
                {
                    "content": "Relevant content",
                    "document_metadata": {"original_name": "test.pdf"},
                    "document_id": "doc1",
                    "score": 0.85
                }
            ],
            "total_results": 1,
            "search_time_ms": 50.0,
            "cached": False
        }
        
        # Mock conversation context
        conversation_context = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        
        # Mock services
        self.mock_rag_service.search_documents = AsyncMock(return_value=search_results)
        self.mock_conversation_service.get_conversation_context = AsyncMock(
            return_value=conversation_context
        )
        self.mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Contextual answer based on conversation."
        )
        
        # Test answer generation with conversation
        result = await self.service.generate_answer(
            db=self.mock_db,
            question="Follow-up question",
            user_id="user123",
            conversation_id="conv123"
        )
        
        assert "answer" in result
        assert result["has_context"] is True
        
        # Verify conversation context was retrieved
        self.mock_conversation_service.get_conversation_context.assert_called_once_with(
            db=self.mock_db,
            conversation_id="conv123",
            user_id="user123",
            max_messages=10
        )
    
    @pytest.mark.asyncio
    async def test_generate_streaming_answer(self):
        """Test streaming answer generation."""
        # Mock search results
        search_results = {
            "results": [
                {
                    "content": "Streaming content",
                    "document_metadata": {"original_name": "test.pdf"},
                    "document_id": "doc1",
                    "score": 0.85
                }
            ],
            "total_results": 1,
            "search_time_ms": 50.0,
            "cached": False
        }
        
        # Mock services
        self.mock_rag_service.search_documents = AsyncMock(return_value=search_results)
        self.mock_conversation_service.get_conversation_context = AsyncMock(return_value=[])
        
        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            yield "This is "
            yield "a streaming "
            yield "response."
        
        self.mock_ai_service.generate_chat_response_stream = mock_stream
        
        # Test streaming generation
        chunks = []
        async for chunk in self.service.generate_streaming_answer(
            db=self.mock_db,
            question="What is the answer?",
            user_id="user123"
        ):
            chunks.append(chunk)
        
        assert len(chunks) == 3
        assert chunks[0] == "This is "
        assert chunks[1] == "a streaming "
        assert chunks[2] == "response."
    
    @pytest.mark.asyncio
    async def test_improve_answer(self):
        """Test answer improvement functionality."""
        search_results = [
            {
                "content": "Improved content",
                "document_metadata": {"original_name": "test.pdf"},
                "document_id": "doc1",
                "score": 0.85
            }
        ]
        
        # Mock AI service
        self.mock_ai_service.generate_chat_response = AsyncMock(
            return_value="This is an improved answer based on feedback."
        )
        
        # Test answer improvement
        result = await self.service.improve_answer(
            original_answer="Original answer",
            question="What is the answer?",
            feedback="Please be more specific",
            search_results=search_results
        )
        
        assert "improved_answer" in result
        assert "sources" in result
        assert "quality_validation" in result
        assert result["improvement_applied"] is True
        
        # Verify AI service was called with improvement prompt
        self.mock_ai_service.generate_chat_response.assert_called_once()
        call_args = self.mock_ai_service.generate_chat_response.call_args
        messages = call_args[1]["messages"]
        
        # Check that improvement prompt contains feedback
        user_message = next(msg for msg in messages if msg.role == "user")
        assert "Please be more specific" in user_message.content


@pytest.mark.asyncio
async def test_initialize_answer_service():
    """Test answer service initialization."""
    mock_ai_service = Mock()
    mock_rag_service = Mock()
    mock_conversation_service = Mock()
    
    service = await initialize_answer_service(
        mock_ai_service,
        mock_rag_service,
        mock_conversation_service
    )
    
    assert isinstance(service, RAGAnswerService)
    assert service.ai_service_manager == mock_ai_service
    assert service.rag_service == mock_rag_service
    assert service.conversation_service == mock_conversation_service


if __name__ == "__main__":
    pytest.main([__file__])