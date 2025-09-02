# Document processing module

# Import core components that don't require database
from .parsers import DocumentParserFactory
from .preprocessor import TextPreprocessor, PreprocessingConfig, preprocess_document_content

# Processor components are imported on demand to avoid database dependency issues
def get_processor():
    """Get processor instance (imports on demand)."""
    from .processor import DocumentProcessor
    return DocumentProcessor

def get_processing_status():
    """Get processing status enum (imports on demand)."""
    from .processor import ProcessingStatus
    return ProcessingStatus

def get_processing_error():
    """Get processing error class (imports on demand)."""
    from .processor import ProcessingError
    return ProcessingError

def get_supported_formats():
    """Get supported formats (imports on demand)."""
    from .processor import get_supported_formats as _get_supported_formats
    return _get_supported_formats()

__all__ = [
    "DocumentParserFactory",
    "TextPreprocessor",
    "PreprocessingConfig",
    "preprocess_document_content",
    "get_processor",
    "get_processing_status",
    "get_processing_error",
    "get_supported_formats"
]