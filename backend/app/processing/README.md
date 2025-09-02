# Document Processing Module

This module provides comprehensive document processing capabilities for the AI Knowledge Base application. It handles parsing, preprocessing, and chunking of various document formats to prepare them for AI-powered search and question answering.

## Features

### Supported Document Formats

- **PDF Documents** (.pdf)
  - Text extraction from all pages
  - Metadata extraction (title, author, creation date, etc.)
  - Page-by-page content structure preservation

- **Microsoft Word Documents** (.docx, .doc)
  - Text extraction from paragraphs and tables
  - Document metadata (title, author, creation date, etc.)
  - Structure preservation (headings, tables, lists)

- **Plain Text Files** (.txt)
  - Multi-encoding support (UTF-8, UTF-16, Latin-1, CP1252)
  - Basic structure analysis
  - Character and word count statistics

- **Markdown Documents** (.md, .markdown)
  - Full markdown parsing with structure preservation
  - Heading extraction and table of contents generation
  - Code block and table detection
  - HTML conversion support

### Processing Pipeline

1. **Document Parsing**
   - Automatic format detection
   - Content extraction with metadata
   - Structure information preservation

2. **Text Preprocessing**
   - Unicode normalization
   - Whitespace cleanup
   - Optional text transformations (lowercase, special character removal)
   - Structure marker preservation

3. **Content Chunking**
   - Intelligent text segmentation
   - Sentence boundary detection
   - Configurable chunk size and overlap
   - Structure-aware chunking

4. **Status Tracking**
   - Real-time processing status updates
   - Error handling and reporting
   - Processing metadata storage

## Architecture

### Core Components

#### DocumentParserFactory
Central factory for creating appropriate parsers based on file type.

```python
from app.processing.parsers import DocumentParserFactory

factory = DocumentParserFactory()
parser = factory.get_parser("application/pdf", "document.pdf")
result = parser.parse(file_content, "document.pdf")
```

#### TextPreprocessor
Handles text cleaning and normalization.

```python
from app.processing.preprocessor import TextPreprocessor, PreprocessingConfig

config = PreprocessingConfig(
    remove_extra_whitespace=True,
    normalize_unicode=True,
    preserve_structure=True
)

preprocessor = TextPreprocessor(config)
result = preprocessor.preprocess(content, metadata)
```

#### DocumentProcessor
Main orchestrator for the complete processing pipeline.

```python
from app.processing.processor import DocumentProcessor

processor = DocumentProcessor(db_session)
result = processor.process_document(
    document_id="uuid",
    file_content=bytes_content,
    filename="document.pdf",
    mime_type="application/pdf"
)
```

### Processing Status Flow

```
uploaded → pending → processing → parsing → preprocessing → chunking → completed
                                     ↓
                                  failed (on any error)
```

### Database Integration

The module integrates with the existing database schema:

- **documents** table: Stores document metadata and processing status
- **document_chunks** table: Stores processed text chunks with metadata
- Processing metadata and errors are stored in the document record

## API Endpoints

### GET /api/v1/processing/formats
Get list of supported document formats.

### POST /api/v1/processing/parse
Parse document content without storing (for testing/preview).

### POST /api/v1/processing/documents/{id}/process
Process an uploaded document.

### POST /api/v1/processing/documents/{id}/reprocess
Reprocess an existing document.

### GET /api/v1/processing/documents/{id}/status
Get processing status for a document.

### GET /api/v1/processing/documents/{id}/chunks
Get processed chunks for a document.

### GET /api/v1/processing/health
Health check for processing service.

## Configuration

### Preprocessing Configuration

```python
from app.processing.preprocessor import PreprocessingConfig

config = PreprocessingConfig(
    remove_extra_whitespace=True,    # Remove extra spaces and newlines
    normalize_unicode=True,          # Normalize unicode characters
    remove_special_chars=False,      # Keep special characters
    min_line_length=3,              # Filter out very short lines
    preserve_structure=True,         # Keep document structure info
    remove_urls=False,              # Keep URLs in text
    remove_emails=False,            # Keep email addresses
    lowercase=False                 # Don't convert to lowercase
)
```

