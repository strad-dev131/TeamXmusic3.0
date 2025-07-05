import time
from functools import wraps


def async_cache(ttl: int = 3600):
    """Simple TTL cache decorator for async functions."""

    def decorator(func):
        cache = {}

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # ignore 'self' for methods
            key = (args[1:] if len(args) > 1 else (), tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                value, exp = cache[key]
                if now < exp:
                    return value
            result = await func(*args, **kwargs)
            cache[key] = (result, now + ttl)
            return result

        wrapper.cache_clear = cache.clear
        return wrapper

    return decorator
