"""
Caching Configuration for Hotel Booking System
Simple in-memory cache with smart invalidation
"""

from flask_caching import Cache
from functools import wraps
import time

# Initialize cache (will be configured by app)
cache = None

def init_cache(app):
    """Initialize Flask-Caching with app"""
    global cache
    cache = Cache(app, config={
        'CACHE_TYPE': 'SimpleCache',  # In-memory cache
        'CACHE_DEFAULT_TIMEOUT': 30,  # 30 seconds TTL
        'CACHE_THRESHOLD': 100  # Max 100 cached items
    })
    return cache

def clear_booking_cache():
    """Clear all booking-related cache entries"""
    if cache:
        cache.delete_memoized('load_booking_data')
        cache.delete_memoized('load_booking_data_for_calculations')
        print("🔄 Cache cleared - booking data will be reloaded on next request")

# Decorator for caching with timestamp tracking
def cached_with_timestamp(timeout=30, key_prefix='view'):
    """Cache decorator that tracks last update time"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if force_fresh is requested
            force_fresh = kwargs.get('force_fresh', False)

            if force_fresh:
                # Skip cache and get fresh data
                result = f(*args, **kwargs)
                # Update cache with fresh data
                if cache:
                    cache.set(f'{key_prefix}_{f.__name__}', result, timeout=timeout)
                return result

            # Try to get from cache
            if cache:
                cached_result = cache.get(f'{key_prefix}_{f.__name__}')
                if cached_result is not None:
                    return cached_result

            # Not in cache, compute and store
            result = f(*args, **kwargs)
            if cache:
                cache.set(f'{key_prefix}_{f.__name__}', result, timeout=timeout)

            return result
        return decorated_function
    return decorator
