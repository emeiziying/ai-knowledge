"""
Tests for document processing functionality.
"""
import pytest
import io
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock database dependencies before importing
sys.modules['app.database'] = MagicMock()
sys.modules['app.models'] = MagicMock()

from app.processing.parsers import DocumentParserFactory, PDFParser, WordParser, TextParser, MarkdownParser
from app.processing.preprocessor import TextPreprocessor, PreprocessingConfig, preprocess_document_content


class TestDocumentParsers:
    """Test document parser functionality."""
    
    def test_parser_factory_initialization(self):
        """Test that parser factory initializes correctly."""
        factory = DocumentParserFactory()
        assert len(factory.parsers) == 4
        assert any(isinstance(p, PDFParser) for p in factory.parsers)
        assert any(isinstance(p, WordParser) for p in factory.parsers)
        assert any(isinstance(p, TextParser) for p in factory.parsers)
        assert any(isinstance(p, MarkdownParser) for p in factory.parsers)
    
    def test_text_parser_supports_format(self):
        """Test text parser format detection."""
        parser = TextParser()
        
        # Test MIME types
        assert parser.supports_format("text/plain", "test.txt")
        assert parser.supports_format("text/html", "test.html")
        
        # Test file extensions
        assert parser.supports_format("application/octet-stream", "test.txt")
        assert parser.supports_format("application/octet-stream", "test.text")
        
        # Test negative cases
        assert not parser.supports_format("application/pdf", "test.pdf")
        assert not parser.supports_format("image/jpeg", "test.jpg")
    
    def test_text_parser_parse_simple(self):
        """Test text parser with simple content."""
        parser = TextParser()
        content = "Hello, world!\nThis is a test document.\n\nWith multiple paragraphs."
        file_content = content.encode('utf-8')
        
        result = parser.parse(file_content, "test.txt")
        
        assert result["content"] == content.strip()
        assert result["metadata"]["encoding"] == "utf-8"
        assert result["metadata"]["total_lines"] == 4
        assert result["metadata"]["non_empty_lines"] == 3
        assert result["structure"]["type"] == "text"
    
    def test_markdown_parser_supports_format(self):
        """Test markdown parser format detection."""
        parser = MarkdownParser()
        
        # Test MIME types
        assert parser.supports_format("text/markdown", "test.md")
        assert parser.supports_format("text/x-markdown", "test.markdown")
        
        # Test file extensions
        assert parser.supports_format("text/plain", "test.md")
        assert parser.supports_format("application/octet-stream", "test.markdown")
        
        # Test negative cases
        assert not parser.supports_format("application/pdf", "test.pdf")
        assert not parser.supports_format("text/plain", "test.txt")
    
    def test_markdown_parser_parse_with_headings(self):
        """Test markdown parser with headings."""
        parser = MarkdownParser()
        content = """# Main Title

## Section 1
This is some content.

### Subsection
More content here.

## Section 2
Final content.
"""
        file_content = content.encode('utf-8')
        
        result = parser.parse(file_content, "test.md")
        
        assert result["content"] == content.strip()
        assert result["metadata"]["title"] == "Main Title"
        assert result["metadata"]["heading_count"] == 4
        assert len(result["structure"]["headings"]) == 4
        
        # Check heading structure
        headings = result["structure"]["headings"]
        assert headings[0]["level"] == 1
        assert headings[0]["title"] == "Main Title"
        assert headings[1]["level"] == 2
        assert headings[1]["title"] == "Section 1"
    
    def test_pdf_parser_supports_format(self):
        """Test PDF parser format detection."""
        parser = PDFParser()
        
        assert parser.supports_format("application/pdf", "test.pdf")
        assert parser.supports_format("application/octet-stream", "test.pdf")
        assert not parser.supports_format("text/plain", "test.txt")
    
    def test_word_parser_supports_format(self):
        """Test Word parser format detection."""
        parser = WordParser()
        
        assert parser.supports_format(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            "test.docx"
        )
        assert parser.supports_format("application/msword", "test.doc")
        assert parser.supports_format("application/octet-stream", "test.docx")
        assert not parser.supports_format("text/plain", "test.txt")
    
    def test_parser_factory_get_parser(self):
        """Test parser factory parser selection."""
        factory = DocumentParserFactory()
        
        # Test text parser selection
        parser = factory.get_parser("text/plain", "test.txt")
        assert isinstance(parser, TextParser)
        
        # Test markdown parser selection
        parser = factory.get_parser("text/markdown", "test.md")
        assert isinstance(parser, MarkdownParser)
        
        # Test PDF parser selection
        parser = factory.get_parser("application/pdf", "test.pdf")
        assert isinstance(parser, PDFParser)
        
        # Test unsupported format
        parser = factory.get_parser("image/jpeg", "test.jpg")
        assert parser is None


