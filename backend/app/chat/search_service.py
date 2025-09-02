"""
Advanced search service with filtering, sorting, and analytics.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..models import Document, DocumentChunk, User
from .rag_service import RAGQueryService
from .schemas import (
    SearchFilter, SearchFilterType, SearchSortBy,
    QueryAnalysis, SearchExplanation, SearchStats
)

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes user queries to understand intent and extract key information."""
    
    def __init__(self):
        # Common question words and patterns
        self.question_words = {
            "what", "how", "why", "when", "where", "who", "which", "whose"
        }
        
        self.factual_indicators = {
            "what is", "define", "definition", "meaning", "explain"
        }
        
        self.procedural_indicators = {
            "how to", "steps", "process", "procedure", "method", "way to"
        }
        
        self.conceptual_indicators = {
            "why", "because", "reason", "cause", "effect", "relationship"
        }
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze query to understand intent and extract key information."""
        try:
            processed_query = self._preprocess_query(query)
            query_type = self._determine_query_type(processed_query)
            key_terms = self._extract_key_terms(processed_query)
            intent = self._infer_intent(processed_query, query_type)
            confidence = self._calculate_confidence(processed_query, query_type)
            
            return QueryAnalysis(
                original_query=query,
                processed_query=processed_query,
                query_type=query_type,
                key_terms=key_terms,
                intent=intent,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze query: {e}")
            # Return basic analysis as fallback
            return QueryAnalysis(
                original_query=query,
                processed_query=query.strip(),
                query_type="general",
                key_terms=query.split()[:5],  # First 5 words as key terms
                intent="search",
                confidence=0.5
            )
    
    def _preprocess_query(self, query: str) -> str:
        """Preprocess query for analysis."""
        # Convert to lowercase and remove extra whitespace
        processed = " ".join(query.lower().strip().split())
        
        # Remove common stop words for key term extraction
        # (but keep them for intent analysis)
        return processed
    
    def _determine_query_type(self, query: str) -> str:
        """Determine the type of query."""
        query_lower = query.lower()
        
        # Check for factual queries
        if any(indicator in query_lower for indicator in self.factual_indicators):
            return "factual"
        
        # Check for procedural queries
        if any(indicator in query_lower for indicator in self.procedural_indicators):
            return "procedural"
        
        # Check for conceptual queries
        if any(indicator in query_lower for indicator in self.conceptual_indicators):
            return "conceptual"
        
        # Check for question words
        if any(word in query_lower.split()[:3] for word in self.question_words):
            return "question"
        
        return "general"
    
    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms from the query."""
        import re
        
        # Remove punctuation and split into words
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "is", "are", "was", "were", "be", "been", "have",
            "has", "had", "do", "does", "did", "will", "would", "could", "should",
            "what", "how", "why", "when", "where", "who", "which", "whose", "between"
        }
        
        key_terms = [
            word for word in words 
            if len(word) > 2 and word not in stop_words
        ]
        
        return key_terms[:10]  # Limit to 10 key terms
    
    def _infer_intent(self, query: str, query_type: str) -> str:
        """Infer user intent from query."""
        query_lower = query.lower()
        
        if "find" in query_lower or "search" in query_lower:
            return "search"
        elif "compare" in query_lower or "difference" in query_lower:
            return "compare"
        elif "list" in query_lower or "show me" in query_lower:
            return "list"
        elif query_type == "procedural":
            return "learn_process"
        elif query_type == "factual":
            return "get_information"
        else:
            return "general_inquiry"
    
    def _calculate_confidence(self, query: str, query_type: str) -> float:
        """Calculate confidence in the analysis."""
        # Simple confidence calculation based on query characteristics
        confidence = 0.5  # Base confidence
        
        # Increase confidence for clear patterns
        if query_type in ["factual", "procedural", "conceptual"]:
            confidence += 0.2
        
        # Increase confidence for longer, more specific queries
        word_count = len(query.split())
        if word_count >= 5:
            confidence += 0.1
        if word_count >= 10:
            confidence += 0.1
        
        # Decrease confidence for very short queries
        if word_count < 3:
            confidence -= 0.2
        
        return min(max(confidence, 0.0), 1.0)


