import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")

def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for async function retry logic
    
    :param retries: Number of retries
    :param delay: Initial delay between retries in seconds
    :param backoff: Multiplier for delay between retries
    :param exceptions: Tuple of exceptions to catch
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        logging.error(f"Final retry failed for {func.__name__}: {str(e)}")
                        raise
                    
                    logging.warning(
                        f"Attempt {attempt + 1}/{retries} failed for {func.__name__}: {str(e)}"
                        f" Retrying in {current_delay:.2f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator
