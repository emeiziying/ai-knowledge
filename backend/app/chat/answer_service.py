"""
RAG Answer Generation Service for creating intelligent responses based on retrieved content.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from ..ai.service_manager import AIServiceManager
from ..ai.interfaces import ChatMessage
from .rag_service import RAGQueryService
from .conversation_service import ConversationService

logger = logging.getLogger(__name__)


class PromptTemplate:
    """Template manager for RAG prompts."""
    
    # System prompt for RAG responses
    SYSTEM_PROMPT = """你是一个智能知识库助手。你的任务是基于提供的文档内容回答用户问题。

重要指导原则：
1. 只基于提供的文档内容回答问题，不要使用你的预训练知识
2. 如果文档中没有相关信息，明确告知用户
3. 在回答中引用具体的文档来源
4. 保持回答准确、简洁且有帮助
5. 如果问题不清楚，要求用户澄清

引用格式：
- 使用 [文档名称] 来标注信息来源
- 如果有多个来源，列出所有相关文档
"""

    # User query template with context
    USER_QUERY_TEMPLATE = """基于以下文档内容回答问题：

=== 相关文档内容 ===
{context}

=== 用户问题 ===
{question}

请基于上述文档内容回答问题，并在回答中标注信息来源。如果文档中没有相关信息，请明确说明。"""

    # No context template
    NO_CONTEXT_TEMPLATE = """用户问题：{question}

很抱歉，我在您的知识库中没有找到与此问题相关的信息。

建议：
1. 尝试使用不同的关键词重新提问
2. 检查是否已上传相关文档
3. 确认问题是否在已上传的文档范围内

如果您认为相关信息应该存在，请尝试更具体的问题或上传更多相关文档。"""

    # Multi-turn conversation template
    CONVERSATION_TEMPLATE = """基于以下对话历史和文档内容回答问题：

=== 对话历史 ===
{conversation_history}

=== 相关文档内容 ===
{context}

=== 当前问题 ===
{question}

请考虑对话上下文，基于文档内容回答当前问题，并标注信息来源。"""

    @classmethod
    def format_context(cls, search_results: List[Dict[str, Any]]) -> str:
        """Format search results into context string."""
        if not search_results:
            return ""
        
        context_parts = []
        for i, result in enumerate(search_results, 1):
            doc_name = result.get("document_metadata", {}).get("original_name", "未知文档")
            content = result.get("content", "")
            score = result.get("final_score", result.get("score", 0))
            
            context_part = f"""文档 {i}: {doc_name} (相关度: {score:.2f})
内容: {content}
---"""
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    @classmethod
    def format_conversation_history(cls, messages: List[Dict[str, Any]]) -> str:
        """Format conversation history for context."""
        if not messages:
            return ""
        
        history_parts = []
        for msg in messages[-10:]:  # Only include last 10 messages
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"]
            history_parts.append(f"{role}: {content}")
        
        return "\n".join(history_parts)


class SourceExtractor:
    """Extract and format source citations from answers."""
    
    def __init__(self):
        # Pattern to match document references in answers
        self.citation_pattern = re.compile(r'\[([^\]]+)\]')
        self.doc_name_pattern = re.compile(r'文档\s*\d*\s*[:：]\s*([^(（]+)')
    
    def extract_sources(
        self, 
        answer: str, 
        search_results: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extract source citations from answer and create source list.
        
        Args:
            answer: Generated answer text
            search_results: Original search results used for context
            
        Returns:
            Tuple of (processed_answer, sources_list)
        """
        try:
            sources = []
            processed_answer = answer
            
            # Create mapping of document names to metadata
            doc_mapping = {}
            for result in search_results:
                doc_metadata = result.get("document_metadata", {})
                doc_name = doc_metadata.get("original_name", "")
                if doc_name and doc_name not in doc_mapping:
                    doc_mapping[doc_name] = {
                        "document_id": result.get("document_id"),
                        "document_name": doc_name,
                        "file_size": doc_metadata.get("file_size"),
                        "mime_type": doc_metadata.get("mime_type"),
                        "created_at": doc_metadata.get("created_at"),
                        "chunks_referenced": []
                    }
                
                # Add chunk information
                if doc_name in doc_mapping:
                    doc_mapping[doc_name]["chunks_referenced"].append({
                        "chunk_index": result.get("chunk_index"),
                        "content_preview": result.get("content", "")[:200] + "...",
                        "score": result.get("final_score", result.get("score", 0))
                    })
            
            # Find citations in the answer
            citations_found = self.citation_pattern.findall(answer)
            
            # Match citations to documents
            for citation in citations_found:
                # Try to find matching document
                matched_doc = None
                for doc_name, doc_info in doc_mapping.items():
                    if (citation.lower() in doc_name.lower() or 
                        doc_name.lower() in citation.lower()):
                        matched_doc = doc_info
                        break
                
                if matched_doc and matched_doc not in sources:
                    sources.append(matched_doc)
            
            # If no explicit citations found, include all referenced documents
            if not sources:
                sources = list(doc_mapping.values())
            
            # Add source numbers to answer
            processed_answer = self._add_source_numbers(processed_answer, sources)
            
            return processed_answer, sources
            
        except Exception as e:
            logger.error(f"Failed to extract sources: {e}")
            return answer, []
    
    def _add_source_numbers(self, answer: str, sources: List[Dict[str, Any]]) -> str:
        """Add numbered source references to answer."""
        try:
            # Create mapping of document names to numbers
            doc_to_number = {}
            for i, source in enumerate(sources, 1):
                doc_name = source["document_name"]
                doc_to_number[doc_name] = i
            
            # Replace document references with numbered citations
            def replace_citation(match):
                citation = match.group(1)
                for doc_name, number in doc_to_number.items():
                    if (citation.lower() in doc_name.lower() or 
                        doc_name.lower() in citation.lower()):
                        return f"[{number}]"
                return match.group(0)  # Return original if no match
            
            processed_answer = self.citation_pattern.sub(replace_citation, answer)
            
            return processed_answer
            
        except Exception as e:
            logger.error(f"Failed to add source numbers: {e}")
            return answer