class SearchFilterProcessor:
    """Processes search filters and applies them to database queries."""
    
    def apply_filters(
        self,
        db: Session,
        base_query,
        filters: List[SearchFilter],
        user_id: str
    ) -> Tuple[Any, List[str]]:
        """Apply filters to the database query."""
        applied_filters = []
        
        for filter_item in filters:
            try:
                if filter_item.type == SearchFilterType.DOCUMENT_TYPE:
                    base_query, filter_desc = self._apply_document_type_filter(
                        base_query, filter_item.value
                    )
                    applied_filters.append(filter_desc)
                
                elif filter_item.type == SearchFilterType.DATE_RANGE:
                    base_query, filter_desc = self._apply_date_range_filter(
                        base_query, filter_item.value
                    )
                    applied_filters.append(filter_desc)
                
                elif filter_item.type == SearchFilterType.FILE_SIZE:
                    base_query, filter_desc = self._apply_file_size_filter(
                        base_query, filter_item.value
                    )
                    applied_filters.append(filter_desc)
                
            except Exception as e:
                logger.warning(f"Failed to apply filter {filter_item.type}: {e}")
        
        return base_query, applied_filters
    
    def _apply_document_type_filter(self, query, mime_types) -> Tuple[Any, str]:
        """Apply document type filter."""
        if isinstance(mime_types, str):
            mime_types = [mime_types]
        
        query = query.filter(Document.mime_type.in_(mime_types))
        return query, f"Document types: {', '.join(mime_types)}"
    
    def _apply_date_range_filter(self, query, date_range) -> Tuple[Any, str]:
        """Apply date range filter."""
        if isinstance(date_range, dict):
            start_date = date_range.get("start")
            end_date = date_range.get("end")
            
            if start_date:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.filter(Document.created_at >= start_dt)
            
            if end_date:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query = query.filter(Document.created_at <= end_dt)
            
            return query, f"Date range: {start_date or 'any'} to {end_date or 'any'}"
        
        return query, "Invalid date range filter"
    
    def _apply_file_size_filter(self, query, size_range) -> Tuple[Any, str]:
        """Apply file size filter."""
        if isinstance(size_range, dict):
            min_size = size_range.get("min", 0)
            max_size = size_range.get("max")
            
            query = query.filter(Document.file_size >= min_size)
            
            if max_size:
                query = query.filter(Document.file_size <= max_size)
            
            size_desc = f"Size: {min_size}+ bytes"
            if max_size:
                size_desc = f"Size: {min_size}-{max_size} bytes"
            
            return query, size_desc
        
        return query, "Invalid file size filter"


