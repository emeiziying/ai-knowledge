"""
Text preprocessing utilities for document content.
Handles text cleaning, normalization, and preparation for chunking.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    """Configuration for text preprocessing."""
    remove_extra_whitespace: bool = True
    normalize_unicode: bool = True
    remove_special_chars: bool = False
    min_line_length: int = 3
    preserve_structure: bool = True
    remove_urls: bool = False
    remove_emails: bool = False
    lowercase: bool = False


class TextPreprocessor:
    """Text preprocessing utility for document content."""
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()
    
    def preprocess(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Preprocess text content for better chunking and indexing.
        
        Args:
            content: Raw text content
            metadata: Document metadata for context
            
        Returns:
            Dictionary containing:
            - processed_content: Cleaned and normalized text
            - original_length: Original content length
            - processed_length: Processed content length
            - preprocessing_stats: Statistics about preprocessing
        """
        original_length = len(content)
        processed_content = content
        stats = {
            "original_length": original_length,
            "operations_applied": []
        }
        
        # Apply preprocessing steps
        if self.config.normalize_unicode:
            processed_content = self._normalize_unicode(processed_content)
            stats["operations_applied"].append("unicode_normalization")
        
        if self.config.remove_extra_whitespace:
            processed_content = self._remove_extra_whitespace(processed_content)
            stats["operations_applied"].append("whitespace_cleanup")
        
        if self.config.remove_urls:
            processed_content = self._remove_urls(processed_content)
            stats["operations_applied"].append("url_removal")
        
        if self.config.remove_emails:
            processed_content = self._remove_emails(processed_content)
            stats["operations_applied"].append("email_removal")
        
        if self.config.remove_special_chars:
            processed_content = self._remove_special_chars(processed_content)
            stats["operations_applied"].append("special_char_removal")
        
        if self.config.lowercase:
            processed_content = processed_content.lower()
            stats["operations_applied"].append("lowercase")
        
        # Filter short lines if configured
        if self.config.min_line_length > 0:
            processed_content = self._filter_short_lines(processed_content)
            stats["operations_applied"].append("short_line_filtering")
        
        # Final cleanup
        processed_content = self._final_cleanup(processed_content)
        
        stats.update({
            "processed_length": len(processed_content),
            "reduction_ratio": 1 - (len(processed_content) / original_length) if original_length > 0 else 0
        })
        
        return {
            "processed_content": processed_content,
            "original_length": original_length,
            "processed_length": len(processed_content),
            "preprocessing_stats": stats
        }
    
    def _normalize_unicode(self, text: str) -> str:
        """Normalize unicode characters."""
        import unicodedata
        return unicodedata.normalize('NFKC', text)
    
    def _remove_extra_whitespace(self, text: str) -> str:
        """Remove extra whitespace while preserving structure."""
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove trailing whitespace from lines
        lines = text.split('\n')
        lines = [line.rstrip() for line in lines]
        
        return '\n'.join(lines)
    
    def _remove_urls(self, text: str) -> str:
        """Remove URLs from text."""
        url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+|www\.[^\s<>"{}|\\^`[\]]+'
        return re.sub(url_pattern, '[URL]', text)
    
    def _remove_emails(self, text: str) -> str:
        """Remove email addresses from text."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.sub(email_pattern, '[EMAIL]', text)
    
    def _remove_special_chars(self, text: str) -> str:
        """Remove special characters while preserving basic punctuation."""
        # Keep letters, numbers, basic punctuation, and whitespace
        return re.sub(r'[^\w\s.,!?;:()\-"\'\n]', '', text)
    
    def _filter_short_lines(self, text: str) -> str:
        """Filter out very short lines that might be noise."""
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            stripped_line = line.strip()
            if len(stripped_line) >= self.config.min_line_length or not stripped_line:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _final_cleanup(self, text: str) -> str:
        """Final cleanup of processed text."""
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Ensure text doesn't end with incomplete sentences
        if text and not text[-1] in '.!?':
            # Don't add punctuation, just leave as is
            pass
        
        return text


class StructurePreserver:
    """Utility to preserve document structure information during preprocessing."""
    
    @staticmethod
    def extract_structure_markers(content: str) -> Dict[str, List[Dict[str, Any]]]:
        """Extract structure markers from content."""
        markers = {
            "headings": [],
            "lists": [],
            "tables": [],
            "code_blocks": [],
            "quotes": []
        }
        
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Detect headings (markdown style)
            if line_stripped.startswith('#'):
                level = len(line_stripped) - len(line_stripped.lstrip('#'))
                title = line_stripped.lstrip('#').strip()
                markers["headings"].append({
                    "line": i,
                    "level": level,
                    "title": title,
                    "position": content.find(line)
                })
            
            # Detect lists
            elif re.match(r'^\s*[-*+]\s+', line) or re.match(r'^\s*\d+\.\s+', line):
                markers["lists"].append({
                    "line": i,
                    "type": "ordered" if re.match(r'^\s*\d+\.\s+', line) else "unordered",
                    "content": line_stripped,
                    "position": content.find(line)
                })
            
            # Detect table rows (simple detection)
            elif '|' in line_stripped and line_stripped.count('|') >= 2:
                markers["tables"].append({
                    "line": i,
                    "content": line_stripped,
                    "position": content.find(line)
                })
            
            # Detect code blocks
            elif line_stripped.startswith('```'):
                markers["code_blocks"].append({
                    "line": i,
                    "type": "fence",
                    "position": content.find(line)
                })
            
            # Detect quotes
            elif line_stripped.startswith('>'):
                markers["quotes"].append({
                    "line": i,
                    "content": line_stripped.lstrip('>').strip(),
                    "position": content.find(line)
                })
        
        return markers
    
    @staticmethod
    def create_structure_metadata(content: str, structure_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create metadata about document structure."""
        markers = StructurePreserver.extract_structure_markers(content)
        
        metadata = {
            "structure_markers": markers,
            "has_headings": len(markers["headings"]) > 0,
            "has_lists": len(markers["lists"]) > 0,
            "has_tables": len(markers["tables"]) > 0,
            "has_code": len(markers["code_blocks"]) > 0,
            "has_quotes": len(markers["quotes"]) > 0,
            "paragraph_count": len([p for p in content.split('\n\n') if p.strip()]),
            "line_count": len(content.split('\n'))
        }
        
        # Merge with existing structure info if provided
        if structure_info:
            metadata["original_structure"] = structure_info
        
        return metadata


def preprocess_document_content(
    content: str, 
    metadata: Dict[str, Any] = None,
    config: Optional[PreprocessingConfig] = None
) -> Dict[str, Any]:
    """
    Main function to preprocess document content.
    
    Args:
        content: Raw document content
        metadata: Document metadata
        config: Preprocessing configuration
        
    Returns:
        Dictionary with processed content and metadata
    """
    preprocessor = TextPreprocessor(config)
    structure_preserver = StructurePreserver()
    
    # Extract structure information before preprocessing
    structure_metadata = structure_preserver.create_structure_metadata(content, metadata)
    
    # Preprocess the content
    preprocessing_result = preprocessor.preprocess(content, metadata)
    
    # Combine results
    return {
        "processed_content": preprocessing_result["processed_content"],
        "original_content": content,
        "preprocessing_stats": preprocessing_result["preprocessing_stats"],
        "structure_metadata": structure_metadata,
        "original_metadata": metadata or {}
    }