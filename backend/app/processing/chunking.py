"""
智能文档分块算法，保持语义完整性。
Intelligent document chunking algorithms that preserve semantic integrity.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkingStrategy(Enum):
    """文档分块策略枚举"""
    FIXED_SIZE = "fixed_size"  # 固定大小分块
    SEMANTIC = "semantic"      # 语义分块
    STRUCTURE_AWARE = "structure_aware"  # 结构感知分块
    HYBRID = "hybrid"          # 混合策略


@dataclass
class ChunkingConfig:
    """分块配置参数"""
    strategy: ChunkingStrategy = ChunkingStrategy.HYBRID
    chunk_size: int = 1000  # 目标分块大小（字符数）
    chunk_overlap: int = 200  # 分块重叠大小
    min_chunk_size: int = 100  # 最小分块大小
    max_chunk_size: int = 2000  # 最大分块大小
    preserve_sentences: bool = True  # 保持句子完整性
    preserve_paragraphs: bool = True  # 保持段落完整性
    respect_structure: bool = True  # 尊重文档结构
    sentence_splitters: List[str] = None  # 句子分隔符
    
    def __post_init__(self):
        if self.sentence_splitters is None:
            self.sentence_splitters = ['.', '!', '?', '。', '！', '？']


class SemanticChunker:
    """语义感知的文档分块器"""
    
    def __init__(self, config: ChunkingConfig = None):
        self.config = config or ChunkingConfig()
        
    def chunk_document(
        self, 
        content: str, 
        structure_metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        对文档进行智能分块
        
        Args:
            content: 文档内容
            structure_metadata: 文档结构元数据
            
        Returns:
            分块结果列表
        """
        if not content.strip():
            return []
        
        # 根据策略选择分块方法
        if self.config.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._fixed_size_chunking(content)
        elif self.config.strategy == ChunkingStrategy.SEMANTIC:
            return self._semantic_chunking(content)
        elif self.config.strategy == ChunkingStrategy.STRUCTURE_AWARE:
            return self._structure_aware_chunking(content, structure_metadata)
        else:  # HYBRID
            return self._hybrid_chunking(content, structure_metadata)
    
    def _fixed_size_chunking(self, content: str) -> List[Dict[str, Any]]:
        """固定大小分块"""
        chunks = []
        content_length = len(content)
        start = 0
        chunk_index = 0
        
        while start < content_length:
            end = min(start + self.config.chunk_size, content_length)
            
            # 尝试在句子边界处分割
            if self.config.preserve_sentences and end < content_length:
                end = self._find_sentence_boundary(content, start, end)
            
            chunk_content = content[start:end].strip()
            
            if chunk_content:  # Only check if content exists
                if len(chunk_content) >= self.config.min_chunk_size or not chunks:
                    # Create chunk if it meets min size OR if no chunks created yet
                    chunk_metadata = self._create_chunk_metadata(
                        chunk_index, start, end, chunk_content
                    )
                    
                    chunks.append({
                        "content": chunk_content,
                        "metadata": chunk_metadata
                    })
                    
                    chunk_index += 1
            
            # 计算下一个起始位置（考虑重叠）
            start = max(end - self.config.chunk_overlap, start + 1)
            
            # 防止无限循环
            if start >= end:
                break
        
        logger.info(f"Fixed size chunking created {len(chunks)} chunks")
        return chunks
    
    def _semantic_chunking(self, content: str) -> List[Dict[str, Any]]:
        """语义感知分块"""
        # 首先按段落分割
        paragraphs = self._split_into_paragraphs(content)
        
        # 如果没有段落，将整个内容作为一个段落处理
        if not paragraphs:
            paragraphs = [{
                "text": content.strip(),
                "start_pos": 0,
                "end_pos": len(content)
            }]
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        start_position = 0
        
        for paragraph in paragraphs:
            paragraph_text = paragraph["text"]
            
            # 检查添加当前段落是否会超过大小限制
            potential_chunk = current_chunk + "\n\n" + paragraph_text if current_chunk else paragraph_text
            
            if len(potential_chunk) <= self.config.max_chunk_size:
                # 可以添加到当前分块
                current_chunk = potential_chunk
            else:
                # 需要创建新的分块
                if current_chunk:
                    # 保存当前分块
                    chunk_metadata = self._create_chunk_metadata(
                        chunk_index, start_position, 
                        start_position + len(current_chunk), current_chunk
                    )
                    chunk_metadata["semantic_info"] = {
                        "paragraph_count": current_chunk.count('\n\n') + 1,
                        "contains_headings": self._contains_headings(current_chunk)
                    }
                    
                    chunks.append({
                        "content": current_chunk,
                        "metadata": chunk_metadata
                    })
                    
                    chunk_index += 1
                    start_position += len(current_chunk)
                
                # 检查单个段落是否过大
                if len(paragraph_text) > self.config.max_chunk_size:
                    # 对大段落进行句子级分割
                    sentence_chunks = self._split_large_paragraph(paragraph_text)
                    for sentence_chunk in sentence_chunks:
                        chunk_metadata = self._create_chunk_metadata(
                            chunk_index, start_position,
                            start_position + len(sentence_chunk), sentence_chunk
                        )
                        
                        chunks.append({
                            "content": sentence_chunk,
                            "metadata": chunk_metadata
                        })
                        
                        chunk_index += 1
                        start_position += len(sentence_chunk)
                    
                    current_chunk = ""
                else:
                    current_chunk = paragraph_text
        
        # 处理最后一个分块
        if current_chunk:
            if len(current_chunk) >= self.config.min_chunk_size:
                chunk_metadata = self._create_chunk_metadata(
                    chunk_index, start_position,
                    start_position + len(current_chunk), current_chunk
                )
                
                chunks.append({
                    "content": current_chunk,
                    "metadata": chunk_metadata
                })
            elif not chunks and current_chunk.strip():
                # If no chunks created yet and we have content, create at least one chunk
                chunk_metadata = self._create_chunk_metadata(
                    chunk_index, start_position,
                    start_position + len(current_chunk), current_chunk
                )
                
                chunks.append({
                    "content": current_chunk,
                    "metadata": chunk_metadata
                })
        
        logger.info(f"Semantic chunking created {len(chunks)} chunks")
        return chunks
    
    def _structure_aware_chunking(
        self, 
        content: str, 
        structure_metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """结构感知分块"""
        if not structure_metadata:
            return self._semantic_chunking(content)
        
        chunks = []
        structure_markers = structure_metadata.get("structure_markers", {})
        headings = structure_markers.get("headings", [])
        
        if not headings:
            return self._semantic_chunking(content)
        
        # 按标题分割内容
        sections = self._split_by_headings(content, headings)
        chunk_index = 0
        
        for section in sections:
            section_content = section["content"]
            section_metadata = section["metadata"]
            
            # 如果章节内容过大，进一步分块
            if len(section_content) > self.config.max_chunk_size:
                sub_chunks = self._semantic_chunking(section_content)
                
                for sub_chunk in sub_chunks:
                    # 合并元数据
                    combined_metadata = {
                        **sub_chunk["metadata"],
                        "section_info": section_metadata,
                        "chunk_index": chunk_index
                    }
                    
                    chunks.append({
                        "content": sub_chunk["content"],
                        "metadata": combined_metadata
                    })
                    
                    chunk_index += 1
            else:
                # 章节内容适中，直接作为一个分块
                chunk_metadata = self._create_chunk_metadata(
                    chunk_index, section["start_pos"], 
                    section["end_pos"], section_content
                )
                chunk_metadata["section_info"] = section_metadata
                
                chunks.append({
                    "content": section_content,
                    "metadata": chunk_metadata
                })
                
                chunk_index += 1
        
        logger.info(f"Structure-aware chunking created {len(chunks)} chunks")
        return chunks
    
    def _hybrid_chunking(
        self, 
        content: str, 
        structure_metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """混合分块策略"""
        # 首先尝试结构感知分块
        if structure_metadata and structure_metadata.get("has_headings"):
            chunks = self._structure_aware_chunking(content, structure_metadata)
            
            # 检查分块质量
            if self._evaluate_chunk_quality(chunks):
                return chunks
        
        # 回退到语义分块
        return self._semantic_chunking(content)
    
    def _split_into_paragraphs(self, content: str) -> List[Dict[str, Any]]:
        """将内容分割为段落"""
        paragraphs = []
        current_pos = 0
        
        # 按双换行符分割段落
        paragraph_texts = re.split(r'\n\s*\n', content)
        
        for paragraph_text in paragraph_texts:
            paragraph_text = paragraph_text.strip()
            if paragraph_text:
                # Find actual position in original content
                actual_pos = content.find(paragraph_text, current_pos)
                if actual_pos == -1:
                    actual_pos = current_pos
                
                paragraphs.append({
                    "text": paragraph_text,
                    "start_pos": actual_pos,
                    "end_pos": actual_pos + len(paragraph_text)
                })
                current_pos = actual_pos + len(paragraph_text)
        
        return paragraphs
    
    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        """分割过大的段落"""
        sentences = self._split_into_sentences(paragraph)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            potential_chunk = current_chunk + " " + sentence if current_chunk else sentence
            
            if len(potential_chunk) <= self.config.chunk_size:
                current_chunk = potential_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割为句子"""
        # 简单的句子分割实现
        sentences = []
        current_sentence = ""
        
        for char in text:
            current_sentence += char
            
            if char in self.config.sentence_splitters:
                # 检查是否是真正的句子结尾
                if self._is_sentence_end(current_sentence):
                    sentences.append(current_sentence.strip())
                    current_sentence = ""
        
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        return sentences
    
    def _is_sentence_end(self, sentence: str) -> bool:
        """判断是否是句子结尾"""
        sentence = sentence.strip()
        if not sentence:
            return False
        
        # 简单的规则：句子长度大于5且以句号等结尾
        return len(sentence) > 5 and sentence[-1] in self.config.sentence_splitters
    
    def _split_by_headings(self, content: str, headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按标题分割内容"""
        sections = []
        content_lines = content.split('\n')
        
        # 按标题位置分割
        for i, heading in enumerate(headings):
            start_line = heading["line"]
            end_line = headings[i + 1]["line"] if i + 1 < len(headings) else len(content_lines)
            
            section_lines = content_lines[start_line:end_line]
            section_content = '\n'.join(section_lines).strip()
            
            if section_content:
                sections.append({
                    "content": section_content,
                    "start_pos": heading["position"],
                    "end_pos": headings[i + 1]["position"] if i + 1 < len(headings) else len(content),
                    "metadata": {
                        "heading": heading["title"],
                        "heading_level": heading["level"],
                        "section_index": i
                    }
                })
        
        return sections
    
    def _find_sentence_boundary(self, content: str, start: int, preferred_end: int) -> int:
        """寻找句子边界"""
        # 在首选结束位置前后寻找句子分隔符
        search_range = min(100, preferred_end - start)
        
        # 向前搜索
        for i in range(preferred_end - 1, max(preferred_end - search_range, start), -1):
            if content[i] in self.config.sentence_splitters:
                # 检查下一个字符是否是空格或换行
                if i + 1 < len(content) and content[i + 1] in ' \n':
                    return i + 1
        
        # 如果没找到合适的句子边界，返回首选位置
        return preferred_end
    
    def _contains_headings(self, text: str) -> bool:
        """检查文本是否包含标题"""
        lines = text.split('\n')
        for line in lines:
            if line.strip().startswith('#'):
                return True
        return False
    
    def _create_chunk_metadata(
        self, 
        chunk_index: int, 
        start_pos: int, 
        end_pos: int, 
        content: str
    ) -> Dict[str, Any]:
        """创建分块元数据"""
        return {
            "chunk_index": chunk_index,
            "start_position": start_pos,
            "end_position": end_pos,
            "character_count": len(content),
            "word_count": len(content.split()),
            "line_count": content.count('\n') + 1,
            "paragraph_count": content.count('\n\n') + 1,
            "chunking_strategy": self.config.strategy.value,
            "has_structure_markers": {
                "has_headings": self._contains_headings(content),
                "has_lists": self._contains_lists(content),
                "has_code": self._contains_code(content),
                "has_tables": self._contains_tables(content)
            }
        }
    
    def _contains_lists(self, text: str) -> bool:
        """检查是否包含列表"""
        return bool(re.search(r'^\s*[-*+]\s+', text, re.MULTILINE) or 
                   re.search(r'^\s*\d+\.\s+', text, re.MULTILINE))
    
    def _contains_code(self, text: str) -> bool:
        """检查是否包含代码"""
        return '```' in text or bool(re.search(r'^    ', text, re.MULTILINE))
    
    def _contains_tables(self, text: str) -> bool:
        """检查是否包含表格"""
        return '|' in text and text.count('|') >= 2
    
    def _evaluate_chunk_quality(self, chunks: List[Dict[str, Any]]) -> bool:
        """评估分块质量"""
        if not chunks:
            return False
        
        # 检查分块大小分布
        sizes = [len(chunk["content"]) for chunk in chunks]
        avg_size = sum(sizes) / len(sizes)
        
        # 检查是否有过小或过大的分块
        too_small = sum(1 for size in sizes if size < self.config.min_chunk_size)
        too_large = sum(1 for size in sizes if size > self.config.max_chunk_size)
        
        # 质量标准：少于20%的分块过小或过大
        quality_ratio = (too_small + too_large) / len(chunks)
        
        return quality_ratio < 0.2 and avg_size >= self.config.min_chunk_size


def create_semantic_chunks(
    content: str,
    structure_metadata: Dict[str, Any] = None,
    config: ChunkingConfig = None
) -> List[Dict[str, Any]]:
    """
    创建语义分块的便捷函数
    
    Args:
        content: 文档内容
        structure_metadata: 文档结构元数据
        config: 分块配置
        
    Returns:
        分块结果列表
    """
    chunker = SemanticChunker(config)
    return chunker.chunk_document(content, structure_metadata)