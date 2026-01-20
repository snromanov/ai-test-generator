#!/usr/bin/env python3
"""
Rate limiting для защиты от избыточных запросов (OWASP A04).

Prevents resource exhaustion and abuse through rate limiting.
"""
import time
from collections import defaultdict, deque
from typing import Optional, Dict
from threading import Lock

from src.utils.logger import setup_logger
from src.utils.security_logging import SecurityLogger

logger = setup_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Allows a specified number of requests within a time window.
    """
    
    def __init__(self, max_calls: int, period: int, name: str = "default"):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
            name: Name for logging
        """
        self.max_calls = max_calls
        self.period = period
        self.name = name
        self.calls: deque = deque()
        self.lock = Lock()
        
        logger.info(f"RateLimiter initialized: {name} ({max_calls} calls/{period}s)")
    
    def allow_request(self) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        with self.lock:
            now = time.time()
            
            # Remove calls outside the current window
            while self.calls and now - self.calls[0] >= self.period:
                self.calls.popleft()
            
            # Check if we're under the limit
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            
            # Rate limit exceeded
            SecurityLogger.log_rate_limit_exceeded(
                resource=self.name,
                limit=self.max_calls,
                window=self.period
            )
            return False
    
    def wait_if_needed(self) -> float:
        """
        Wait if necessary to respect rate limit.
        
        Returns:
            Time waited in seconds
        """
        with self.lock:
            now = time.time()
            
            # Remove old calls
            while self.calls and now - self.calls[0] >= self.period:
                self.calls.popleft()
            
            # If under limit, proceed
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return 0.0
            
            # Calculate wait time
            oldest_call = self.calls[0]
            wait_time = self.period - (now - oldest_call)
            
            if wait_time > 0:
                logger.debug(f"Rate limit reached for {self.name}, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
                
                # Add new call after waiting
                self.calls.append(time.time())
                return wait_time
            
            return 0.0
    
    def get_remaining_calls(self) -> int:
        """
        Get number of remaining calls in current window.
        
        Returns:
            Number of calls still allowed
        """
        with self.lock:
            now = time.time()
            
            # Remove old calls
            while self.calls and now - self.calls[0] >= self.period:
                self.calls.popleft()
            
            return max(0, self.max_calls - len(self.calls))
    
    def reset(self):
        """Reset the rate limiter."""
        with self.lock:
            self.calls.clear()
            logger.debug(f"Rate limiter reset: {self.name}")


class GlobalRateLimitManager:
    """
    Manages multiple rate limiters for different resources.
    """
    
    def __init__(self):
        """Initialize global rate limit manager."""
        self.limiters: Dict[str, RateLimiter] = {}
        self.lock = Lock()
    
    def get_limiter(
        self,
        name: str,
        max_calls: int = 10,
        period: int = 60
    ) -> RateLimiter:
        """
        Get or create a rate limiter.
        
        Args:
            name: Name of the resource
            max_calls: Maximum calls allowed
            period: Time period in seconds
            
        Returns:
            RateLimiter instance
        """
        with self.lock:
            if name not in self.limiters:
                self.limiters[name] = RateLimiter(max_calls, period, name)
            return self.limiters[name]
    
    def reset_all(self):
        """Reset all rate limiters."""
        with self.lock:
            for limiter in self.limiters.values():
                limiter.reset()
            logger.info("All rate limiters reset")


# Global instance
_rate_limit_manager = GlobalRateLimitManager()


def get_rate_limiter(name: str, max_calls: int = 10, period: int = 60) -> RateLimiter:
    """
    Get a rate limiter by name.
    
    Args:
        name: Resource name
        max_calls: Maximum calls allowed
        period: Time period in seconds
        
    Returns:
        RateLimiter instance
    """
    return _rate_limit_manager.get_limiter(name, max_calls, period)


# Predefined rate limiters for common resources
def get_confluence_rate_limiter() -> RateLimiter:
    """
    Get rate limiter for Confluence API.
    
    Confluence Cloud has rate limits:
    - 10 requests per second per IP
    - 5000 requests per hour per app
    
    We use conservative limits: 5 requests per second
    """
    return get_rate_limiter("confluence_api", max_calls=5, period=1)


def get_file_operation_rate_limiter() -> RateLimiter:
    """
    Get rate limiter for file operations.
    
    Prevents file system abuse: 100 operations per minute
    """
    return get_rate_limiter("file_operations", max_calls=100, period=60)


def get_state_update_rate_limiter() -> RateLimiter:
    """
    Get rate limiter for state updates.
    
    Prevents excessive state file writes: 30 per minute
    """
    return get_rate_limiter("state_updates", max_calls=30, period=60)


# Export
__all__ = [
    'RateLimiter',
    'GlobalRateLimitManager',
    'get_rate_limiter',
    'get_confluence_rate_limiter',
    'get_file_operation_rate_limiter',
    'get_state_update_rate_limiter',
]
