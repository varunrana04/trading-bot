#!/usr/bin/env python3
"""
================================================================================
                    PHASE 2 TESTS — Correlation, Circuit Breaker, Rate Limiter
================================================================================
Tests for the advanced features added in Phase 2.
================================================================================
"""

import sys
import os
import time
import unittest

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.correlation_guard import CorrelationGuard
from core.rate_limiter import RateLimiter
from live.paper_trader import PaperTrader


# ==============================================================================
#                         CORRELATION GUARD TESTS
# ==============================================================================

class TestCorrelationGuard(unittest.TestCase):
    """Tests for CorrelationGuard."""
    
    def setUp(self):
        self.guard = CorrelationGuard(max_per_group=2)
    
    def _mock_positions(self, entries):
        """Create mock positions dict from (symbol, direction) tuples."""
        class MockPos:
            def __init__(self, d): self.direction = d
        return {sym: MockPos(d) for sym, d in entries}
    
    def test_blocks_3rd_same_direction_crypto(self):
        """3rd BUY in crypto group should be blocked."""
        positions = self._mock_positions([("BTCUSDT", "BUY"), ("ETHUSDT", "BUY")])
        allowed, reason = self.guard.can_open("SOLUSDT", "BUY", positions)
        self.assertFalse(allowed)
        self.assertIn("Correlation limit", reason)
    
    def test_allows_opposite_direction(self):
        """SHORT should be allowed even if 2 BUYs exist in same group."""
        positions = self._mock_positions([("BTCUSDT", "BUY"), ("ETHUSDT", "BUY")])
        allowed, _ = self.guard.can_open("SOLUSDT", "SELL", positions)
        self.assertTrue(allowed)
    
    def test_allows_different_group(self):
        """Metals group is independent from crypto group."""
        positions = self._mock_positions([("BTCUSDT", "BUY"), ("ETHUSDT", "BUY")])
        allowed, _ = self.guard.can_open("XAUUSDT", "BUY", positions)
        self.assertTrue(allowed)
    
    def test_allows_within_limit(self):
        """1 existing position should allow 2nd in same direction."""
        positions = self._mock_positions([("BTCUSDT", "BUY")])
        allowed, _ = self.guard.can_open("ETHUSDT", "BUY", positions)
        self.assertTrue(allowed)
    
    def test_unknown_symbol_always_allowed(self):
        """Unknown symbols are not in any group, should always pass."""
        positions = self._mock_positions([("BTCUSDT", "BUY"), ("ETHUSDT", "BUY")])
        allowed, _ = self.guard.can_open("DOGEUSDT", "BUY", positions)
        self.assertTrue(allowed)
    
    def test_exposure_summary(self):
        """Exposure summary should show correct net direction."""
        positions = self._mock_positions([("BTCUSDT", "BUY"), ("ETHUSDT", "SELL")])
        exposure = self.guard.get_group_exposure(positions)
        self.assertEqual(exposure["crypto"]["net"], 0)  # 1 long - 1 short


# ==============================================================================
#                         CIRCUIT BREAKER TESTS
# ==============================================================================

class TestCircuitBreaker(unittest.TestCase):
    """Tests for circuit breaker in PaperTrader."""
    
    def setUp(self):
        self.trader = PaperTrader(starting_balance=10000.0, min_leverage=5, max_leverage=10)
    
    def _open_and_close(self, symbol, direction, entry, exit_price, reason="MANUAL"):
        """Helper: open a position and close it."""
        signal = {
            "symbol": symbol, "signal": direction, "price": entry,
            "conviction": 0.5, "atr_pct": 1.0
        }
        self.trader.open_position(signal)
        self.trader.close_position(symbol, exit_price, reason)
    
    def test_circuit_breaker_not_triggered_by_wins(self):
        """Winning trades should not trigger circuit breaker."""
        self._open_and_close("BTCUSDT", "BUY", 100.0, 110.0)
        self.assertFalse(self.trader._circuit_open)
    
    def test_consecutive_losses_resets_on_win(self):
        """A win should reset the consecutive loss counter."""
        # 2 losses
        self._open_and_close("BTCUSDT", "BUY", 100.0, 90.0)
        self._open_and_close("ETHUSDT", "BUY", 100.0, 90.0)
        self.assertEqual(self.trader._consecutive_losses, 2)
        
        # 1 win resets
        self._open_and_close("SOLUSDT", "BUY", 100.0, 120.0)
        self.assertEqual(self.trader._consecutive_losses, 0)
    
    def test_circuit_breaker_activates_after_3_losses(self):
        """3 consecutive losses should activate circuit breaker."""
        self._open_and_close("BTCUSDT", "BUY", 100.0, 90.0)
        self._open_and_close("ETHUSDT", "BUY", 100.0, 90.0)
        self._open_and_close("SOLUSDT", "BUY", 100.0, 90.0)
        self.assertTrue(self.trader._circuit_open)
    
    def test_circuit_breaker_blocks_new_trades(self):
        """When circuit breaker is active, new trades should be rejected."""
        # Manually activate circuit breaker
        self.trader._circuit_open = True
        self.trader._circuit_open_time = time.time()
        
        signal = {
            "symbol": "BTCUSDT", "signal": "BUY", "price": 100.0,
            "conviction": 0.5, "atr_pct": 1.0
        }
        result = self.trader.open_position(signal)
        self.assertFalse(result)


# ==============================================================================
#                         RATE LIMITER TESTS
# ==============================================================================

class TestRateLimiter(unittest.TestCase):
    """Tests for RateLimiter."""
    
    def test_allows_within_limit(self):
        """Requests within limit should not wait."""
        limiter = RateLimiter(max_requests=10, window_seconds=1.0, name="test1")
        for _ in range(10):
            wait = limiter.acquire()
            self.assertEqual(wait, 0)
    
    def test_can_proceed_accurate(self):
        """can_proceed should reflect current usage correctly."""
        limiter = RateLimiter(max_requests=3, window_seconds=10.0, name="test2")
        self.assertTrue(limiter.can_proceed())
        for _ in range(3):
            limiter.acquire()
        self.assertFalse(limiter.can_proceed())
    
    def test_stats_tracking(self):
        """Stats should track total requests accurately."""
        limiter = RateLimiter(max_requests=100, window_seconds=1.0, name="test3")
        for _ in range(5):
            limiter.acquire()
        self.assertEqual(limiter.stats["total_requests"], 5)
        self.assertEqual(limiter.stats["total_waits"], 0)
    
    def test_usage_percentage(self):
        """Usage percentage should reflect current window usage."""
        limiter = RateLimiter(max_requests=10, window_seconds=10.0, name="test4")
        limiter.acquire()
        self.assertAlmostEqual(limiter.usage_pct, 10.0, places=0)


if __name__ == "__main__":
    unittest.main()
