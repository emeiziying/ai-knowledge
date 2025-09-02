"""
Utility functions for document management.
"""
import os
import uuid
import hashlib
import mimetypes
from typing import Optional, Tuple, List
from fastapi import UploadFile, HTTPException
from ..config import get_settings

settings = get_settings()


def validate_file_type(file: UploadFile) -> bool:
    """
    Validate if the uploaded file type is allowed.
    
    Args:
        file: FastAPI UploadFile object
        
    Returns:
        True if file type is allowed, False otherwise
    """
    if file.content_type not in settings.allowed_file_types:
        return False
    
    # Additional validation based on file extension
    if file.filename:
        _, ext = os.path.splitext(file.filename.lower())
        allowed_extensions = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.md': 'text/markdown'
        }
        
        if ext in allowed_extensions:
            expected_mime = allowed_extensions[ext]
            return file.content_type == expected_mime or file.content_type == 'application/octet-stream'
    
    return True


def validate_file_size(file: UploadFile) -> bool:
    """
    Validate if the uploaded file size is within limits.
    
    Args:
        file: FastAPI UploadFile object
        
    Returns:
        True if file size is acceptable, False otherwise
    """
    if hasattr(file, 'size') and file.size:
        return file.size <= settings.max_file_size
    return True


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a unique filename for storage.
    
    Args:
        original_filename: Original filename from upload
        
    Returns:
        Unique filename string
    """
    # Extract file extension
    _, ext = os.path.splitext(original_filename)
    
    # Generate unique identifier
    unique_id = str(uuid.uuid4())
    
    # Combine with extension
    return f"{unique_id}{ext}"


def get_file_hash(file_content: bytes) -> str:
    """
    Generate SHA-256 hash of file content.
    
    Args:
        file_content: File content as bytes
        
    Returns:
        SHA-256 hash string
    """
    return hashlib.sha256(file_content).hexdigest()


def detect_mime_type(filename: str, file_content: bytes) -> str:
    """
    Detect MIME type of file based on filename and content.
    
    Args:
        filename: Original filename
        file_content: File content as bytes
        
    Returns:
        MIME type string
    """
    # First try to detect from filename
    mime_type, _ = mimetypes.guess_type(filename)
    
    if mime_type:
        return mime_type
    
    # Fallback to content-based detection for common types
    if file_content.startswith(b'%PDF'):
        return 'application/pdf'
    elif file_content.startswith(b'PK\x03\x04'):
        # Could be DOCX or other ZIP-based format
        if filename.lower().endswith('.docx'):
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif file_content.startswith(b'\xd0\xcf\x11\xe0'):
        # Old Microsoft Office format
        return 'application/msword'
    
    # Default to plain text for unknown types
    return 'text/plain'


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing or replacing unsafe characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path separators and other unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    
    for char in unsafe_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        max_name_length = 255 - len(ext)
        sanitized = name[:max_name_length] + ext
    
    return sanitized


def validate_file_security(file_content: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """
    Perform basic security validation on uploaded file.
    
    Args:
        file_content: File content as bytes
        filename: Original filename
        
    Returns:
        Tuple of (is_safe, error_message)
    """
    # Check for executable file extensions
    dangerous_extensions = [
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
        '.jar', '.sh', '.ps1', '.php', '.asp', '.jsp'
    ]
    
    _, ext = os.path.splitext(filename.lower())
    if ext in dangerous_extensions:
        return False, f"File type {ext} is not allowed for security reasons"
    
    # Check for suspicious content patterns
    suspicious_patterns = [
        b'<script',
        b'javascript:',
        b'vbscript:',
        b'onload=',
        b'onerror=',
        b'<?php',
        b'<%',
        b'#!/bin/sh',
        b'#!/bin/bash'
    ]
    
    content_lower = file_content[:1024].lower()  # Check first 1KB
    for pattern in suspicious_patterns:
        if pattern in content_lower:
            return False, "File contains potentially malicious content"
    
    return True, None


def get_file_info(file_content: bytes, filename: str) -> dict:
    """
    Extract comprehensive file information.
    
    Args:
        file_content: File content as bytes
        filename: Original filename
        
    Returns:
        Dictionary with file information
    """
    return {
        'size': len(file_content),
        'hash': get_file_hash(file_content),
        'mime_type': detect_mime_type(filename, file_content),
        'extension': os.path.splitext(filename)[1].lower(),
        'sanitized_name': sanitize_filename(filename)
    }


class FileValidator:
    """File validation class with comprehensive checks."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def validate_upload(self, file: UploadFile) -> Tuple[bool, Optional[str]]:
        """
        Perform comprehensive validation on uploaded file.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if file is provided
        if not file or not file.filename:
            return False, "No file provided"
        
        # Read file content
        try:
            file_content = await file.read()
            await file.seek(0)  # Reset file pointer
        except Exception as e:
            return False, f"Failed to read file: {str(e)}"
        
        # Check file size
        if len(file_content) > self.settings.max_file_size:
            return False, f"File size exceeds maximum allowed size of {self.settings.max_file_size} bytes"
        
        if len(file_content) == 0:
            return False, "File is empty"
        
        # Validate file type
        if not validate_file_type(file):
            return False, f"File type {file.content_type} is not allowed"
        
        # Security validation
        is_safe, security_error = validate_file_security(file_content, file.filename)
        if not is_safe:
            return False, security_error
        
        return True, None