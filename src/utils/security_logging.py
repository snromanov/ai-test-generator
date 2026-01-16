#!/usr/bin/env python3
"""
Security event logging (OWASP A09).

Dedicated logging for security-related events with sanitization.
"""
import re
from datetime import datetime
from typing import Optional, Dict, Any

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def sanitize_log_message(message: str) -> str:
    """
    Remove sensitive data from log messages.
    
    Args:
        message: Log message to sanitize
        
    Returns:
        Sanitized log message
    """
    if not message:
        return message
    
    # Remove API tokens (various patterns)
    message = re.sub(
        r'(token|api[_-]?key|auth|bearer|password)["\s:=]+([A-Za-z0-9+/=]{20,})',
        r'\1=***REDACTED***',
        message,
        flags=re.IGNORECASE
    )
    
    # Remove passwords
    message = re.sub(
        r'(password|passwd|pwd)["\s:=]+[^\s"\']+',
        r'\1=***REDACTED***',
        message,
        flags=re.IGNORECASE
    )
    
    # Remove email addresses (optional - keep domain for debugging)
    message = re.sub(
        r'\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b',
        r'***@\1',
        message
    )
    
    return message


class SecurityLogger:
    """Dedicated logger for security events."""
    
    @staticmethod
    def log_injection_attempt(
        text: str,
        risk_score: float,
        patterns: list[str],
        source: str = "unknown"
    ):
        """
        Log potential injection attempts.
        
        Args:
            text: Text containing potential injection
            risk_score: Risk score (0.0 - 1.0)
            patterns: Detected patterns
            source: Source of the input (file, confluence, manual)
        """
        # Don't log full text - only preview
        text_preview = text[:100] + "..." if len(text) > 100 else text
        
        logger.warning(
            f"SECURITY: Injection detected (risk={risk_score:.2f}, source={source})",
            extra={
                'event_type': 'injection_attempt',
                'risk_score': risk_score,
                'patterns_count': len(patterns),
                'source': source,
                'text_length': len(text),
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Log patterns separately for debugging
        if patterns:
            logger.debug(f"Detected patterns: {', '.join(patterns[:5])}")
    
    @staticmethod
    def log_auth_failure(service: str, reason: Optional[str] = None):
        """
        Log authentication failures.
        
        Args:
            service: Service name (e.g., 'confluence')
            reason: Optional failure reason
        """
        logger.error(
            f"SECURITY: Authentication failed for {service}" + (f": {reason}" if reason else ""),
            extra={
                'event_type': 'auth_failure',
                'service': service,
                'reason': sanitize_log_message(reason) if reason else None,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def log_file_access(file_path: str, operation: str, success: bool = True):
        """
        Log sensitive file access.
        
        Args:
            file_path: Path to file
            operation: Operation type (read, write, delete)
            success: Whether operation succeeded
        """
        level = logger.info if success else logger.warning
        level(
            f"SECURITY: File {operation}: {file_path} ({'success' if success else 'failed'})",
            extra={
                'event_type': 'file_access',
                'operation': operation,
                'file_path': file_path,
                'success': success,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def log_validation_failure(
        validation_type: str,
        value: str,
        reason: str
    ):
        """
        Log validation failures.
        
        Args:
            validation_type: Type of validation (path, size, format, etc.)
            value: Value that failed validation (sanitized)
            reason: Reason for failure
        """
        # Sanitize value before logging
        safe_value = value[:50] + "..." if len(value) > 50 else value
        safe_value = sanitize_log_message(safe_value)
        
        logger.warning(
            f"SECURITY: Validation failed ({validation_type}): {reason}",
            extra={
                'event_type': 'validation_failure',
                'validation_type': validation_type,
                'value_preview': safe_value,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def log_rate_limit_exceeded(
        resource: str,
        limit: int,
        window: int
    ):
        """
        Log rate limit violations.
        
        Args:
            resource: Resource being rate limited
            limit: Rate limit threshold
            window: Time window in seconds
        """
        logger.warning(
            f"SECURITY: Rate limit exceeded for {resource} ({limit} requests/{window}s)",
            extra={
                'event_type': 'rate_limit_exceeded',
                'resource': resource,
                'limit': limit,
                'window': window,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def log_ssrf_attempt(url: str, reason: str):
        """
        Log SSRF (Server-Side Request Forgery) attempts.
        
        Args:
            url: URL that was blocked
            reason: Reason for blocking
        """
        logger.error(
            f"SECURITY: SSRF attempt blocked: {url} ({reason})",
            extra={
                'event_type': 'ssrf_attempt',
                'url': url,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def log_state_integrity_failure(
        file_path: str,
        reason: str
    ):
        """
        Log state file integrity failures.
        
        Args:
            file_path: Path to state file
            reason: Reason for failure
        """
        logger.error(
            f"SECURITY: State integrity check failed: {file_path} ({reason})",
            extra={
                'event_type': 'state_integrity_failure',
                'file_path': file_path,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def log_security_event(
        event_type: str,
        message: str,
        severity: str = "warning",
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        Log generic security event.
        
        Args:
            event_type: Type of security event
            message: Event message
            severity: Severity level (info, warning, error)
            extra_data: Additional event data
        """
        # Sanitize message
        safe_message = sanitize_log_message(message)
        
        # Prepare extra data
        event_data = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat()
        }
        if extra_data:
            event_data.update(extra_data)
        
        # Log with appropriate level
        log_func = {
            'info': logger.info,
            'warning': logger.warning,
            'error': logger.error
        }.get(severity, logger.warning)
        
        log_func(f"SECURITY: {safe_message}", extra=event_data)


# Convenience functions
def log_injection_attempt(text: str, risk_score: float, patterns: list[str], source: str = "unknown"):
    """Convenience wrapper for SecurityLogger.log_injection_attempt."""
    SecurityLogger.log_injection_attempt(text, risk_score, patterns, source)


def log_auth_failure(service: str, reason: Optional[str] = None):
    """Convenience wrapper for SecurityLogger.log_auth_failure."""
    SecurityLogger.log_auth_failure(service, reason)


def log_file_access(file_path: str, operation: str, success: bool = True):
    """Convenience wrapper for SecurityLogger.log_file_access."""
    SecurityLogger.log_file_access(file_path, operation, success)


def log_validation_failure(validation_type: str, value: str, reason: str):
    """Convenience wrapper for SecurityLogger.log_validation_failure."""
    SecurityLogger.log_validation_failure(validation_type, value, reason)


# Export
__all__ = [
    'SecurityLogger',
    'sanitize_log_message',
    'log_injection_attempt',
    'log_auth_failure',
    'log_file_access',
    'log_validation_failure',
]
