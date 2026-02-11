"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       BOT_ALGO TEST SUITE                                     ║
║                                                                               ║
║  Comprehensive tests for all trading system components.                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Run: python tests/test_all.py

Author: Bot_Algo
Last Updated: January 2026
"""

import os
import sys
import unittest
import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)


# ═══════════════════════════════════════════════════════════════════════════════
#                           TEST DATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_test_data(days: int = 100, trend: str = 'up') -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=days, freq='D')
    
    if trend == 'up':
        base = 40000 * np.cumprod(1 + 0.001 + np.random.randn(days) * 0.015)
    elif trend == 'down':
        base = 40000 * np.cumprod(1 - 0.001 + np.random.randn(days) * 0.015)
    else:
        base = 40000 * (1 + np.random.randn(days) * 0.02)
    
    df = pd.DataFrame({
        'open': base,
        'high': base * (1 + np.abs(np.random.randn(days)) * 0.01),
        'low': base * (1 - np.abs(np.random.randn(days)) * 0.01),
        'close': base * (1 + np.random.randn(days) * 0.005),
        'volume': np.random.randint(10000, 100000, days)
    }, index=dates)
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#                           COST MODULE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBinanceCosts(unittest.TestCase):
    """Tests for Binance futures cost calculator."""
    
    def setUp(self):
        from core.costs.binance_costs import BinanceFuturesCosts
        self.calc = BinanceFuturesCosts('BTCUSDT')
    
    def test_trade_cost_calculation(self):
        """Test basic trade cost calculation."""
        costs = self.calc.calculate_trade_cost(
            entry_price=45000,
            quantity=0.1,
            leverage=10
        )
        
        self.assertIn('notional_value', costs)
        self.assertIn('trading_fee_entry', costs)
        self.assertIn('total_round_trip', costs)
        
        self.assertEqual(costs['notional_value'], 4500)
        self.assertGreater(costs['trading_fee_entry'], 0)
    
    def test_leverage_limits(self):
        """Test leverage is capped at maximum."""
        costs = self.calc.calculate_trade_cost(
            entry_price=45000,
            quantity=0.1,
            leverage=200  # Over max
        )
        
        self.assertLessEqual(costs['leverage'], self.calc.max_leverage)
    
    def test_funding_cost(self):
        """Test funding cost calculation."""
        costs = self.calc.calculate_trade_cost(
            entry_price=45000,
            quantity=0.1,
            leverage=10,
            holding_hours=24  # 3 funding periods
        )
        
        self.assertIn('funding_cost', costs)
        self.assertEqual(costs['funding_periods'], 3)


class TestSlippage(unittest.TestCase):
    """Tests for slippage simulator."""
    
    def setUp(self):
        from core.validation.slippage import SlippageSimulator, OrderType
        self.sim = SlippageSimulator('BTCUSDT')
        self.OrderType = OrderType
    
    def test_market_order_slippage(self):
        """Test market order slippage is applied."""
        result = self.sim.calculate(
            price=45000,
            size=1.0,
            order_type=self.OrderType.MARKET,
            is_buy=True
        )
        
        self.assertIn('slippage_pct', result)
        self.assertIn('execution_price', result)
        self.assertGreater(result['execution_price'], 45000)  # Buyer pays more
    
    def test_limit_order_lower_slippage(self):
        """Test limit orders have lower slippage than market on average."""
        # Run multiple times to account for randomness
        market_slippages = []
        limit_slippages = []
        for _ in range(10):
            market = self.sim.calculate(45000, 1.0, self.OrderType.MARKET, True)
            limit = self.sim.calculate(45000, 1.0, self.OrderType.LIMIT, True)
            market_slippages.append(market['slippage_pct'])
            limit_slippages.append(limit['slippage_pct'])
        
        avg_market = sum(market_slippages) / len(market_slippages)
        avg_limit = sum(limit_slippages) / len(limit_slippages)
        self.assertLess(avg_limit, avg_market)


# ═══════════════════════════════════════════════════════════════════════════════
#                           STRATEGY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrendFollower(unittest.TestCase):
    """Tests for Trend Follower V2 strategy."""
    
    def test_signal_generation(self):
        """Test signal generation returns valid values."""
        from strategies.trend_follower_v2 import generate_signals_v2
        
        df = generate_test_data(100, 'up')
        signals = generate_signals_v2(df)
        
        self.assertEqual(len(signals), len(df))
        self.assertTrue(all(s in [-1, 0, 1] for s in signals.unique()))
    
    def test_fixed_parameters(self):
        """Test optimization returns fixed params."""
        from strategies.trend_follower_v2 import optimize_parameters_v2, FIXED_PARAMS
        
        df = generate_test_data(100)
        params = optimize_parameters_v2(df)
        
        self.assertEqual(params, FIXED_PARAMS)


class TestMeanReversion(unittest.TestCase):
    """Tests for Mean Reversion SOL strategy."""
    
    def test_signal_generation(self):
        """Test signal generation."""
        from strategies.mean_reversion_sol import generate_signals_mr
        
        df = generate_test_data(100, 'ranging')
        signals = generate_signals_mr(df)
        
        self.assertEqual(len(signals), len(df))
        self.assertTrue(all(s in [-1, 0, 1] for s in signals.unique()))


class TestRegimeFilter(unittest.TestCase):
    """Tests for market regime filter."""
    
    def test_regime_detection(self):
        """Test regime detection adds column."""
        from core.regime_filter import RegimeFilter
        
        filter = RegimeFilter()
        df = generate_test_data(100, 'up')
        df = filter.detect_regime(df)
        
        self.assertIn('regime', df.columns)
        self.assertIn('ADX', df.columns)
    
    def test_regime_values(self):
        """Test regime values are valid."""
        from core.regime_filter import RegimeFilter, MarketRegime
        
        filter = RegimeFilter()
        df = generate_test_data(100)
        df = filter.detect_regime(df)
        
        valid_regimes = [r.value for r in MarketRegime]
        self.assertTrue(all(r in valid_regimes for r in df['regime'].dropna().unique()))


# ═══════════════════════════════════════════════════════════════════════════════
#                           VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWalkForward(unittest.TestCase):
    """Tests for Walk-Forward Optimization."""
    
    def test_wfo_config(self):
        """Test WFO config defaults."""
        from core.validation.walk_forward import WFOConfig
        
        config = WFOConfig()
        
        self.assertEqual(config.train_ratio + config.validation_ratio + 
                        config.holdout_ratio, 1.0)
    
    def test_wfo_initialization(self):
        """Test WFO can be initialized."""
        from core.validation.walk_forward import WalkForwardOptimizer, WFOConfig
        from strategies.trend_follower_v2 import generate_signals_v2, optimize_parameters_v2
        
        df = generate_test_data(200)
        
        wfo = WalkForwardOptimizer(
            data=df,
            strategy_func=generate_signals_v2,
            optimize_func=optimize_parameters_v2,
            config=WFOConfig(num_folds=2, min_train_samples=50, min_test_samples=20)
        )
        
        self.assertIsNotNone(wfo)


# ═══════════════════════════════════════════════════════════════════════════════
#                           PAPER TRADING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaperTrading(unittest.TestCase):
    """Tests for paper trading engine."""
    
    def setUp(self):
        from core.paper_trading import PaperTradingEngine
        self.engine = PaperTradingEngine(
            initial_balance=1000,
            symbol='BTCUSDT'
        )
    
    def test_initial_balance(self):
        """Test initial balance is set."""
        self.assertEqual(self.engine.balance, 1000)
        self.assertEqual(self.engine.get_equity(), 1000)
    
    def test_place_order(self):
        """Test order placement."""
        order = self.engine.place_order(
            side='buy',
            quantity=0.01,
            price=45000,
            strategy='test'
        )
        
        self.assertEqual(order.status.value, 'filled')
        self.assertIsNotNone(order.fill_price)
        self.assertGreater(order.fill_price, 0)
    
    def test_position_tracking(self):
        """Test position is created after buy."""
        self.engine.place_order('buy', 0.01, 45000, strategy='test')
        
        positions = self.engine.positions
        self.assertEqual(len(positions), 1)
    
    def test_close_position(self):
        """Test position can be closed."""
        self.engine.place_order('buy', 0.01, 45000, strategy='test')
        self.engine.close_position('BTCUSDT', 46000, 'test')
        
        positions = self.engine.positions
        self.assertEqual(len(positions), 0)



# ═══════════════════════════════════════════════════════════════════════════════
#                           LIVE MODULE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestLiveSignalEngine(unittest.TestCase):
    """Tests for live signal engine."""
    
    def setUp(self):
        from live.signal_engine import SignalEngine, IndicatorCalculator
        self.engine = SignalEngine()
        self.calc = IndicatorCalculator()
    
    def test_1h_indicators(self):
        """Test 1hr indicator calculation."""
        df = generate_test_data(100, 'up')
        result = self.calc.add_1h_indicators(df)
        
        self.assertIn('EMA_8', result.columns)
        self.assertIn('EMA_21', result.columns)
        self.assertIn('EMA_50', result.columns)
        self.assertIn('st_dir', result.columns)
    
    def test_15m_indicators(self):
        """Test 15m indicator calculation."""
        df = generate_test_data(100)
        result = self.calc.add_15m_indicators(df)
        
        self.assertIn('EMA_5', result.columns)
        self.assertIn('RSI', result.columns)
        self.assertIn('MACD', result.columns)
        self.assertIn('ATR', result.columns)
    
    def test_signal_generation(self):
        """Test signal generation returns valid structure."""
        df_1h = generate_test_data(100, 'up')
        df_15m = generate_test_data(100, 'up')
        
        signal = self.engine.process('BTCUSDT', df_1h, df_15m)
        
        self.assertIn('symbol', signal)
        self.assertIn('signal', signal)
        self.assertIn(signal['signal'], ['BUY', 'SELL', 'HOLD'])


class TestLivePaperTrader(unittest.TestCase):
    """Tests for live paper trader."""
    
    def setUp(self):
        from live.paper_trader import PaperTrader
        self.trader = PaperTrader(starting_balance=10000.0, min_leverage=5, max_leverage=20)
    
    def test_initial_balance(self):
        """Test initial balance is set correctly."""
        self.assertEqual(self.trader.balance, 10000.0)
        self.assertEqual(self.trader.starting_balance, 10000.0)
    
    def test_open_position(self):
        """Test opening a position."""
        signal = {
            'symbol': 'BTCUSDT',
            'signal': 'BUY',
            'price': 42000.0,
            'conviction': 0.7,
            'atr_pct': 1.5
        }
        
        result = self.trader.open_position(signal)
        
        self.assertTrue(result)
        self.assertTrue(self.trader.has_position('BTCUSDT'))
    
    def test_position_update_and_close(self):
        """Test position update and stop loss."""
        signal = {
            'symbol': 'BTCUSDT',
            'signal': 'BUY',
            'price': 42000.0,
            'conviction': 0.5
        }
        
        self.trader.open_position(signal)
        pos = self.trader.get_position('BTCUSDT')
        
        # Simulate price hitting stop loss
        exit_reason = self.trader.update_position('BTCUSDT', pos.sl_price - 100)
        
        self.assertEqual(exit_reason, 'SL')
        self.assertFalse(self.trader.has_position('BTCUSDT'))
    
    def test_stats_calculation(self):
        """Test stats calculation."""
        stats = self.trader.get_stats()
        
        self.assertIn('total_trades', stats)
        self.assertIn('balance', stats)
        self.assertIn('return_pct', stats)


class TestLiveDashboard(unittest.TestCase):
    """Tests for live dashboard."""
    
    def test_dashboard_creation(self):
        """Test dashboard can be created."""
        from live.dashboard import DashboardManager
        
        dashboard = DashboardManager(starting_balance=10000.0)
        self.assertIsNotNone(dashboard)
    
    def test_signal_update(self):
        """Test signal update."""
        from live.dashboard import DashboardManager
        
        dashboard = DashboardManager()
        dashboard.on_signal({
            'symbol': 'BTCUSDT',
            'signal': 'BUY',
            'direction': 'BULLISH',
            'price': 42000.0,
            'score': 4
        })
        
        self.assertIn('BTCUSDT', dashboard.dashboard.signals)
    
    def test_stats_update(self):
        """Test stats update."""
        from live.dashboard import DashboardManager
        
        dashboard = DashboardManager(starting_balance=10000.0)
        dashboard.on_stats_update({
            'total_trades': 10,
            'win_rate': 60.0,
            'balance': 11000.0
        })
        
        self.assertEqual(dashboard.dashboard.balance, 11000.0)


# ═══════════════════════════════════════════════════════════════════════════════
#                           IRON CONDOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIronCondor(unittest.TestCase):
    """Tests for Iron Condor strategy."""
    
    def test_strike_selection(self):
        """Test strike selection."""
        from strategies.iron_condor import select_iron_condor_strikes, IronCondorConfig
        
        config = IronCondorConfig()
        strikes = select_iron_condor_strikes(19500, config, 'NIFTY')
        
        self.assertIn('short_put', strikes)
        self.assertIn('short_call', strikes)
        self.assertLess(strikes['short_put'], strikes['short_call'])
    
    def test_entry_conditions(self):
        """Test entry condition checking."""
        from strategies.iron_condor import IronCondorStrategy
        
        strategy = IronCondorStrategy(capital=100000)
        
        # Should not enter if VIX too high
        should_enter, reason = strategy.should_enter(19500, 25, 7, 'NIFTY')
        self.assertFalse(should_enter)
        
        # Should enter in low VIX
        should_enter, reason = strategy.should_enter(19500, 12, 7, 'NIFTY')
        self.assertTrue(should_enter)


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """Run all tests and print summary."""
    print("=" * 60)
    print("BOT_ALGO - TEST SUITE")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestBinanceCosts,
        TestSlippage,
        TestTrendFollower,
        TestMeanReversion,
        TestRegimeFilter,
        TestWalkForward,
        TestPaperTrading,
        TestLiveSignalEngine,
        TestLivePaperTrader,
        TestLiveDashboard,
        TestIronCondor,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
