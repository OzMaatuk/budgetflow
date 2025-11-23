"""Retry decorator with exponential backoff."""
# utils/retry.py
import time
import functools
from typing import Callable, Tuple, Type
from .exceptions import RetryableError
from .logger import get_logger
from googleapiclient.errors import HttpError
import ssl

logger = get_logger()

def retry_with_backoff(
    max_retries: int = 6,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        RetryableError,
        HttpError,
        ConnectionError,
        TimeoutError,
        ssl.SSLError,
        OSError,
    ),
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
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    wait = (backoff_factor ** attempt) + (0.1 if jitter else 0)
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait:.1f}s..."
                    )
                    time.sleep(wait)
            logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {last_exception}")
            raise last_exception
        return wrapper
    return decorator
    