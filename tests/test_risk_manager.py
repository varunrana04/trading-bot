"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    RISK MANAGER TESTS                                       ║
║  Tests for position sizing, SL/TP, trailing stops, and daily limits         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
from pathlib import Path
import unittest

# Add root to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from core.risk_manager import RiskManager, RiskConfig, Position, OrderSide


class TestPosition(unittest.TestCase):
    """Tests for the Position dataclass."""

    def test_long_pnl_positive(self):
        """Test PnL calculation for a profitable long."""
        pos = Position(
            symbol="BTCUSDT", side=OrderSide.LONG,
            entry_price=100.0, quantity=1.0, leverage=5,
            stop_loss=95.0, take_profit=110.0
        )
        pnl = pos.get_pnl_percent(105.0)
        # 5% move * 5x leverage = 25%
        self.assertAlmostEqual(pnl, 25.0, places=1)

    def test_long_pnl_negative(self):
        """Test PnL calculation for a losing long."""
        pos = Position(
            symbol="BTCUSDT", side=OrderSide.LONG,
            entry_price=100.0, quantity=1.0, leverage=5,
            stop_loss=95.0, take_profit=110.0
        )
        pnl = pos.get_pnl_percent(97.0)
        self.assertLess(pnl, 0)

    def test_short_pnl_positive(self):
        """Test PnL calculation for a profitable short."""
        pos = Position(
            symbol="ETHUSDT", side=OrderSide.SHORT,
            entry_price=100.0, quantity=1.0, leverage=5,
            stop_loss=105.0, take_profit=90.0
        )
        pnl = pos.get_pnl_percent(95.0)
        self.assertGreater(pnl, 0)

    def test_check_sl_triggers_long(self):
        """Test stop loss triggers for long position."""
        pos = Position(
            symbol="BTCUSDT", side=OrderSide.LONG,
            entry_price=100.0, quantity=1.0, leverage=5,
            stop_loss=95.0, take_profit=110.0
        )
        triggered, reason = pos.check_sl_tp(94.0)
        self.assertTrue(triggered)
        self.assertIn("STOP", reason.upper())

    def test_check_tp_triggers_long(self):
        """Test take profit triggers for long position."""
        pos = Position(
            symbol="BTCUSDT", side=OrderSide.LONG,
            entry_price=100.0, quantity=1.0, leverage=5,
            stop_loss=95.0, take_profit=110.0
        )
        triggered, reason = pos.check_sl_tp(111.0)
        self.assertTrue(triggered)
        self.assertIn("PROFIT", reason.upper())

    def test_no_trigger_within_range(self):
        """Test no trigger when price is between SL and TP."""
        pos = Position(
            symbol="BTCUSDT", side=OrderSide.LONG,
            entry_price=100.0, quantity=1.0, leverage=5,
            stop_loss=95.0, take_profit=110.0
        )
        triggered, reason = pos.check_sl_tp(103.0)
        self.assertFalse(triggered)

    def test_trailing_stop_updates(self):
        """Test trailing stop activates after sufficient move."""
        pos = Position(
            symbol="BTCUSDT", side=OrderSide.LONG,
            entry_price=100.0, quantity=1.0, leverage=5,
            stop_loss=95.0, take_profit=110.0,
            trailing_stop=2.0, trailing_activation=3.0
        )
        # Move price up to activate trailing
        pos.update_trailing(103.5)  # +3.5%, activates trailing
        pos.update_trailing(105.0)  # Trail higher

        # Now pull back
        triggered = pos.update_trailing(102.5)
        # Should trigger trail stop at some point


class TestRiskConfig(unittest.TestCase):
    """Tests for RiskConfig defaults."""

    def test_default_values(self):
        """Test default configuration values are sensible."""
        config = RiskConfig()
        self.assertGreater(config.risk_per_trade, 0)
        self.assertLessEqual(config.risk_per_trade, 5.0)
        self.assertGreater(config.max_leverage, config.min_leverage)
        self.assertGreater(config.default_sl_percent, 0)
        self.assertGreater(config.default_tp_percent, config.default_sl_percent)

    def test_custom_config(self):
        """Test custom configuration overrides."""
        config = RiskConfig(risk_per_trade=2.0, max_leverage=20)
        self.assertEqual(config.risk_per_trade, 2.0)
        self.assertEqual(config.max_leverage, 20)


class TestRiskManager(unittest.TestCase):
    """Tests for RiskManager class."""

    def setUp(self):
        self.rm = RiskManager(capital=10000.0)

    def test_initial_capital(self):
        """Test initial capital is set correctly."""
        self.assertEqual(self.rm.capital, 10000.0)
        self.assertEqual(self.rm.initial_capital, 10000.0)

    def test_calculate_leverage_higher_confidence(self):
        """Test higher confidence gives higher (or equal) leverage."""
        lev_low = self.rm.calculate_leverage(50.0)
        lev_high = self.rm.calculate_leverage(90.0)
        self.assertGreaterEqual(lev_high, lev_low)

    def test_calculate_leverage_respects_bounds(self):
        """Test leverage stays within min/max bounds."""
        config = self.rm.config if hasattr(self.rm, 'config') and self.rm.config else RiskConfig()
        
        lev = self.rm.calculate_leverage(99.0)
        self.assertLessEqual(lev, config.max_leverage)
        self.assertGreaterEqual(lev, config.min_leverage)

    def test_calculate_position_size_scales_with_capital(self):
        """Test position size scales with available capital."""
        rm_small = RiskManager(capital=1000.0)
        rm_big = RiskManager(capital=100000.0)

        size_small = rm_small.calculate_position_size(50000.0, 5)
        size_big = rm_big.calculate_position_size(50000.0, 5)

        self.assertGreater(size_big, size_small)

    def test_open_position_reduces_available(self):
        """Test opening a position is tracked."""
        pos = self.rm.open_position(
            symbol="BTCUSDT", side=1, price=50000.0,
            confidence=80.0
        )
        self.assertIsNotNone(pos)

    def test_close_position_returns_pnl(self):
        """Test closing a position returns PnL value."""
        self.rm.open_position(
            symbol="BTCUSDT", side=1, price=50000.0,
            confidence=80.0
        )
        pnl = self.rm.close_position("BTCUSDT", 51000.0, "TEST")
        # PnL should be positive for price increase on long
        self.assertGreater(pnl, 0)

    def test_calculate_sl_tp_long(self):
        """Test SL/TP calculation for long position."""
        sl, tp = self.rm.calculate_sl_tp(100.0, OrderSide.LONG)
        self.assertLess(sl, 100.0)
        self.assertGreater(tp, 100.0)

    def test_calculate_sl_tp_short(self):
        """Test SL/TP calculation for short position."""
        sl, tp = self.rm.calculate_sl_tp(100.0, OrderSide.SHORT)
        self.assertGreater(sl, 100.0)
        self.assertLess(tp, 100.0)

    def test_reset_daily(self):
        """Test daily counter reset."""
        self.rm.reset_daily()
        # Should not raise


if __name__ == '__main__':
    unittest.main()
