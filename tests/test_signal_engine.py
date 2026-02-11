"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    SIGNAL ENGINE TESTS                                      ║
║  Tests for dual-timeframe signal generation and edge cases                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
from pathlib import Path
import unittest
import pandas as pd
import numpy as np

# Add root to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from live.signal_engine import SignalEngine, IndicatorCalculator


class TestIndicatorCalculator(unittest.TestCase):
    """Tests for the IndicatorCalculator class."""

    def setUp(self):
        self.calc = IndicatorCalculator()
        self.days = 200
        np.random.seed(42)

    def _make_ohlcv(self, n: int = 200, base_price: float = 100.0) -> pd.DataFrame:
        """Generate synthetic OHLCV data."""
        close = base_price + np.cumsum(np.random.randn(n) * 0.5)
        close = np.maximum(close, 1.0)  # Prevent negative prices
        high = close * (1 + np.random.uniform(0.001, 0.02, n))
        low = close * (1 - np.random.uniform(0.001, 0.02, n))
        open_ = close + np.random.randn(n) * 0.3
        volume = np.random.uniform(1000, 50000, n)

        return pd.DataFrame({
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    def test_1h_indicators_adds_expected_columns(self):
        """Test that add_1h_indicators adds all expected indicator columns."""
        df = self._make_ohlcv(200)
        result = self.calc.add_1h_indicators(df)

        expected_cols = ['EMA_8', 'EMA_21', 'EMA_50', 'st_dir']
        for col in expected_cols:
            self.assertIn(col, result.columns, f"Missing column: {col}")

    def test_15m_indicators_adds_expected_columns(self):
        """Test that add_15m_indicators adds all expected indicator columns."""
        df = self._make_ohlcv(200)
        result = self.calc.add_15m_indicators(df)

        expected_cols = ['EMA_13', 'RSI', 'ATR']
        for col in expected_cols:
            self.assertIn(col, result.columns, f"Missing column: {col}")

    def test_rsi_values_in_valid_range(self):
        """Test that RSI values are between 0 and 100."""
        df = self._make_ohlcv(200)
        result = self.calc.add_15m_indicators(df)

        rsi_valid = result['RSI'].dropna()
        self.assertTrue((rsi_valid >= 0).all(), "RSI below 0 found")
        self.assertTrue((rsi_valid <= 100).all(), "RSI above 100 found")

    def test_indicators_with_minimal_data(self):
        """Test indicator calculation with very few candles (edge case)."""
        df = self._make_ohlcv(20)
        # Should not crash, even with insufficient data for some indicators
        result = self.calc.add_1h_indicators(df)
        self.assertEqual(len(result), 20)


class TestSignalEngine(unittest.TestCase):
    """Tests for the SignalEngine class."""

    def setUp(self):
        self.engine = SignalEngine()
        np.random.seed(42)

    def _make_ohlcv(self, n: int = 200, base_price: float = 100.0,
                    trend: str = 'up') -> pd.DataFrame:
        """Generate synthetic OHLCV data with a directional trend."""
        if trend == 'up':
            drift = 0.002
        elif trend == 'down':
            drift = -0.002
        else:
            drift = 0.0

        returns = drift + np.random.randn(n) * 0.01
        close = base_price * np.cumprod(1 + returns)
        high = close * (1 + np.random.uniform(0.001, 0.02, n))
        low = close * (1 - np.random.uniform(0.001, 0.02, n))
        open_ = close + np.random.randn(n) * 0.3
        volume = np.random.uniform(1000, 50000, n)

        return pd.DataFrame({
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    def test_process_returns_valid_signal(self):
        """Test that process() returns a valid signal dict."""
        df_1h = self._make_ohlcv(200, trend='up')
        df_15m = self._make_ohlcv(200, trend='up')

        signal = self.engine.process("BTCUSDT", df_1h, df_15m)

        self.assertIn('symbol', signal)
        self.assertEqual(signal['symbol'], 'BTCUSDT')
        self.assertIn('signal', signal)
        self.assertIn(signal['signal'], ['LONG', 'SHORT', 'HOLD', 'WAIT', 'BUY', 'SELL'])

    def test_process_with_flat_market(self):
        """Test signal generation in sideways market."""
        df_1h = self._make_ohlcv(200, trend='flat')
        df_15m = self._make_ohlcv(200, trend='flat')

        signal = self.engine.process("ETHUSDT", df_1h, df_15m)

        self.assertIn('signal', signal)
        # Flat market should typically produce HOLD or WAIT
        self.assertIn(signal['signal'], ['LONG', 'SHORT', 'HOLD', 'WAIT', 'BUY', 'SELL'])

    def test_generate_signal_compatibility(self):
        """Test generate_signal wrapper works like process()."""
        df_15m = self._make_ohlcv(200, trend='up')

        signal = self.engine.generate_signal("SOLUSDT", df=df_15m)

        self.assertIn('symbol', signal)
        self.assertEqual(signal['symbol'], 'SOLUSDT')
        self.assertIn('signal', signal)

    def test_last_signal_tracking(self):
        """Test that last signals are tracked per symbol."""
        df_1h = self._make_ohlcv(200, trend='up')
        df_15m = self._make_ohlcv(200, trend='up')

        self.engine.process("BTCUSDT", df_1h, df_15m)

        last = self.engine.get_last_signal("BTCUSDT")
        self.assertIsNotNone(last)
        self.assertEqual(last['symbol'], 'BTCUSDT')

    def test_callback_fires_on_signal(self):
        """Test that callbacks are invoked when signals are generated."""
        received_signals = []

        def on_signal(signal):
            received_signals.append(signal)

        self.engine.add_callback(on_signal)

        df_1h = self._make_ohlcv(200, trend='up')
        df_15m = self._make_ohlcv(200, trend='up')

        self.engine.process("BTCUSDT", df_1h, df_15m)

        self.assertGreaterEqual(len(received_signals), 1)

    def test_1h_direction_returns_valid_values(self):
        """Test get_1h_direction returns -1, 0, or 1."""
        df_1h = self._make_ohlcv(200, trend='up')
        df_1h = self.engine.calc.add_1h_indicators(df_1h)

        direction = self.engine.get_1h_direction(df_1h)
        self.assertIn(direction, [-1, 0, 1])

    def test_signal_includes_confidence(self):
        """Test that non-HOLD signals include confidence."""
        df_1h = self._make_ohlcv(200, trend='up')
        df_15m = self._make_ohlcv(200, trend='up')

        signal = self.engine.process("BTCUSDT", df_1h, df_15m)

        if signal['signal'] in ['LONG', 'SHORT']:
            self.assertIn('confidence', signal)
            self.assertGreater(signal['confidence'], 0)


if __name__ == '__main__':
    unittest.main()
