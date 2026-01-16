#!/usr/bin/env python3
"""
State file integrity protection (OWASP A08).

HMAC signatures and JSON schema validation for state files.
"""
import json
import hmac
import hashlib
import os
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from src.utils.logger import setup_logger
from src.utils.security_logging import SecurityLogger

logger = setup_logger(__name__)

# JSON Schema for state file validation
STATE_SCHEMA = {
    "type": "object",
    "required": ["session_id", "requirements", "progress"],
    "properties": {
        "session_id": {"type": "string"},
        "created_at": {"type": "string"},
        "updated_at": {"type": "string"},
        "llm_provider": {"type": "string"},
        "techniques": {"type": "array", "items": {"type": "string"}},
        "output_format": {"type": "string"},
        "output_path": {"type": ["string", "null"]},
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "text", "source", "status"],
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "source": {"type": "string"},
                    "status": {"type": "string"},
                }
            }
        },
        "progress": {
            "type": "object",
            "required": ["total_requirements", "processed_requirements"],
            "properties": {
                "total_requirements": {"type": "integer", "minimum": 0},
                "processed_requirements": {"type": "integer", "minimum": 0},
                "total_test_cases": {"type": "integer", "minimum": 0},
                "approved_test_cases": {"type": "integer", "minimum": 0},
                "rejected_test_cases": {"type": "integer", "minimum": 0},
                "current_step": {"type": "string"},
            }
        },
        "total_tokens_used": {"type": "integer", "minimum": 0},
        "agent_type": {"type": ["string", "null"]},
        "notes": {"type": "array", "items": {"type": "string"}},
        "_signature": {"type": "string"}  # HMAC signature
    }
}


