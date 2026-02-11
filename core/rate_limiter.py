"""
Rate Limiter — Token bucket rate limiter for API calls.

Prevents exceeding Binance API limits (1200 requests/min default).
Supports both sync and async usage.

Usage:
    from core.rate_limiter import RateLimiter
    
    limiter = RateLimiter(max_requests=1200, window_seconds=60)
    
    # Sync
    limiter.acquire()  # Blocks if rate exceeded
    
    # Async
    await limiter.async_acquire()
"""

import time
import asyncio
import logging
from collections import deque
from threading import Lock

logger = logging.getLogger("RateLimiter")


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Thread-safe for sync usage, supports async via async_acquire().
    """
    
    def __init__(self, max_requests: int = 1200, window_seconds: float = 60.0,
                 name: str = "API"):
        self.max_requests = max_requests
        self.window = window_seconds
        self.name = name
        self._timestamps: deque = deque()
        self._lock = Lock()
        self._total_requests = 0
        self._total_waits = 0
        
        logger.info(f"RateLimiter [{name}]: {max_requests} req/{window_seconds}s")
    
    def acquire(self, weight: int = 1) -> float:
        """
        Acquire permission to make API call(s). Blocks if rate exceeded.
        
        Args:
            weight: Number of request slots to consume (default 1)
        
        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        with self._lock:
            return self._acquire_internal(weight)
    
    def _acquire_internal(self, weight: int) -> float:
        """Internal acquire logic (must hold lock)."""
        now = time.monotonic()
        total_wait = 0.0
        
        for _ in range(weight):
            # Remove expired timestamps
            cutoff = now - self.window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            
            # If at capacity, wait for oldest to expire
            if len(self._timestamps) >= self.max_requests:
                wait_until = self._timestamps[0] + self.window
                wait_time = max(0, wait_until - now)
                
                if wait_time > 0:
                    logger.warning(
                        f"RateLimiter [{self.name}]: Rate limit hit, "
                        f"waiting {wait_time:.2f}s "
                        f"({len(self._timestamps)}/{self.max_requests} used)"
                    )
                    self._total_waits += 1
                    time.sleep(wait_time)
                    total_wait += wait_time
                    now = time.monotonic()
                    
                    # Clean up again after wait
                    cutoff = now - self.window
                    while self._timestamps and self._timestamps[0] < cutoff:
                        self._timestamps.popleft()
            
            self._timestamps.append(now)
            self._total_requests += 1
        
        return total_wait
    
    async def async_acquire(self, weight: int = 1) -> float:
        """Async version of acquire(). Uses asyncio.sleep instead of blocking."""
        now = time.monotonic()
        total_wait = 0.0
        
        for _ in range(weight):
            cutoff = now - self.window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            
            if len(self._timestamps) >= self.max_requests:
                wait_until = self._timestamps[0] + self.window
                wait_time = max(0, wait_until - now)
                
                if wait_time > 0:
                    logger.warning(
                        f"RateLimiter [{self.name}]: Async rate limit hit, "
                        f"waiting {wait_time:.2f}s"
                    )
                    self._total_waits += 1
                    await asyncio.sleep(wait_time)
                    total_wait += wait_time
                    now = time.monotonic()
                    
                    cutoff = now - self.window
                    while self._timestamps and self._timestamps[0] < cutoff:
                        self._timestamps.popleft()
            
            self._timestamps.append(now)
            self._total_requests += 1
        
        return total_wait
    
    def can_proceed(self) -> bool:
        """Check if a request can proceed without waiting (non-blocking)."""
        now = time.monotonic()
        cutoff = now - self.window
        
        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return len(self._timestamps) < self.max_requests
    
    @property
    def usage_pct(self) -> float:
        """Current usage as percentage of limit."""
        now = time.monotonic()
        cutoff = now - self.window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps) / self.max_requests * 100
    
    @property
    def stats(self) -> dict:
        """Get limiter statistics."""
        return {
            "name": self.name,
            "total_requests": self._total_requests,
            "total_waits": self._total_waits,
            "current_usage": f"{self.usage_pct:.1f}%",
            "limit": f"{self.max_requests}/{self.window}s"
        }


# Singleton instances for common APIs
_limiters = {}

def get_limiter(name: str = "binance", max_requests: int = 1200, 
                window: float = 60.0) -> RateLimiter:
    """Get or create a named rate limiter singleton."""
    if name not in _limiters:
        _limiters[name] = RateLimiter(max_requests, window, name)
    return _limiters[name]


# Self-test
if __name__ == "__main__":
    import time as t
    
    print("=" * 50)
    print("  RATE LIMITER - SELF TEST")
    print("=" * 50)
    
    # Test with small limits for fast testing
    limiter = RateLimiter(max_requests=5, window_seconds=1.0, name="test")
    
    # Test 1: Should allow 5 requests immediately
    for i in range(5):
        wait = limiter.acquire()
        assert wait == 0, f"Request {i+1} should not wait"
    print("[OK] Test 1: 5 requests allowed immediately")
    
    # Test 2: 6th request should wait
    start = t.monotonic()
    limiter.acquire()
    elapsed = t.monotonic() - start
    assert elapsed > 0.1, "6th request should have waited"
    print(f"[OK] Test 2: 6th request waited {elapsed:.2f}s")
    
    # Test 3: can_proceed check
    limiter2 = RateLimiter(max_requests=3, window_seconds=1.0, name="test2")
    assert limiter2.can_proceed()
    for _ in range(3):
        limiter2.acquire()
    assert not limiter2.can_proceed()
    print("[OK] Test 3: can_proceed works correctly")
    
    # Test 4: Stats
    stats = limiter.stats
    assert stats["total_requests"] == 6
    assert stats["total_waits"] == 1
    print(f"[OK] Test 4: Stats correct - {stats}")
    
    # Test 5: Singleton
    l1 = get_limiter("binance")
    l2 = get_limiter("binance")
    assert l1 is l2
    print("[OK] Test 5: Singleton works")
    
    print("\nAll tests passed!")
