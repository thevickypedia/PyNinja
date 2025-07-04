import functools
import inspect
import time
from typing import Any, Callable, Dict, Tuple, Union


def timed_cache(max_age: int, maxsize: int = 128, typed: bool = False):
    """Least-recently-used cache decorator with time-based cache invalidation for both sync and async functions.

    Args:
        max_age: Time to live for cached results (in seconds).
        maxsize: Maximum cache size (see `functools.lru_cache`).
        typed: Cache on distinct input types (see `functools.lru_cache`).

    See Also:
        - Works with both synchronous and asynchronous functions.
        - For async functions, caches the awaited result, not the coroutine itself.
        - Custom async cache implementation to handle coroutine lifecycle properly.

    Notes:
        - ``lru_cache`` takes all params of the function and creates a key.
        - If even one key is changed, it will map to new entry thus refreshed.
        - This is just a trick to force lru_cache lib to provide TTL on top of max size.
        - Uses ``time.monotonic`` since ``time.time`` relies on the system clock and may not be monotonic.
        - | ``time.time()`` not always guaranteed to increase,
          | it may in fact decrease if the machine syncs its system clock over a network.
    """

    def _decorator(fn: Callable) -> Union[Callable, Callable]:
        """Decorator for the timed cache that handles both sync and async functions.

        Args:
            fn: Function that has been decorated (sync or async).

        Returns:
            Union[Callable, Callable]:
            Returns a wrapped function that implements the timed cache logic.
        """
        if inspect.iscoroutinefunction(fn):
            # Custom cache for async functions since lru_cache doesn't work with coroutines
            async_cache: Dict[Tuple, Any] = {}
            access_order = []  # For LRU tracking

            @functools.wraps(fn)
            async def _async_wrapped(*args: tuple, **kwargs: dict[str, Any]) -> Any:
                """Async wrapped function that calculates the timed hash and checks the cache.

                Args:
                    *args: Args passed to the async function.
                    **kwargs: Keyword args passed to the async function.

                Returns:
                    Any:
                    Result of the cached async function call.
                """
                timed_hash = int(time.monotonic() / max_age)

                # Create cache key including the timed hash
                if typed:
                    key = (
                        *args,
                        timed_hash,
                        tuple(sorted(kwargs.items())),
                        tuple(type(arg) for arg in args),
                    )
                else:
                    key = (*args, timed_hash, tuple(sorted(kwargs.items())))

                # Check if we have a cached result
                if key in async_cache:
                    # Move to end for LRU tracking
                    access_order.remove(key)
                    access_order.append(key)
                    return async_cache[key]

                # Not in cache, execute the async function
                result = await fn(*args, **kwargs)

                # Add to cache
                async_cache[key] = result
                access_order.append(key)

                # Implement LRU eviction if we exceed maxsize
                while len(async_cache) > maxsize:
                    oldest_key = access_order.pop(0)
                    del async_cache[oldest_key]

                return result

            return _async_wrapped
        else:
            # Handle sync functions with original approach
            @functools.lru_cache(maxsize=maxsize, typed=typed)
            def _sync_cached(
                *args: tuple, __timed_hash: int, **kwargs: dict[str, Any]
            ) -> Any:
                """Sync cached function that uses a timed hash to invalidate cache.

                Args:
                    *args: Args passed to the function.
                    __timed_hash: Timed hash to ensure cache invalidation.
                    **kwargs: Keyword args passed to the function.

                Returns:
                    Any:
                    Result of the function call.
                """
                return fn(*args, **kwargs)

            @functools.wraps(fn)
            def _sync_wrapped(*args: tuple, **kwargs: dict[str, Any]) -> Any:
                """Sync wrapped function that calculates the timed hash and calls the cached function.

                Args:
                    *args: Args passed to the function.
                    **kwargs: Keyword args passed to the function.

                Returns:
                    Any:
                    Result of the cached function call.
                """
                timed_hash = int(time.monotonic() / max_age)
                return _sync_cached(*args, __timed_hash=timed_hash, **kwargs)

            return _sync_wrapped

    return _decorator


if __name__ == "__main__":
    import asyncio

    @timed_cache(3)
    def expensive():
        """Expensive function that returns response from the origin.

        See Also:
            - This function can call N number of downstream functions.
            - The response will be cached as long as the size limit isn't reached.
        """
        print("response from origin")
        return "cached response [sync]"

    for _ in range(10):
        print(expensive())
        time.sleep(0.5)

    @timed_cache(3)
    async def expensive_async():
        """Expensive function that returns response from the origin.

        See Also:
            - This function can call N number of downstream functions.
            - The response will be cached as long as the size limit isn't reached.
        """
        print("response from origin")
        return "cached response [async]"

    for _ in range(10):
        print(asyncio.run(expensive_async()))
        time.sleep(0.5)
