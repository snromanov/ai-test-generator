#!/usr/bin/env python3
"""
SSRF (Server-Side Request Forgery) Protection (OWASP A10).

Validates URLs and prevents requests to private networks or unauthorized domains.
"""
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Tuple, Optional

from src.utils.logger import setup_logger
from src.utils.security_logging import SecurityLogger

logger = setup_logger(__name__)

# Allowed Confluence domains (customize based on your setup)
ALLOWED_CONFLUENCE_DOMAINS = [
    'atlassian.net',
    'atlassian.com',
]

# Request timeout in seconds
REQUEST_TIMEOUT = 30

# Maximum response size (10MB)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024


def is_private_ip(ip: str) -> bool:
    """
    Check if IP address is private or reserved.
    
    Args:
        ip: IP address string
        
    Returns:
        True if IP is private/reserved, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return (
            ip_obj.is_private or
            ip_obj.is_loopback or
            ip_obj.is_link_local or
            ip_obj.is_reserved or
            ip_obj.is_multicast
        )
    except ValueError:
        return True  # If invalid, treat as suspicious


def validate_confluence_url(url: str) -> Tuple[bool, str]:
    """
    Validate Confluence URL to prevent SSRF attacks.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    try:
        parsed = urlparse(url)
        
        # Only allow HTTPS
        if parsed.scheme != 'https':
            SecurityLogger.log_ssrf_attempt(url, "Non-HTTPS scheme")
            return False, f"Only HTTPS URLs allowed, got: {parsed.scheme}"
        
        # Check hostname exists
        hostname = parsed.hostname
        if not hostname:
            return False, "URL must have a hostname"
        
        # Validate hostname is not an IP address (should be domain)
        try:
            ipaddress.ip_address(hostname)
            SecurityLogger.log_ssrf_attempt(url, "Direct IP address not allowed")
            return False, "Direct IP addresses not allowed, use domain names"
        except ValueError:
            # Good - it's not an IP, it's a hostname
            pass
        
        # Resolve hostname to IP and check it's not private
        try:
            ip = socket.gethostbyname(hostname)
            if is_private_ip(ip):
                SecurityLogger.log_ssrf_attempt(url, f"Resolves to private IP: {ip}")
                return False, f"URL resolves to private network: {ip}"
        except socket.gaierror as e:
            SecurityLogger.log_ssrf_attempt(url, f"Cannot resolve: {e}")
            return False, f"Cannot resolve hostname: {hostname}"
        
        # Check domain whitelist
        if not any(hostname.endswith(domain) for domain in ALLOWED_CONFLUENCE_DOMAINS):
            SecurityLogger.log_ssrf_attempt(url, f"Domain not in whitelist: {hostname}")
            return False, f"Domain not allowed: {hostname}"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False, f"Invalid URL: {str(e)}"


def validate_generic_url(url: str, allowed_schemes: Optional[list] = None) -> Tuple[bool, str]:
    """
    Validate generic URL (non-Confluence).
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: ['https'])
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if allowed_schemes is None:
        allowed_schemes = ['https']
    
    if not url:
        return False, "URL cannot be empty"
    
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in allowed_schemes:
            SecurityLogger.log_ssrf_attempt(url, f"Scheme not allowed: {parsed.scheme}")
            return False, f"Scheme must be one of: {', '.join(allowed_schemes)}"
        
        # Check hostname
        hostname = parsed.hostname
        if not hostname:
            return False, "URL must have a hostname"
        
        # Check for private IPs
        try:
            ip = socket.gethostbyname(hostname)
            if is_private_ip(ip):
                SecurityLogger.log_ssrf_attempt(url, f"Resolves to private IP: {ip}")
                return False, "URL resolves to private network"
        except socket.gaierror as e:
            SecurityLogger.log_ssrf_attempt(url, f"Cannot resolve: {e}")
            return False, f"Cannot resolve hostname: {hostname}"
        
        return True, ""
        
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"


def safe_request_wrapper(url: str, timeout: int = REQUEST_TIMEOUT) -> dict:
    """
    Wrapper for making safe HTTP requests with SSRF protection.
    
    Args:
        url: URL to request
        timeout: Request timeout in seconds
        
    Returns:
        Dict with response info or error
        
    Raises:
        ValueError: If URL is unsafe
    """
    # Validate URL
    is_valid, error = validate_confluence_url(url)
    if not is_valid:
        raise ValueError(f"Unsafe URL: {error}")
    
    try:
        import requests
        
        # Make request with safety measures
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=False,  # Prevent redirect-based SSRF
            stream=True,
            headers={'User-Agent': 'AI-Test-Generator/1.0'}
        )
        
        # Check response size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_RESPONSE_SIZE:
            raise ValueError(f"Response too large: {content_length} bytes")
        
        # Read response with size limit
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_RESPONSE_SIZE:
                raise ValueError("Response exceeded size limit")
        
        return {
            'status_code': response.status_code,
            'content': content,
            'headers': dict(response.headers)
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise ValueError(f"Request failed: {str(e)}")


# Export
__all__ = [
    'validate_confluence_url',
    'validate_generic_url',
    'is_private_ip',
    'safe_request_wrapper',
    'ALLOWED_CONFLUENCE_DOMAINS',
    'REQUEST_TIMEOUT',
    'MAX_RESPONSE_SIZE',
]
