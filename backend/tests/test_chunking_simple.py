"""
Simple tests for document chunking functionality without database dependencies.
"""
import pytest
from app.processing.chunking import (
    SemanticChunker, 
    ChunkingConfig, 
    ChunkingStrategy,
    create_semantic_chunks
)


class TestSemanticChunker:
    """Test semantic chunking functionality."""
    
    def test_chunking_config_defaults(self):
        """Test default chunking configuration."""
        config = ChunkingConfig()
        assert config.strategy == ChunkingStrategy.HYBRID
        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.preserve_sentences is True
        assert config.preserve_paragraphs is True
    
    def test_fixed_size_chunking(self):
        """Test fixed size chunking strategy."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=100,
            chunk_overlap=20
        )
        chunker = SemanticChunker(config)
        
        content = "This is a test document. " * 20  # ~500 characters
        chunks = chunker.chunk_document(content)
        
        assert len(chunks) > 0
        assert all(len(chunk["content"]) <= 120 for chunk in chunks)  # Allow some overlap
        assert all("chunk_index" in chunk["metadata"] for chunk in chunks)
    
    def test_semantic_chunking_with_paragraphs(self):
        """Test semantic chunking with paragraph structure."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.SEMANTIC,
            chunk_size=200,
            max_chunk_size=400
        )
        chunker = SemanticChunker(config)
        
        content = """This is the first paragraph. It contains some important information.

This is the second paragraph. It has different content and should be preserved.

This is the third paragraph. It continues the document structure."""
        
        chunks = chunker.chunk_document(content)
        
        assert len(chunks) > 0
        # Check that paragraph structure is somewhat preserved
        assert any("\n\n" in chunk["content"] for chunk in chunks)
    
    def test_structure_aware_chunking(self):
        """Test structure-aware chunking with headings."""
        config = ChunkingConfig(strategy=ChunkingStrategy.STRUCTURE_AWARE)
        chunker = SemanticChunker(config)
        
        content = """# Introduction
This is the introduction section.

## Background
This section provides background information.

### Details
More detailed information here.

# Conclusion
This is the conclusion."""
        
        structure_metadata = {
            "has_headings": True,
            "structure_markers": {
                "headings": [
                    {"line": 0, "level": 1, "title": "Introduction", "position": 0},
                    {"line": 2, "level": 2, "title": "Background", "position": 50},
                    {"line": 4, "level": 3, "title": "Details", "position": 100},
                    {"line": 6, "level": 1, "title": "Conclusion", "position": 150}
                ]
            }
        }
        
        chunks = chunker.chunk_document(content, structure_metadata)
        
        assert len(chunks) > 0
        # Check that some chunks contain headings
        assert any("#" in chunk["content"] for chunk in chunks)
    
    def test_empty_content_handling(self):
        """Test handling of empty content."""
        chunker = SemanticChunker()
        
        chunks = chunker.chunk_document("")
        assert chunks == []
        
        chunks = chunker.chunk_document("   \n\n   ")
        assert chunks == []
    
    def test_create_semantic_chunks_function(self):
        """Test the convenience function for creating semantic chunks."""
        content = "This is a test document with multiple sentences. Each sentence should be preserved properly."
        
        chunks = create_semantic_chunks(content)
        
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)
    
    def test_chunk_metadata_structure(self):
        """Test that chunk metadata has the expected structure."""
        content = "This is a test document for checking metadata structure."
        
        chunks = create_semantic_chunks(content)
        
        assert len(chunks) > 0
        
        for chunk in chunks:
            metadata = chunk["metadata"]
            
            # Check required metadata fields
            assert "chunk_index" in metadata
            assert "start_position" in metadata
            assert "end_position" in metadata
            assert "character_count" in metadata
            assert "word_count" in metadata
            assert "chunking_strategy" in metadata
            
            # Check data types
            assert isinstance(metadata["chunk_index"], int)
            assert isinstance(metadata["start_position"], int)
            assert isinstance(metadata["end_position"], int)
            assert isinstance(metadata["character_count"], int)
            assert isinstance(metadata["word_count"], int)
            assert isinstance(metadata["chunking_strategy"], str)
    
    def test_chunk_content_preservation(self):
        """Test that chunk content is properly preserved."""
        content = """First paragraph with important information.

Second paragraph with different content.

Third paragraph with more details."""
        
        chunks = create_semantic_chunks(content)
        
        # Reconstruct content from chunks (without overlap)
        reconstructed_parts = []
        for chunk in chunks:
            chunk_content = chunk["content"].strip()
            if chunk_content and chunk_content not in reconstructed_parts:
                reconstructed_parts.append(chunk_content)
        
        # Check that important parts are preserved
        reconstructed = " ".join(reconstructed_parts)
        assert "First paragraph" in reconstructed
        assert "Second paragraph" in reconstructed
        assert "Third paragraph" in reconstructed


if __name__ == "__main__":
    pytest.main([__file__])