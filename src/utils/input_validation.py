#!/usr/bin/env python3
"""
Input validation and size limits for security (OWASP A04).

Validates input sizes, formats, and prevents resource exhaustion attacks.
"""
import os
from pathlib import Path
from typing import Tuple

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Security limits
MAX_REQUIREMENT_LENGTH = 10000  # characters
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_REQUIREMENTS_PER_SESSION = 1000
MAX_TEST_CASES_PER_REQUIREMENT = 100
MIN_REQUIREMENT_LENGTH = 10  # characters


def validate_requirement_length(text: str) -> Tuple[bool, str]:
    """
    Validate requirement text length.
    
    Args:
        text: Requirement text to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Requirement text must be a non-empty string"
    
    text_length = len(text)
    
    if text_length < MIN_REQUIREMENT_LENGTH:
        return False, f"Requirement too short: {text_length} < {MIN_REQUIREMENT_LENGTH} characters"
    
    if text_length > MAX_REQUIREMENT_LENGTH:
        logger.warning(f"Requirement exceeds max length: {text_length} > {MAX_REQUIREMENT_LENGTH}")
        return False, f"Requirement too long: {text_length} > {MAX_REQUIREMENT_LENGTH} characters"
    
    return True, ""


def validate_file_size(file_path: Path) -> Tuple[bool, str]:
    """
    Validate file size before reading.
    
    Args:
        file_path: Path to file to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path.exists():
        return False, f"File not found: {file_path}"
    
    if not file_path.is_file():
        return False, f"Not a file: {file_path}"
    
    file_size = file_path.stat().st_size
    
    if file_size > MAX_FILE_SIZE:
        logger.warning(f"File too large: {file_size} bytes > {MAX_FILE_SIZE} bytes")
        return False, f"File too large: {file_size / 1024 / 1024:.2f}MB > {MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
    
    if file_size == 0:
        return False, "File is empty"
    
    return True, ""


def validate_requirements_count(count: int) -> Tuple[bool, str]:
    """
    Validate number of requirements per session.
    
    Args:
        count: Number of requirements
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if count < 1:
        return False, "At least one requirement is required"
    
    if count > MAX_REQUIREMENTS_PER_SESSION:
        logger.warning(f"Too many requirements: {count} > {MAX_REQUIREMENTS_PER_SESSION}")
        return False, f"Too many requirements: {count} > {MAX_REQUIREMENTS_PER_SESSION}"
    
    return True, ""


def validate_test_cases_count(count: int) -> Tuple[bool, str]:
    """
    Validate number of test cases per requirement.
    
    Args:
        count: Number of test cases
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if count < 0:
        return False, "Test cases count cannot be negative"
    
    if count > MAX_TEST_CASES_PER_REQUIREMENT:
        logger.warning(f"Too many test cases: {count} > {MAX_TEST_CASES_PER_REQUIREMENT}")
        return False, f"Too many test cases per requirement: {count} > {MAX_TEST_CASES_PER_REQUIREMENT}"
    
    return True, ""


def validate_file_path(path: str, allow_absolute: bool = False) -> Tuple[bool, str]:
    """
    Validate file path to prevent path traversal attacks (OWASP A04).
    
    Args:
        path: File path to validate
        allow_absolute: Whether to allow absolute paths
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"
    
    try:
        file_path = Path(path)
        
        # Check for path traversal patterns
        path_str = str(file_path)
        if ".." in path_str:
            logger.warning(f"Path traversal attempt detected: {path}")
            return False, "Path traversal patterns not allowed (..)"
        
        # Resolve to absolute path
        if not allow_absolute and file_path.is_absolute():
            logger.warning(f"Absolute path not allowed: {path}")
            return False, "Absolute paths not allowed"
        
        # Check if path stays within project directory
        real_path = file_path.resolve()
        project_root = Path.cwd().resolve()
        
        try:
            real_path.relative_to(project_root)
        except ValueError:
            logger.warning(f"Path outside project directory: {path}")
            return False, "Path must be within project directory"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return False, f"Invalid path: {str(e)}"


def validate_confluence_page_id(page_id: str) -> Tuple[bool, str]:
    """
    Validate Confluence page ID format.
    
    Args:
        page_id: Confluence page ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not page_id or not isinstance(page_id, str):
        return False, "Page ID must be a non-empty string"
    
    # Page IDs should be numeric
    if not page_id.isdigit():
        return False, "Page ID must be numeric"
    
    # Reasonable length check (Confluence IDs are typically 8-12 digits)
    if len(page_id) < 5 or len(page_id) > 15:
        return False, f"Page ID length invalid: {len(page_id)} (expected 5-15 digits)"
    
    return True, ""


def validate_export_filename(filename: str) -> Tuple[bool, str]:
    """
    Validate export filename for safety.
    
    Args:
        filename: Filename to validate (without extension)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filename:
        return False, "Filename cannot be empty"
    
    # Check for dangerous characters
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
    for char in dangerous_chars:
        if char in filename:
            return False, f"Filename contains dangerous character: {char}"
    
    # Check length
    if len(filename) > 200:
        return False, f"Filename too long: {len(filename)} > 200"
    
    # Check for hidden files
    if filename.startswith('.'):
        return False, "Hidden filenames not allowed"
    
    return True, ""


# Export all validation functions
__all__ = [
    'validate_requirement_length',
    'validate_file_size',
    'validate_requirements_count',
    'validate_test_cases_count',
    'validate_file_path',
    'validate_confluence_page_id',
    'validate_export_filename',
    'MAX_REQUIREMENT_LENGTH',
    'MAX_FILE_SIZE',
    'MAX_REQUIREMENTS_PER_SESSION',
    'MAX_TEST_CASES_PER_REQUIREMENT',
]