### Chunking Configuration

```python
# In DocumentProcessor._create_basic_chunks()
chunk_size = 1000        # Maximum characters per chunk
chunk_overlap = 200      # Overlap between chunks
```

## Error Handling

The module provides comprehensive error handling:

### ProcessingError Exception
Custom exception for processing-related errors with error codes and details.

### Status Tracking
- Processing status is updated in real-time
- Errors are logged and stored in the database
- Failed documents can be reprocessed

### Retry Mechanisms
- Automatic retry for transient failures
- Manual reprocessing capability
- Graceful degradation for unsupported formats

## Testing

### Unit Tests
Located in `backend/tests/test_document_processing.py`:

- Parser functionality tests
- Preprocessing tests
- Structure preservation tests
- Error handling tests

### Running Tests
```bash
cd backend
python -m pytest tests/test_document_processing.py -v
```

### Integration Testing
The module includes integration with the document management system and can be tested through the API endpoints.

## Performance Considerations

### Memory Usage
- Streaming file processing where possible
- Chunked processing for large documents
- Garbage collection after processing

### Processing Time
- Asynchronous processing support
- Status tracking for long-running operations
- Configurable timeouts

### Scalability
- Stateless processing design
- Database session management
- Support for distributed processing (future)

## Future Enhancements

### Planned Features
1. **Advanced Chunking**
   - Semantic chunking based on content
   - Custom chunking strategies per document type
   - Hierarchical chunking for structured documents

2. **Additional Formats**
   - PowerPoint presentations (.pptx)
   - Excel spreadsheets (.xlsx)
   - HTML documents
   - RTF documents

3. **Processing Optimization**
   - Parallel processing for large documents
   - Caching for repeated processing
   - Background job queue integration

4. **Enhanced Metadata**
   - Language detection
   - Content classification
   - Quality scoring

### Extension Points
The module is designed for extensibility:

- New parsers can be added by implementing the `DocumentParser` interface
- Preprocessing steps can be customized through configuration
- Chunking strategies can be replaced or extended
- Status tracking can be enhanced with additional states

## Dependencies

### Required Packages
- `PyPDF2`: PDF document parsing
- `python-docx`: Word document parsing
- `markdown`: Markdown parsing and conversion
- `sqlalchemy`: Database integration
- `fastapi`: API endpoints

### Optional Dependencies
- `pypdf`: Alternative PDF parser (recommended upgrade from PyPDF2)
- `pdfplumber`: Enhanced PDF parsing with table support
- `textract`: Universal document parsing (system dependencies required)

## Troubleshooting

### Common Issues

1. **Unsupported File Format**
   - Check supported formats with `/api/v1/processing/formats`
   - Verify MIME type detection
   - Consider format conversion

2. **Processing Failures**
   - Check document corruption
   - Verify file permissions
   - Review processing logs

3. **Memory Issues**
   - Reduce chunk size for large documents
   - Implement streaming processing
   - Monitor system resources

4. **Database Errors**
   - Verify database connectivity
   - Check transaction handling
   - Review migration status

### Debugging

Enable debug logging:
```python
import logging
logging.getLogger('app.processing').setLevel(logging.DEBUG)
```

Check processing status:
```bash
curl -X GET "http://localhost:8000/api/v1/processing/documents/{id}/status"
```

## Contributing

When adding new features:

1. Implement appropriate tests
2. Update documentation
3. Follow existing code patterns
4. Consider backward compatibility
5. Update API documentation

### Adding New Parsers

1. Create parser class inheriting from `DocumentParser`
2. Implement `supports_format()` and `parse()` methods
3. Add to `DocumentParserFactory.parsers` list
4. Add tests for the new parser
5. Update supported formats documentation