class SearchResultSorter:
    """Sorts search results based on different criteria."""
    
    def sort_results(
        self,
        results: List[Dict[str, Any]],
        sort_by: SearchSortBy,
        document_metadata: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort search results based on the specified criteria."""
        try:
            if sort_by == SearchSortBy.RELEVANCE:
                return sorted(
                    results, 
                    key=lambda x: x.get("final_score", x.get("score", 0)), 
                    reverse=True
                )
            
            elif sort_by == SearchSortBy.DATE:
                return sorted(
                    results,
                    key=lambda x: self._get_document_date(x, document_metadata),
                    reverse=True
                )
            
            elif sort_by == SearchSortBy.DOCUMENT_NAME:
                return sorted(
                    results,
                    key=lambda x: self._get_document_name(x, document_metadata)
                )
            
            else:
                return results
                
        except Exception as e:
            logger.error(f"Failed to sort results: {e}")
            return results
    
    def _get_document_date(self, result: Dict[str, Any], metadata: Dict[str, Dict[str, Any]]) -> datetime:
        """Get document creation date for sorting."""
        doc_id = result.get("document_id")
        if doc_id in metadata:
            date_str = metadata[doc_id].get("created_at")
            if date_str:
                try:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except:
                    pass
        
        return datetime.min  # Fallback for missing dates
    
    def _get_document_name(self, result: Dict[str, Any], metadata: Dict[str, Dict[str, Any]]) -> str:
        """Get document name for sorting."""
        doc_id = result.get("document_id")
        if doc_id in metadata:
            return metadata[doc_id].get("original_name", "")
        
        return ""


class AdvancedSearchService:
    """Advanced search service with filtering, sorting, and analytics."""
    
    def __init__(self, rag_service: RAGQueryService):
        self.rag_service = rag_service
        self.query_analyzer = QueryAnalyzer()
        self.filter_processor = SearchFilterProcessor()
        self.result_sorter = SearchResultSorter()
    
    async def advanced_search(
        self,
        db: Session,
        query: str,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        score_threshold: float = 0.7,
        sort_by: SearchSortBy = SearchSortBy.RELEVANCE,
        filters: Optional[List[SearchFilter]] = None,
        document_ids: Optional[List[str]] = None,
        include_metadata: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Perform advanced search with filtering, sorting, and analytics.
        """
        search_start_time = datetime.now()
        
        try:
            # Analyze query
            query_analysis = self.query_analyzer.analyze_query(query)
            
            # Apply filters to get filtered document IDs
            filtered_doc_ids = document_ids
            applied_filters = []
            
            if filters:
                filtered_doc_ids, applied_filters = await self._apply_document_filters(
                    db, filters, user_id, document_ids
                )
            
            # Perform vector search
            vector_search_start = datetime.now()
            search_results = await self.rag_service.search_documents(
                db=db,
                query=query,
                user_id=user_id,
                limit=limit + offset,  # Get more results to handle offset
                score_threshold=score_threshold,
                document_ids=filtered_doc_ids,
                use_cache=use_cache
            )
            vector_search_time = (datetime.now() - vector_search_start).total_seconds() * 1000
            
            # Extract results and metadata
            results = search_results.get("results", [])
            
            # Get document metadata for sorting
            document_metadata = {}
            if results:
                doc_ids = list(set(result.get("document_id") for result in results))
                documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
                document_metadata = {
                    str(doc.id): {
                        "filename": doc.filename,
                        "original_name": doc.original_name,
                        "created_at": doc.created_at.isoformat(),
                        "file_size": doc.file_size,
                        "mime_type": doc.mime_type
                    }
                    for doc in documents
                }
            
            # Sort results
            sorting_start = datetime.now()
            sorted_results = self.result_sorter.sort_results(
                results, sort_by, document_metadata
            )
            sorting_time = (datetime.now() - sorting_start).total_seconds() * 1000
            
            # Apply offset and limit
            paginated_results = sorted_results[offset:offset + limit]
            
            # Calculate statistics
            total_search_time = (datetime.now() - search_start_time).total_seconds() * 1000
            
            stats = SearchStats(
                total_results=len(sorted_results),
                search_time_ms=total_search_time,
                cached=search_results.get("cached", False),
                vector_search_time_ms=vector_search_time,
                ranking_time_ms=sorting_time,
                avg_score=sum(r.get("score", 0) for r in paginated_results) / len(paginated_results) if paginated_results else 0,
                max_score=max((r.get("score", 0) for r in paginated_results), default=0),
                min_score=min((r.get("score", 0) for r in paginated_results), default=0)
            )
            
            # Generate explanation
            explanation = self._generate_search_explanation(
                query_analysis, len(sorted_results), applied_filters, sort_by
            )
            
            # Generate related queries
            related_queries = await self._generate_related_queries(
                query_analysis, paginated_results
            )
            
            return {
                "results": paginated_results,
                "stats": stats,
                "query_analysis": query_analysis,
                "explanation": explanation,
                "related_queries": related_queries,
                "applied_filters": applied_filters,
                "document_metadata": document_metadata if include_metadata else None
            }
            
        except Exception as e:
            logger.error(f"Advanced search failed: {e}")
            raise
    
    async def _apply_document_filters(
        self,
        db: Session,
        filters: List[SearchFilter],
        user_id: str,
        existing_doc_ids: Optional[List[str]] = None
    ) -> Tuple[List[str], List[str]]:
        """Apply document-level filters and return filtered document IDs."""
        try:
            # Start with user's documents
            query = db.query(Document).filter(
                Document.user_id == user_id,
                Document.status == "completed"
            )
            
            # Apply existing document ID filter if provided
            if existing_doc_ids:
                query = query.filter(Document.id.in_(existing_doc_ids))
            
            # Apply filters
            query, applied_filters = self.filter_processor.apply_filters(
                db, query, filters, user_id
            )
            
            # Get filtered document IDs
            documents = query.all()
            filtered_doc_ids = [str(doc.id) for doc in documents]
            
            return filtered_doc_ids, applied_filters
            
        except Exception as e:
            logger.error(f"Failed to apply document filters: {e}")
            return existing_doc_ids or [], []
    
    def _generate_search_explanation(
        self,
        query_analysis: QueryAnalysis,
        result_count: int,
        applied_filters: List[str],
        sort_by: SearchSortBy
    ) -> SearchExplanation:
        """Generate explanation of search results."""
        try:
            # Query interpretation
            interpretation = f"Interpreted as a {query_analysis.query_type} query"
            if query_analysis.intent:
                interpretation += f" with intent to {query_analysis.intent}"
            
            # Search strategy
            strategy = "Used semantic vector search to find relevant document chunks"
            if applied_filters:
                strategy += f" with {len(applied_filters)} filter(s) applied"
            
            # Ranking explanation
            ranking = f"Results sorted by {sort_by.value}"
            if sort_by == SearchSortBy.RELEVANCE:
                ranking += " (combination of semantic similarity and keyword matching)"
            
            # Suggestions for improvement
            suggestions = []
            if result_count == 0:
                suggestions.extend([
                    "Try using different keywords",
                    "Remove some filters to broaden the search",
                    "Check if documents are properly uploaded and processed"
                ])
            elif result_count < 5:
                suggestions.extend([
                    "Try using synonyms or related terms",
                    "Make the query more general"
                ])
            
            return SearchExplanation(
                query_interpretation=interpretation,
                search_strategy=strategy,
                ranking_explanation=ranking,
                suggestions_for_improvement=suggestions if suggestions else None
            )
            
        except Exception as e:
            logger.error(f"Failed to generate search explanation: {e}")
            return SearchExplanation(
                query_interpretation="Query processed",
                search_strategy="Semantic search performed",
                ranking_explanation="Results ranked by relevance"
            )
    
    async def _generate_related_queries(
        self,
        query_analysis: QueryAnalysis,
        results: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate related query suggestions."""
        try:
            related_queries = []
            
            # Generate variations based on key terms
            key_terms = query_analysis.key_terms[:3]  # Use top 3 key terms
            
            if len(key_terms) >= 2:
                # Create combinations of key terms
                for i, term1 in enumerate(key_terms):
                    for term2 in key_terms[i+1:]:
                        related_queries.append(f"{term1} and {term2}")
                        related_queries.append(f"difference between {term1} and {term2}")
            
            # Add query type variations
            if query_analysis.query_type == "factual":
                for term in key_terms[:2]:
                    related_queries.append(f"how to use {term}")
                    related_queries.append(f"examples of {term}")
            
            elif query_analysis.query_type == "procedural":
                for term in key_terms[:2]:
                    related_queries.append(f"what is {term}")
                    related_queries.append(f"benefits of {term}")
            
            # Limit to 5 related queries
            return related_queries[:5]
            
        except Exception as e:
            logger.error(f"Failed to generate related queries: {e}")
            return []