class AnswerQualityValidator:
    """Validate and improve answer quality."""
    
    def __init__(self):
        self.min_answer_length = 10
        self.max_answer_length = 5000
        
        # Patterns for detecting poor answers
        self.poor_answer_patterns = [
            r"我不知道",
            r"无法回答",
            r"没有信息",
            r"不清楚",
            r"无法确定"
        ]
    
    def validate_answer(
        self, 
        answer: str, 
        question: str, 
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate answer quality and provide feedback.
        
        Args:
            answer: Generated answer
            question: Original question
            search_results: Search results used for context
            
        Returns:
            Validation result with quality metrics
        """
        try:
            validation_result = {
                "is_valid": True,
                "quality_score": 1.0,
                "issues": [],
                "suggestions": []
            }
            
            # Check answer length
            if len(answer) < self.min_answer_length:
                validation_result["issues"].append("答案过短")
                validation_result["quality_score"] -= 0.3
            
            if len(answer) > self.max_answer_length:
                validation_result["issues"].append("答案过长")
                validation_result["quality_score"] -= 0.1
            
            # Check for poor answer patterns
            answer_lower = answer.lower()
            for pattern in self.poor_answer_patterns:
                if re.search(pattern, answer_lower):
                    validation_result["issues"].append("答案质量可能较低")
                    validation_result["quality_score"] -= 0.4
                    break
            
            # Check if answer addresses the question
            question_keywords = set(question.lower().split())
            answer_keywords = set(answer.lower().split())
            keyword_overlap = len(question_keywords.intersection(answer_keywords))
            
            if keyword_overlap < 2:
                validation_result["issues"].append("答案可能与问题不够相关")
                validation_result["quality_score"] -= 0.2
            
            # Check if sources are referenced
            if search_results and "[" not in answer:
                validation_result["suggestions"].append("建议在答案中添加文档来源引用")
                validation_result["quality_score"] -= 0.1
            
            # Set overall validity
            validation_result["is_valid"] = validation_result["quality_score"] > 0.3
            validation_result["quality_score"] = max(0.0, validation_result["quality_score"])
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to validate answer: {e}")
            return {
                "is_valid": True,
                "quality_score": 0.5,
                "issues": ["验证过程出错"],
                "suggestions": []
            }


class RAGAnswerService:
    """Main service for generating RAG-based answers."""
    
    def __init__(
        self, 
        ai_service_manager: AIServiceManager,
        rag_service: RAGQueryService,
        conversation_service: ConversationService
    ):
        self.ai_service_manager = ai_service_manager
        self.rag_service = rag_service
        self.conversation_service = conversation_service
        self.prompt_template = PromptTemplate()
        self.source_extractor = SourceExtractor()
        self.quality_validator = AnswerQualityValidator()
    
    async def generate_answer(
        self,
        db: Session,
        question: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        search_params: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate RAG-based answer for user question.
        
        Args:
            db: Database session
            question: User question
            user_id: User ID
            conversation_id: Optional conversation ID for context
            search_params: Optional search parameters
            model: Optional AI model to use
            
        Returns:
            Dictionary containing answer, sources, and metadata
        """
        try:
            start_time = datetime.now()
            
            # Set default search parameters
            if search_params is None:
                search_params = {
                    "limit": 5,
                    "score_threshold": 0.7,
                    "use_cache": True
                }
            
            # Perform semantic search
            search_results = await self.rag_service.search_documents(
                db=db,
                query=question,
                user_id=user_id,
                **search_params
            )
            
            # Get conversation context if conversation_id provided
            conversation_context = []
            if conversation_id:
                try:
                    conversation_context = await self.conversation_service.get_conversation_context(
                        db=db,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        max_messages=10
                    )
                except Exception as e:
                    logger.warning(f"Failed to get conversation context: {e}")
            
            # Generate answer based on search results
            if search_results["results"]:
                answer_data = await self._generate_contextual_answer(
                    question=question,
                    search_results=search_results["results"],
                    conversation_context=conversation_context,
                    model=model
                )
            else:
                answer_data = await self._generate_no_context_answer(
                    question=question,
                    model=model
                )
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Add metadata
            answer_data.update({
                "question": question,
                "search_metadata": {
                    "total_results": search_results["total_results"],
                    "search_time_ms": search_results["search_time_ms"],
                    "cached": search_results["cached"]
                },
                "processing_time_ms": round(processing_time, 2),
                "model_used": model,
                "has_context": len(search_results["results"]) > 0
            })
            
            return answer_data
            
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            from ..middleware.error_handler import AIServiceError
            raise AIServiceError(
                message=f"Failed to generate answer: {str(e)}",
                service_type="rag_answer_service",
                error_code="ANSWER_GENERATION_FAILED"
            )
    
    async def _generate_contextual_answer(
        self,
        question: str,
        search_results: List[Dict[str, Any]],
        conversation_context: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate answer with retrieved context."""
        try:
            # Format context from search results
            context = self.prompt_template.format_context(search_results)
            
            # Prepare messages for AI service
            messages = [
                ChatMessage(role="system", content=self.prompt_template.SYSTEM_PROMPT)
            ]
            
            # Add conversation context if available
            if conversation_context:
                conversation_history = self.prompt_template.format_conversation_history(conversation_context)
                user_content = self.prompt_template.CONVERSATION_TEMPLATE.format(
                    conversation_history=conversation_history,
                    context=context,
                    question=question
                )
            else:
                user_content = self.prompt_template.USER_QUERY_TEMPLATE.format(
                    context=context,
                    question=question
                )
            
            messages.append(ChatMessage(role="user", content=user_content))
            
            # Generate answer using AI service
            answer = await self.ai_service_manager.generate_chat_response(
                messages=messages,
                model=model,
                temperature=0.3,  # Lower temperature for more factual responses
                max_tokens=2000
            )
            
            # Extract sources and citations
            processed_answer, sources = self.source_extractor.extract_sources(
                answer, search_results
            )
            
            # Validate answer quality
            quality_validation = self.quality_validator.validate_answer(
                processed_answer, question, search_results
            )
            
            return {
                "answer": processed_answer,
                "sources": sources,
                "quality_validation": quality_validation,
                "context_used": True,
                "context_chunks": len(search_results)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate contextual answer: {e}")
            raise
    
    async def _generate_no_context_answer(
        self,
        question: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate answer when no relevant context is found."""
        try:
            # Use template for no context scenario
            answer = self.prompt_template.NO_CONTEXT_TEMPLATE.format(question=question)
            
            return {
                "answer": answer,
                "sources": [],
                "quality_validation": {
                    "is_valid": True,
                    "quality_score": 0.8,
                    "issues": [],
                    "suggestions": ["尝试上传更多相关文档", "使用不同的关键词重新提问"]
                },
                "context_used": False,
                "context_chunks": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to generate no-context answer: {e}")
            raise
    
    async def generate_streaming_answer(
        self,
        db: Session,
        question: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        search_params: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ):
        """
        Generate streaming RAG-based answer for real-time responses.
        
        Args:
            db: Database session
            question: User question
            user_id: User ID
            conversation_id: Optional conversation ID for context
            search_params: Optional search parameters
            model: Optional AI model to use
            
        Yields:
            Streaming answer chunks
        """
        try:
            # Set default search parameters
            if search_params is None:
                search_params = {
                    "limit": 5,
                    "score_threshold": 0.7,
                    "use_cache": True
                }
            
            # Perform semantic search
            search_results = await self.rag_service.search_documents(
                db=db,
                query=question,
                user_id=user_id,
                **search_params
            )
            
            # If no context found, yield no-context response
            if not search_results["results"]:
                no_context_answer = self.prompt_template.NO_CONTEXT_TEMPLATE.format(question=question)
                yield no_context_answer
                return
            
            # Get conversation context if conversation_id provided
            conversation_context = []
            if conversation_id:
                try:
                    conversation_context = await self.conversation_service.get_conversation_context(
                        db=db,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        max_messages=10
                    )
                except Exception as e:
                    logger.warning(f"Failed to get conversation context: {e}")
            
            # Format context and prepare messages
            context = self.prompt_template.format_context(search_results["results"])
            
            messages = [
                ChatMessage(role="system", content=self.prompt_template.SYSTEM_PROMPT)
            ]
            
            if conversation_context:
                conversation_history = self.prompt_template.format_conversation_history(conversation_context)
                user_content = self.prompt_template.CONVERSATION_TEMPLATE.format(
                    conversation_history=conversation_history,
                    context=context,
                    question=question
                )
            else:
                user_content = self.prompt_template.USER_QUERY_TEMPLATE.format(
                    context=context,
                    question=question
                )
            
            messages.append(ChatMessage(role="user", content=user_content))
            
            # Generate streaming response
            async for chunk in self.ai_service_manager.generate_chat_response_stream(
                messages=messages,
                model=model,
                temperature=0.3,
                max_tokens=2000
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Failed to generate streaming answer: {e}")
            from ..middleware.error_handler import AIServiceError
            # For streaming, we yield the error message instead of raising
            yield f"抱歉，生成回答时出现错误：{str(e)}"
    
    async def improve_answer(
        self,
        original_answer: str,
        question: str,
        feedback: str,
        search_results: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Improve answer based on user feedback.
        
        Args:
            original_answer: Original generated answer
            question: Original question
            feedback: User feedback on the answer
            search_results: Original search results
            model: Optional AI model to use
            
        Returns:
            Improved answer with metadata
        """
        try:
            # Format context
            context = self.prompt_template.format_context(search_results)
            
            # Create improvement prompt
            improvement_prompt = f"""请基于用户反馈改进以下回答：

原始问题：{question}

原始回答：{original_answer}

用户反馈：{feedback}

相关文档内容：
{context}

请根据用户反馈改进回答，确保：
1. 解决用户提出的问题
2. 保持基于文档内容的准确性
3. 添加或修正引用来源
4. 提供更清晰、更有帮助的信息"""

            messages = [
                ChatMessage(role="system", content=self.prompt_template.SYSTEM_PROMPT),
                ChatMessage(role="user", content=improvement_prompt)
            ]
            
            # Generate improved answer
            improved_answer = await self.ai_service_manager.generate_chat_response(
                messages=messages,
                model=model,
                temperature=0.3,
                max_tokens=2000
            )
            
            # Extract sources and validate
            processed_answer, sources = self.source_extractor.extract_sources(
                improved_answer, search_results
            )
            
            quality_validation = self.quality_validator.validate_answer(
                processed_answer, question, search_results
            )
            
            return {
                "improved_answer": processed_answer,
                "sources": sources,
                "quality_validation": quality_validation,
                "improvement_applied": True
            }
            
        except Exception as e:
            logger.error(f"Failed to improve answer: {e}")
            from ..middleware.error_handler import AIServiceError
            raise AIServiceError(
                message=f"Failed to improve answer: {str(e)}",
                service_type="rag_answer_service",
                error_code="ANSWER_IMPROVEMENT_FAILED"
            )


# Global service instance
_answer_service = None


async def initialize_answer_service(
    ai_service_manager: AIServiceManager,
    rag_service: RAGQueryService,
    conversation_service: ConversationService
) -> RAGAnswerService:
    """Initialize the global RAG answer service."""
    global _answer_service
    
    try:
        _answer_service = RAGAnswerService(
            ai_service_manager=ai_service_manager,
            rag_service=rag_service,
            conversation_service=conversation_service
        )
        logger.info("RAG answer service initialized")
        return _answer_service
    except Exception as e:
        logger.error(f"Failed to initialize RAG answer service: {e}")
        raise


def get_answer_service() -> Optional[RAGAnswerService]:
    """Get the global RAG answer service instance."""
    return _answer_service