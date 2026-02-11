"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    PAPER TRADER TESTS                                       ║
║  Tests for position lifecycle, PnL, trade logging, and statistics           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
from pathlib import Path
import unittest
import tempfile
import shutil

# Add root to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from live.paper_trader import PaperTrader, Position, Trade


class TestPaperTraderInit(unittest.TestCase):
    """Tests for PaperTrader initialization."""

    def test_default_balance(self):
        """Test default starting balance."""
        trader = PaperTrader()
        self.assertEqual(trader.balance, 100000.0)

    def test_custom_balance(self):
        """Test custom starting balance."""
        trader = PaperTrader(starting_balance=500.0)
        self.assertEqual(trader.balance, 500.0)

    def test_no_initial_positions(self):
        """Test no positions on init."""
        trader = PaperTrader(starting_balance=1000.0)
        self.assertEqual(len(trader.positions), 0)
        self.assertEqual(len(trader.trades), 0)


class TestOpenPosition(unittest.TestCase):
    """Tests for opening positions."""

    def setUp(self):
        self.trader = PaperTrader(starting_balance=10000.0, min_leverage=5, max_leverage=20)
        # Use temp dir for trade logs
        self.tmp_dir = tempfile.mkdtemp()
        self.trader.log_dir = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_signal(self, symbol="BTCUSDT", direction="BUY", price=50000.0, conviction=0.7):
        return {
            "symbol": symbol,
            "signal": direction,
            "price": price,
            "conviction": conviction,
            "atr_pct": 1.0
        }

    def test_open_buy_position(self):
        """Test opening a BUY position."""
        signal = self._make_signal(direction="BUY")
        result = self.trader.open_position(signal)
        self.assertTrue(result)
        self.assertTrue(self.trader.has_position("BTCUSDT"))

    def test_open_sell_position(self):
        """Test opening a SELL position."""
        signal = self._make_signal(direction="SELL")
        result = self.trader.open_position(signal)
        self.assertTrue(result)
        self.assertTrue(self.trader.has_position("BTCUSDT"))

    def test_cannot_open_duplicate(self):
        """Test cannot open duplicate position for same symbol."""
        signal = self._make_signal()
        self.trader.open_position(signal)
        result = self.trader.open_position(signal)
        self.assertFalse(result)

    def test_invalid_direction_rejected(self):
        """Test invalid direction is rejected."""
        signal = self._make_signal(direction="HOLD")
        result = self.trader.open_position(signal)
        self.assertFalse(result)

    def test_slippage_applied_buy(self):
        """Test slippage is applied on BUY (price increases)."""
        signal = self._make_signal(direction="BUY", price=50000.0)
        self.trader.open_position(signal)
        pos = self.trader.get_position("BTCUSDT")
        self.assertGreater(pos.entry_price, 50000.0)

    def test_slippage_applied_sell(self):
        """Test slippage is applied on SELL (price decreases)."""
        signal = self._make_signal(direction="SELL", price=50000.0)
        self.trader.open_position(signal)
        pos = self.trader.get_position("BTCUSDT")
        self.assertLess(pos.entry_price, 50000.0)

    def test_take_profit_set_correctly_buy(self):
        """Test TP is above entry for BUY."""
        signal = self._make_signal(direction="BUY")
        self.trader.open_position(signal)
        pos = self.trader.get_position("BTCUSDT")
        self.assertGreater(pos.tp_price, pos.entry_price)

    def test_stop_loss_set_correctly_buy(self):
        """Test SL is below entry for BUY."""
        signal = self._make_signal(direction="BUY")
        self.trader.open_position(signal)
        pos = self.trader.get_position("BTCUSDT")
        self.assertLess(pos.sl_price, pos.entry_price)


class TestUpdateAndClosePosition(unittest.TestCase):
    """Tests for position updates and closing."""

    def setUp(self):
        self.trader = PaperTrader(starting_balance=10000.0, min_leverage=5, max_leverage=20)
        self.tmp_dir = tempfile.mkdtemp()
        self.trader.log_dir = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _open_buy(self, symbol="BTCUSDT", price=50000.0):
        signal = {
            "symbol": symbol, "signal": "BUY",
            "price": price, "conviction": 0.5
        }
        self.trader.open_position(signal)
        return self.trader.get_position(symbol)

    def test_tp_triggers_close(self):
        """Test take profit triggers position close."""
        pos = self._open_buy()
        # Move price above TP
        tp_hit_price = pos.tp_price * 1.01
        result = self.trader.update_position("BTCUSDT", tp_hit_price)
        self.assertEqual(result, "TP")
        self.assertFalse(self.trader.has_position("BTCUSDT"))

    def test_sl_triggers_close(self):
        """Test stop loss triggers position close."""
        pos = self._open_buy()
        # Move price below SL
        sl_hit_price = pos.sl_price * 0.99
        result = self.trader.update_position("BTCUSDT", sl_hit_price)
        self.assertEqual(result, "SL")
        self.assertFalse(self.trader.has_position("BTCUSDT"))

    def test_no_exit_within_range(self):
        """Test no exit when price is between SL and TP."""
        pos = self._open_buy()
        mid_price = (pos.entry_price + pos.tp_price) / 2
        result = self.trader.update_position("BTCUSDT", mid_price)
        self.assertIsNone(result)
        self.assertTrue(self.trader.has_position("BTCUSDT"))

    def test_timeout_triggers_close(self):
        """Test position closes after max hold candles."""
        self._open_buy()
        mid_price = 50050.0
        for _ in range(self.trader.max_hold_candles):
            result = self.trader.update_position("BTCUSDT", mid_price)
            if result is not None:
                break
        # Should eventually timeout
        self.assertFalse(self.trader.has_position("BTCUSDT"))

    def test_trade_recorded_on_close(self):
        """Test trade is recorded after closing."""
        pos = self._open_buy()
        self.trader.close_position("BTCUSDT", pos.tp_price, "TEST")
        self.assertEqual(len(self.trader.trades), 1)
        self.assertEqual(self.trader.trades[0].exit_reason, "TEST")

    def test_balance_updates_on_close(self):
        """Test balance changes after closing position."""
        initial = self.trader.balance
        pos = self._open_buy()
        # Close at higher price (should be profitable)
        self.trader.close_position("BTCUSDT", pos.entry_price * 1.02, "TP")
        self.assertNotEqual(self.trader.balance, initial)

    def test_update_nonexistent_position(self):
        """Test updating a position that doesn't exist returns None."""
        result = self.trader.update_position("NONEXIST", 50000.0)
        self.assertIsNone(result)


class TestPaperTraderStats(unittest.TestCase):
    """Tests for trading statistics."""

    def setUp(self):
        self.trader = PaperTrader(starting_balance=10000.0, min_leverage=5, max_leverage=20)
        self.tmp_dir = tempfile.mkdtemp()
        self.trader.log_dir = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_empty_stats(self):
        """Test stats with no trades."""
        stats = self.trader.get_stats()
        self.assertEqual(stats['total_trades'], 0)
        self.assertEqual(stats['return_pct'], 0)

    def test_stats_after_trade(self):
        """Test stats after completing a trade."""
        signal = {
            "symbol": "BTCUSDT", "signal": "BUY",
            "price": 50000.0, "conviction": 0.5
        }
        self.trader.open_position(signal)
        pos = self.trader.get_position("BTCUSDT")
        self.trader.close_position("BTCUSDT", pos.entry_price * 1.02, "TP")

        stats = self.trader.get_stats()
        self.assertEqual(stats['total_trades'], 1)
        self.assertGreater(stats['total_pnl'], 0)

    def test_callbacks_fire(self):
        """Test callbacks fire on open and close."""
        events = []

        def on_event(event_type, data):
            events.append(event_type)

        self.trader.add_callback(on_event)

        signal = {
            "symbol": "BTCUSDT", "signal": "BUY",
            "price": 50000.0, "conviction": 0.5
        }
        self.trader.open_position(signal)
        pos = self.trader.get_position("BTCUSDT")
        self.trader.close_position("BTCUSDT", pos.entry_price * 1.02, "TP")

        self.assertIn("OPEN", events)
        self.assertIn("CLOSE", events)


if __name__ == '__main__':
    unittest.main()