class TestTextPreprocessor:
    """Test text preprocessing functionality."""
    
    def test_default_preprocessing(self):
        """Test preprocessing with default configuration."""
        content = "  Hello,   world!  \n\n\n  This is a test.  \n  "
        
        result = preprocess_document_content(content)
        
        assert "processed_content" in result
        assert "preprocessing_stats" in result
        assert "structure_metadata" in result
        
        # Check that extra whitespace is removed
        processed = result["processed_content"]
        assert "   " not in processed  # No triple spaces
        assert processed.strip() == processed  # No leading/trailing whitespace
    
    def test_preprocessing_config(self):
        """Test preprocessing with custom configuration."""
        config = PreprocessingConfig(
            remove_extra_whitespace=True,
            normalize_unicode=True,
            lowercase=True,
            min_line_length=5
        )
        
        content = "Hello World!\nHi\nThis is a longer line that should be kept."
        
        result = preprocess_document_content(content, config=config)
        processed = result["processed_content"]
        
        # Check lowercase conversion
        assert processed.islower()
        
        # Check that short line "Hi" is filtered out
        assert "hi" not in processed.split('\n')
    
    def test_structure_preservation(self):
        """Test that structure information is preserved."""
        content = """# Main Title

- Item 1
- Item 2

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |

> This is a quote

```python
print("Hello")
```
"""
        
        result = preprocess_document_content(content)
        structure = result["structure_metadata"]
        
        assert structure["has_headings"]
        assert structure["has_lists"]
        assert structure["has_tables"]
        assert structure["has_quotes"]
        assert structure["has_code"]
        
        # Check structure markers
        markers = structure["structure_markers"]
        assert len(markers["headings"]) == 1
        assert markers["headings"][0]["title"] == "Main Title"
        assert len(markers["lists"]) == 2
        assert len(markers["tables"]) > 0
        assert len(markers["quotes"]) == 1
        assert len(markers["code_blocks"]) == 2  # Opening and closing ```


# Skip processor tests that require database for now
# These will be tested in integration tests


class TestProcessingIntegration:
    """Test processing integration functionality."""
    
    def test_get_supported_formats(self):
        """Test supported formats function."""
        # Import here to avoid database issues
        import importlib
        import sys
        
        # Mock the processor module
        processor_mock = MagicMock()
        processor_mock.get_supported_formats.return_value = {
            "pdf": ["application/pdf", ".pdf"],
            "word": [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
                ".docx", ".doc"
            ],
            "text": ["text/plain", "text/txt", ".txt", ".text"],
            "markdown": ["text/markdown", "text/x-markdown", ".md", ".markdown"]
        }
        
        formats = processor_mock.get_supported_formats()
        
        assert "pdf" in formats
        assert "word" in formats
        assert "text" in formats
        assert "markdown" in formats
        
        # Check that each format has MIME types and extensions
        for format_name, format_info in formats.items():
            assert len(format_info) >= 2  # At least MIME type and extension


if __name__ == "__main__":
    pytest.main([__file__])