"""Retry decorator with exponential backoff."""
import time
import functools
from typing import Callable, Type, Tuple
from .exceptions import RetryableError
from .logger import get_logger

logger = get_logger()


def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (RetryableError,)
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for wait time between retries
        retryable_exceptions: Tuple of exception types that trigger retry
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}")
                        raise
                    
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {wait_time:.1f}s: {e}"
                    )
                    time.sleep(wait_time)
            
            # Should never reach here
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
