# src/utils/retry.py
"""Retry decorator utility with SSL support."""
import time
import functools
import ssl
import socket
from googleapiclient.errors import HttpError
from utils.logger import get_logger

logger = get_logger()

# Define exceptions that are safe to retry
RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    socket.timeout,
    ssl.SSLError,
    HttpError,
    OSError
)

def retry_with_backoff(max_retries=9, initial_delay=2, backoff_factor=2, retryable_exceptions=RETRYABLE_ERRORS):
    """Decorator for exponential backoff retries."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Don't retry 4xx HttpErrors (except 429)
                    if isinstance(e, HttpError):
                        if e.resp.status < 500 and e.resp.status != 429:
                            raise e

                    if attempt == max_retries:
                        break
                    
                    wait_time = delay * (backoff_factor ** attempt)
                    
                    error_msg = str(e)
                    if "SSL" in error_msg:
                        logger.warning(f"SSL issue in {func.__name__} (Attempt {attempt+1}): {e}. Retrying...")
                    else:
                        logger.warning(f"Network glitch in {func.__name__} (Attempt {attempt+1}): {e}. Retrying in {wait_time}s...")
                        
                    time.sleep(wait_time)
            
            logger.error(f"Permanently failed {func.__name__} after {max_retries} attempts.")
            raise last_exception
        return wrapper
    return decorator