def _get_key_file_path() -> Path:
    key_path = os.getenv("AI_TEST_GEN_SIGNATURE_KEY")
    if key_path:
        path = Path(key_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path
    return Path.cwd() / ".ai-test-gen-signature-key"


def get_signature_key() -> bytes:
    """
    Get or generate signing key for HMAC.

    Uses cryptographically secure random generator for key creation.
    Stores key in user's home directory with restricted permissions (0600).

    Security considerations:
    - Key is 32 bytes (256 bits) from os.urandom (CSPRNG)
    - File permissions restrict access to owner only
    - Key is never logged or exposed

    Returns:
        Signing key bytes (32 bytes)
    """
    import os as _os
    import stat

    key_file = _get_key_file_path()

    if key_file.exists():
        # Verify file permissions before reading
        file_stat = key_file.stat()
        if file_stat.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            logger.warning("Signature key file has insecure permissions, regenerating...")
            key_file.unlink()
        else:
            key_data = key_file.read_bytes()
            # Validate key length
            if len(key_data) == 32:
                return key_data
            else:
                logger.warning("Invalid signature key length, regenerating...")
                key_file.unlink()

    # Generate new cryptographically secure key
    key = _os.urandom(32)  # 256-bit key from CSPRNG

    # Save with restricted permissions
    key_file.write_bytes(key)
    key_file.chmod(0o600)

    logger.info("Generated new cryptographically secure signature key")
    return key


def compute_signature(data: Dict[str, Any], exclude_signature: bool = True) -> str:
    """
    Compute HMAC-SHA256 signature for state data.
    
    Args:
        data: State data dictionary
        exclude_signature: Whether to exclude _signature field from computation
        
    Returns:
        Hex-encoded HMAC signature
    """
    # Get signing key
    key = get_signature_key()
    
    # Create a copy and remove signature if present
    data_copy = dict(data)
    if exclude_signature and '_signature' in data_copy:
        del data_copy['_signature']
    
    # Serialize data consistently
    content = json.dumps(data_copy, sort_keys=True, separators=(',', ':'))
    
    # Compute HMAC
    signature = hmac.new(key, content.encode('utf-8'), hashlib.sha256).hexdigest()
    
    return signature


def verify_signature(data: Dict[str, Any]) -> bool:
    """
    Verify HMAC signature of state data.
    
    Args:
        data: State data dictionary with _signature field
        
    Returns:
        True if signature is valid, False otherwise
    """
    if '_signature' not in data:
        logger.warning("State file has no signature")
        return False
    
    stored_signature = data['_signature']
    computed_signature = compute_signature(data, exclude_signature=True)
    
    # Use constant-time comparison
    is_valid = hmac.compare_digest(stored_signature, computed_signature)
    
    if not is_valid:
        SecurityLogger.log_state_integrity_failure(
            "state file",
            "HMAC signature mismatch"
        )
    
    return is_valid


def validate_schema(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate state data against JSON schema.
    
    Args:
        data: State data dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        from jsonschema import validate
        from jsonschema.exceptions import ValidationError
    except ImportError:
        logger.warning("jsonschema not installed, skipping schema validation")
        return True, None

    try:
        validate(instance=data, schema=STATE_SCHEMA)
        return True, None
    except ValidationError as e:
        error_msg = f"Schema validation failed: {e.message}"
        logger.error(error_msg)
        SecurityLogger.log_state_integrity_failure("state file", error_msg)
        return False, error_msg


def sign_state_file(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sign state data with HMAC signature.
    
    Args:
        data: State data dictionary
        
    Returns:
        Data dictionary with _signature field added
    """
    # Compute signature
    signature = compute_signature(data, exclude_signature=True)
    
    # Add signature to data
    data_copy = dict(data)
    data_copy['_signature'] = signature
    
    return data_copy


def validate_state_file(file_path: Path) -> Tuple[bool, list[str]]:
    """
    Validate state file integrity and schema.
    
    Args:
        file_path: Path to state file
        
    Returns:
        Tuple of (is_valid, list of warnings/errors)
    """
    warnings = []
    
    if not file_path.exists():
        return True, []  # No file to validate
    
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate schema
        is_valid_schema, schema_error = validate_schema(data)
        if not is_valid_schema:
            warnings.append(f"Schema validation failed: {schema_error}")
        
        # Verify signature
        if not verify_signature(data):
            warnings.append("HMAC signature verification failed - file may have been tampered with")
        
        # Check required fields
        required_keys = ['session_id', 'requirements', 'progress']
        for key in required_keys:
            if key not in data:
                warnings.append(f"Missing required field: {key}")
        
        # Validate progress consistency
        progress = data.get('progress', {})
        requirements_count = len(data.get('requirements', []))
        if progress.get('total_requirements', 0) != requirements_count:
            warnings.append(
                f"Progress mismatch: total_requirements={progress.get('total_requirements')} "
                f"but found {requirements_count} requirements"
            )
        
        return len(warnings) == 0, warnings
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON: {e}"
        SecurityLogger.log_state_integrity_failure(str(file_path), error_msg)
        return False, [error_msg]
        
    except Exception as e:
        error_msg = f"Validation error: {e}"
        logger.error(error_msg)
        return False, [error_msg]


def create_backup(file_path: Path) -> Optional[Path]:
    """
    Create backup of state file before modification.
    
    Args:
        file_path: Path to state file
        
    Returns:
        Path to backup file, or None if backup failed
    """
    if not file_path.exists():
        return None
    
    try:
        backup_path = file_path.with_suffix('.json.backup')
        
        # Read original
        content = file_path.read_bytes()
        
        # Write backup
        backup_path.write_bytes(content)
        backup_path.chmod(0o600)
        
        logger.debug(f"Created backup: {backup_path}")
        return backup_path
        
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def restore_from_backup(file_path: Path) -> bool:
    """
    Restore state file from backup.
    
    Args:
        file_path: Path to state file
        
    Returns:
        True if restored successfully, False otherwise
    """
    backup_path = file_path.with_suffix('.json.backup')
    
    if not backup_path.exists():
        logger.error("No backup file found")
        return False
    
    try:
        # Validate backup first
        is_valid, warnings = validate_state_file(backup_path)
        if not is_valid:
            logger.error(f"Backup file is invalid: {warnings}")
            return False
        
        # Restore from backup
        content = backup_path.read_bytes()
        file_path.write_bytes(content)
        file_path.chmod(0o600)
        
        logger.info(f"Restored state from backup: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to restore from backup: {e}")
        return False


# Export
__all__ = [
    'compute_signature',
    'verify_signature',
    'validate_schema',
    'sign_state_file',
    'validate_state_file',
    'create_backup',
    'restore_from_backup',
    'STATE_SCHEMA',
]
