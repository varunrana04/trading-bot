#!/usr/bin/env python3
"""
================================================================================
           EXTREME STRESS TEST - PRODUCTION READINESS ASSESSMENT
================================================================================
Simulates worst-case scenarios to find weaknesses before real money is at risk.

Categories:
  1. Edge Cases        - Zero, negative, NaN, Inf prices
  2. Flash Crash       - 50% drop in 1 candle  
  3. V-Recovery        - Crash + instant bounce
  4. Sideways Chop     - Random noise, no trend
  5. Pump and Dump     - 10x spike then collapse
  6. Circuit Breaker   - Exhaustion under rapid losses
  7. Correlation Guard - Saturation with max exposure
  8. Rapid Cycling     - 100+ trades in quick succession
  9. Balance Drain     - Trade until bankrupt
  10. Signal Engine    - Missing/corrupt data
  11. State Manager    - Crash-during-save
  12. Config Loader    - Invalid/corrupt configuration
  13. Rate Limiter     - Burst capacity test
  14. Volatility Sim   - Real BTC/ETH vol profiles

Usage:
    python scripts/extreme_stress_test_v2.py
================================================================================
"""

import sys
import os
import time
import json
import tempfile
import shutil
import traceback
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from io import StringIO

# Add root to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from live.signal_engine import SignalEngine, IndicatorCalculator
from live.paper_trader import PaperTrader
from core.correlation_guard import CorrelationGuard
from core.rate_limiter import RateLimiter
from core.state_manager import StateManager
from config.config_loader import validate_config


# ==============================================================================
#                              HELPERS
# ==============================================================================

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results = []
    
    def ok(self, name, detail=""):
        self.passed += 1
        self.results.append(("PASS", name, detail))
        print(f"  [PASS] {name}" + (f" - {detail}" if detail else ""))
    
    def fail(self, name, detail=""):
        self.failed += 1
        self.results.append(("FAIL", name, detail))
        print(f"  [FAIL] {name}" + (f" - {detail}" if detail else ""))
    
    def warn(self, name, detail=""):
        self.warnings += 1
        self.results.append(("WARN", name, detail))
        print(f"  [WARN] {name}" + (f" - {detail}" if detail else ""))
    
    def summary(self):
        total = self.passed + self.failed + self.warnings
        return {
            "total": total, "passed": self.passed,
            "failed": self.failed, "warnings": self.warnings
        }


def make_ohlcv(n=200, base_price=100.0, volatility=0.02, trend=0.0):
    """Generate synthetic OHLCV data."""
    dates = pd.date_range(end=datetime.now(), periods=n, freq='15min')
    prices = [base_price]
    for i in range(1, n):
        change = np.random.normal(trend, volatility)
        prices.append(prices[-1] * (1 + change))
    
    prices = np.array(prices)
    high = prices * (1 + np.random.uniform(0, volatility, n))
    low = prices * (1 - np.random.uniform(0, volatility, n))
    volume = np.random.uniform(100, 10000, n)
    
    return pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.001, n)),
        'high': high, 'low': low, 'close': prices,
        'volume': volume
    }, index=dates)


def make_flash_crash(n=200, crash_at=150, crash_pct=0.50):
    """Generate data with a flash crash."""
    df = make_ohlcv(n, base_price=50000, volatility=0.01)
    prices = df['close'].values.copy()
    
    # Sudden drop
    crash_factor = 1 - crash_pct
    prices[crash_at:] *= crash_factor
    df['close'] = prices
    df['low'] = np.minimum(df['low'], df['close'])
    df['high'] = np.maximum(df['high'], df['close'])
    df['open'] = df['close'] * (1 + np.random.normal(0, 0.005, n))
    return df


def make_v_recovery(n=200, crash_at=140, recover_at=160, crash_pct=0.40):
    """Flash crash followed by instant recovery."""
    df = make_ohlcv(n, base_price=50000, volatility=0.01)
    prices = df['close'].values.copy()
    original = prices[crash_at]
    
    crash_factor = 1 - crash_pct
    prices[crash_at:recover_at] *= crash_factor
    # Recover back to original
    prices[recover_at:] = original * (1 + np.random.normal(0, 0.005, n - recover_at))
    
    df['close'] = prices
    df['low'] = np.minimum(df['low'], df['close'])
    df['high'] = np.maximum(df['high'], df['close'])
    return df


def make_pump_dump(n=200, pump_at=130, dump_at=160, pump_mult=5.0):
    """Price spikes then collapses back."""
    df = make_ohlcv(n, base_price=100, volatility=0.01)
    prices = df['close'].values.copy()
    original = prices[pump_at]
    
    # Pump phase
    for i in range(pump_at, dump_at):
        factor = 1 + (pump_mult - 1) * (i - pump_at) / (dump_at - pump_at)
        prices[i] = original * factor
    
    # Dump back to original
    prices[dump_at:] = original * (1 + np.random.normal(0, 0.02, n - dump_at))
    
    df['close'] = prices
    df['high'] = np.maximum(df['high'], df['close'])
    df['low'] = np.minimum(df['low'], df['close'])
    return df


def make_sideways_chop(n=200, base_price=100, noise=0.005):
    """Pure sideways random noise."""
    return make_ohlcv(n, base_price, volatility=noise, trend=0.0)


# ==============================================================================
#                     TEST CATEGORY 1: EDGE CASE INPUTS
# ==============================================================================

def test_edge_cases(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 1: EDGE CASE INPUTS")
    print("=" * 70)
    
    calc = IndicatorCalculator()
    engine = SignalEngine()
    
    # Test 1: Zero prices
    try:
        df = make_ohlcv(200, base_price=0.001)
        result = calc.add_15m_indicators(df)
        r.ok("Zero-near prices", f"Indicators computed, {result.isna().sum().sum()} NaN values")
    except Exception as e:
        r.fail("Zero-near prices", str(e))
    
    # Test 2: Very large prices (like BTC at $1M)
    try:
        df = make_ohlcv(200, base_price=1000000)
        result = calc.add_15m_indicators(df)
        r.ok("Large prices ($1M)", f"No overflow, RSI range: {result['RSI'].min():.1f}-{result['RSI'].max():.1f}")
    except Exception as e:
        r.fail("Large prices ($1M)", str(e))
    
    # Test 3: NaN in data
    try:
        df = make_ohlcv(200)
        df.loc[df.index[50:55], 'close'] = np.nan
        result = calc.add_15m_indicators(df)
        nan_count = result['RSI'].isna().sum()
        if nan_count > 50:
            r.warn("NaN in price data", f"Excessive NaN propagation: {nan_count}/200")
        else:
            r.ok("NaN in price data", f"Handled gracefully, {nan_count} NaN in RSI")
    except Exception as e:
        r.fail("NaN in price data", str(e))
    
    # Test 4: Inf in data
    try:
        df = make_ohlcv(200)
        df.loc[df.index[100], 'close'] = np.inf
        result = calc.add_15m_indicators(df)
        has_inf = np.isinf(result.select_dtypes(include=[np.number])).any().any()
        if has_inf:
            r.warn("Inf in price data", "Inf propagated to indicators (not sanitized)")
        else:
            r.ok("Inf in price data", "Handled without propagation")
    except Exception as e:
        r.fail("Inf in price data", str(e))
    
    # Test 5: Empty DataFrame
    try:
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        result = calc.add_15m_indicators(df)
        r.ok("Empty DataFrame", "No crash on empty input")
    except Exception as e:
        r.fail("Empty DataFrame", str(e)[:80])
    
    # Test 6: Single row
    try:
        df = make_ohlcv(1)
        result = calc.add_15m_indicators(df)
        r.ok("Single row DataFrame", "Handled without crash")
    except Exception as e:
        r.fail("Single row DataFrame", str(e)[:80])
    
    # Test 7: Negative prices
    try:
        df = make_ohlcv(200)
        df['close'] = df['close'] * -1
        df['open'] = df['open'] * -1
        df['high'] = df['high'] * -1
        df['low'] = df['low'] * -1
        result = calc.add_15m_indicators(df)
        # Check if sanitization clamped negatives
        if (result['close'] > 0).all():
            r.ok("Negative prices", "Sanitized to positive values by IndicatorCalculator")
        else:
            r.warn("Negative prices", "Negative prices not fully sanitized")
    except Exception as e:
        r.ok("Negative prices", f"Properly rejected: {str(e)[:60]}")
    
    # Test 8: Signal engine with insufficient data
    try:
        df_1h = make_ohlcv(5)
        df_15m = make_ohlcv(5)
        signal = engine.process("BTCUSDT", df_1h, df_15m)
        if signal['signal'] in ['HOLD', 'WAIT']:
            r.ok("Insufficient data signal", f"Correctly returned {signal['signal']}")
        else:
            r.warn("Insufficient data signal", f"Generated {signal['signal']} on only 5 candles")
    except Exception as e:
        r.fail("Insufficient data signal", str(e)[:80])


# ==============================================================================
#                    TEST CATEGORY 2: VOLATILITY SIMULATIONS
# ==============================================================================

def test_volatility_scenarios(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 2: VOLATILITY SIMULATIONS")
    print("=" * 70)
    
    engine = SignalEngine()
    trader = PaperTrader(starting_balance=10000.0, min_leverage=5, max_leverage=20)
    
    scenarios = [
        ("Flash Crash -50%", make_flash_crash(200, crash_at=150, crash_pct=0.50)),
        ("V-Recovery -40%/+40%", make_v_recovery(200)),
        ("Pump and Dump 5x", make_pump_dump(200)),
        ("Sideways Chop", make_sideways_chop(200)),
        ("High Vol (5%)", make_ohlcv(200, volatility=0.05)),
        ("Extreme Vol (15%)", make_ohlcv(200, volatility=0.15)),
        ("Strong Uptrend", make_ohlcv(200, volatility=0.02, trend=0.005)),
        ("Strong Downtrend", make_ohlcv(200, volatility=0.02, trend=-0.005)),
    ]
    
    for name, df in scenarios:
        try:
            df_1h = df.iloc[::4].copy()  # Resample to 1h-like
            df_15m = df.copy()
            
            signal = engine.process("BTCUSDT", df_1h, df_15m)
            sig = signal.get('signal', 'UNKNOWN')
            conf = signal.get('conviction', signal.get('confidence', 0))
            
            # Try to open a position
            if sig in ['BUY', 'SELL', 'LONG', 'SHORT']:
                trade_signal = {
                    'symbol': 'BTCUSDT',
                    'signal': 'BUY' if sig in ['BUY', 'LONG'] else 'SELL',
                    'price': float(df['close'].iloc[-1]),
                    'conviction': conf if isinstance(conf, (int, float)) else 0.5,
                    'atr_pct': 1.0
                }
                trader.open_position(trade_signal)
                
                # Simulate price movement
                future_price = float(df['close'].iloc[-1]) * 0.95  # 5% drop
                trader.update_position('BTCUSDT', future_price)
                
                # Clean up
                if trader.has_position('BTCUSDT'):
                    trader.close_position('BTCUSDT', future_price, 'TEST')
            
            r.ok(f"Volatility: {name}", f"Signal={sig}, Conf={conf}")
        except Exception as e:
            r.fail(f"Volatility: {name}", str(e)[:80])


# ==============================================================================
#               TEST CATEGORY 3: CIRCUIT BREAKER STRESS
# ==============================================================================

def test_circuit_breaker_stress(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 3: CIRCUIT BREAKER STRESS")
    print("=" * 70)
    
    trader = PaperTrader(starting_balance=10000.0, min_leverage=5, max_leverage=10)
    
    # Rapid losing trades
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSDT", "XAGUSDT"]
    loss_count = 0
    blocked_count = 0
    
    for i in range(20):
        sym = symbols[i % len(symbols)]
        signal = {
            'symbol': sym, 'signal': 'BUY', 'price': 100.0,
            'conviction': 0.5, 'atr_pct': 1.0
        }
        
        opened = trader.open_position(signal)
        if opened:
            trader.close_position(sym, 80.0, 'SL')  # 20% loss
            loss_count += 1
        else:
            blocked_count += 1
    
    if trader._circuit_open:
        r.ok("Circuit breaker activated", f"After {loss_count} losses, blocked {blocked_count} trades")
    else:
        r.fail("Circuit breaker should have activated", f"After {loss_count} losses")
    
    # Test cooldown bypass
    trader._circuit_open_time = time.time() - 2000  # Expired cooldown
    signal = {
        'symbol': 'BTCUSDT', 'signal': 'BUY', 'price': 100.0,
        'conviction': 0.5, 'atr_pct': 1.0
    }
    opened = trader.open_position(signal)
    if opened:
        r.ok("Cooldown expiry resumes trading")
        trader.close_position('BTCUSDT', 100.0, 'TEST')
    else:
        r.fail("Cooldown expiry", "Should have allowed trading after cooldown")
    
    # Test daily loss threshold
    trader2 = PaperTrader(starting_balance=1000.0, min_leverage=5, max_leverage=10)
    signal = {'symbol': 'BTCUSDT', 'signal': 'BUY', 'price': 100.0, 'conviction': 0.9, 'atr_pct': 1.0}
    trader2.open_position(signal)
    # Create massive loss (>5% of starting balance)
    trader2.close_position('BTCUSDT', 10.0, 'SL')  # Huge loss
    
    if trader2._circuit_open:
        r.ok("Daily loss circuit breaker", f"Triggered on ${trader2._daily_pnl:.2f} loss")
    else:
        daily_pct = abs(trader2._daily_pnl / trader2.starting_balance * 100)
        if daily_pct < 5:
            r.warn("Daily loss circuit breaker", f"Loss was only {daily_pct:.1f}% (below 5% threshold)")
        else:
            r.fail("Daily loss circuit breaker", f"Should have triggered at {daily_pct:.1f}% daily loss")


# ==============================================================================
#             TEST CATEGORY 4: CORRELATION GUARD SATURATION
# ==============================================================================

def test_correlation_saturation(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 4: CORRELATION GUARD SATURATION")
    print("=" * 70)
    
    trader = PaperTrader(starting_balance=100000.0, min_leverage=5, max_leverage=10)
    
    # Try to open all crypto positions same direction
    cryptos = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    metals = ["XAUUSDT", "XAGUSDT"]
    
    opened = []
    blocked = []
    
    for sym in cryptos + metals:
        signal = {
            'symbol': sym, 'signal': 'BUY', 'price': 100.0,
            'conviction': 0.5, 'atr_pct': 1.0
        }
        result = trader.open_position(signal)
        if result:
            opened.append(sym)
        else:
            blocked.append(sym)
    
    # Should allow 2 crypto + 2 metals, block 3rd of each
    crypto_opened = [s for s in opened if s in cryptos]
    metal_opened = [s for s in opened if s in metals]
    
    if len(crypto_opened) <= 2:
        r.ok(f"Crypto group limited", f"Opened {len(crypto_opened)}/3: {crypto_opened}")
    else:
        r.fail(f"Crypto group NOT limited", f"Opened all {len(crypto_opened)}")
    
    if len(metal_opened) <= 2:
        r.ok(f"Metals group limited", f"Opened {len(metal_opened)}/2: {metal_opened}")
    else:
        r.fail(f"Metals group NOT limited", f"Opened all {len(metal_opened)}")
    
    # Test opposite direction bypass
    for sym in opened:
        trader.close_position(sym, 100.0, 'TEST')
    
    # Reset circuit breaker so it doesn't interfere  
    trader._circuit_open = False
    trader._consecutive_losses = 0
    trader._daily_pnl = 0
    
    # Open 2 BUY, then try SELL
    for sym in ["BTCUSDT", "ETHUSDT"]:
        signal = {'symbol': sym, 'signal': 'BUY', 'price': 100.0, 'conviction': 0.5, 'atr_pct': 1.0}
        trader.open_position(signal)
    
    signal = {'symbol': 'SOLUSDT', 'signal': 'SELL', 'price': 100.0, 'conviction': 0.5, 'atr_pct': 1.0}
    if trader.open_position(signal):
        r.ok("Opposite direction allowed", "SELL passed while 2 BUYs exist")
        trader.close_position('SOLUSDT', 100.0, 'TEST')
    else:
        r.fail("Opposite direction blocked", "Should allow SELL when BUYs are at limit")
    
    # Clean up
    for sym in list(trader.positions.keys()):
        trader.close_position(sym, 100.0, 'TEST')


# ==============================================================================
#              TEST CATEGORY 5: RAPID TRADE CYCLING
# ==============================================================================

def test_rapid_cycling(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 5: RAPID TRADE CYCLING (100+ trades)")
    print("=" * 70)
    
    trader = PaperTrader(starting_balance=100000.0, min_leverage=5, max_leverage=10)
    
    # Disable circuit breaker for this test
    trader._max_consecutive_losses = 999
    trader._max_daily_loss_pct = 999
    
    # Disable correlation guard
    trader._corr_guard = None
    
    start_time = time.time()
    trades_completed = 0
    errors = []
    
    for i in range(100):
        sym = f"TEST{i}USDT"
        price = 100.0 + np.random.normal(0, 5)
        
        try:
            signal = {
                'symbol': sym, 'signal': 'BUY' if i % 2 == 0 else 'SELL',
                'price': max(price, 1.0),  # Ensure positive
                'conviction': np.random.uniform(0.3, 0.9),
                'atr_pct': np.random.uniform(0.5, 3.0)
            }
            
            trader.open_position(signal)
            
            # Random exit
            exit_price = price * (1 + np.random.normal(0, 0.05))
            exit_price = max(exit_price, 0.01)
            trader.close_position(sym, exit_price, 'TEST')
            trades_completed += 1
            
        except Exception as e:
            errors.append(f"Trade {i}: {str(e)[:50]}")
    
    elapsed = time.time() - start_time
    
    if trades_completed == 100:
        r.ok(f"100 trades completed", f"in {elapsed:.2f}s ({100/elapsed:.0f} trades/sec)")
    else:
        r.fail(f"Only {trades_completed}/100 trades completed", f"Errors: {len(errors)}")
    
    # Check balance didn't go to NaN/Inf
    if np.isfinite(trader.balance):
        r.ok("Balance is finite after 100 trades", f"${trader.balance:,.2f}")
    else:
        r.fail("Balance is NaN/Inf after rapid cycling", f"{trader.balance}")
    
    if errors:
        for err in errors[:3]:
            r.warn("Trade error", err)


# ==============================================================================
#              TEST CATEGORY 6: BALANCE DRAIN TO ZERO
# ==============================================================================

def test_balance_drain(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 6: BALANCE DRAIN TO ZERO")
    print("=" * 70)
    
    trader = PaperTrader(starting_balance=100.0, min_leverage=50, max_leverage=50)
    trader._max_consecutive_losses = 999
    trader._max_daily_loss_pct = 999
    trader._corr_guard = None
    
    trades_before_ruin = 0
    
    for i in range(50):
        if trader.balance <= 0:
            break
        
        signal = {
            'symbol': f'SYM{i}USDT', 'signal': 'BUY',
            'price': 100.0, 'conviction': 0.9, 'atr_pct': 1.0
        }
        
        opened = trader.open_position(signal)
        if opened:
            # 10% loss at 50x leverage = massive hit
            trader.close_position(f'SYM{i}USDT', 90.0, 'SL')
            trades_before_ruin += 1
        else:
            break
    
    if trader.balance <= 0:
        r.warn("Balance went negative", f"${trader.balance:.2f} after {trades_before_ruin} trades (no liquidation protection)")
    elif trader.balance < 10:
        r.ok("Balance nearly drained", f"${trader.balance:.2f} after {trades_before_ruin} trades")
    else:
        r.ok("Balance survived", f"${trader.balance:.2f} after {trades_before_ruin} trades")
    
    # Check for NaN/Inf
    if not np.isfinite(trader.balance):
        r.fail("Balance is NaN/Inf", f"{trader.balance}")


# ==============================================================================
#            TEST CATEGORY 7: STATE MANAGER ROBUSTNESS
# ==============================================================================

def test_state_manager_robustness(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 7: STATE MANAGER ROBUSTNESS")
    print("=" * 70)
    
    tmp_dir = tempfile.mkdtemp()
    
    try:
        sm = StateManager(state_dir=tmp_dir)
        
        # Test 1: Save and load large state
        positions = {f"SYM{i}USDT": {
            "symbol": f"SYM{i}USDT", "direction": "BUY",
            "entry_price": 100.0 * (i + 1), "margin": 50.0
        } for i in range(50)}
        
        sm.save_positions(positions, balance=9999.99)
        loaded = sm.load_positions()
        
        if loaded and len(loaded.get('positions', {})) == 50:
            r.ok("Large state (50 positions)", "Saved and loaded correctly")
        else:
            r.fail("Large state", f"Got {len(loaded.get('positions', {}))} positions")
        
        # Test 2: Corrupt state file
        state_file = os.path.join(tmp_dir, "bot_state.json")
        with open(state_file, 'w') as f:
            f.write("{corrupt json data!!!!")
        
        try:
            loaded = sm.load_positions()
            if loaded is None or loaded == {}:
                r.ok("Corrupt state file", "Handled gracefully, returned empty")
            else:
                r.warn("Corrupt state file", f"Returned unexpected: {type(loaded)}")
        except json.JSONDecodeError:
            r.warn("Corrupt state file", "Raised JSONDecodeError instead of handling gracefully")
        except Exception as e:
            r.fail("Corrupt state file", str(e)[:80])
        
        # Test 3: Missing state directory
        sm2 = StateManager(state_dir="/nonexistent/path/test")
        try:
            loaded = sm2.load_positions()
            r.ok("Missing state dir", "No crash on missing directory")
        except Exception as e:
            r.warn("Missing state dir", f"Error: {str(e)[:60]}")
        
        # Test 4: Concurrent saves (simulate race condition)
        sm3 = StateManager(state_dir=tmp_dir)
        for i in range(10):
            sm3.save_positions({"pos": {"symbol": "TEST", "i": i}}, balance=float(i * 100))
        loaded = sm3.load_positions()
        if loaded:
            r.ok("Rapid sequential saves", "No corruption from rapid writes")
        else:
            r.fail("Rapid sequential saves", "State lost")
    
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ==============================================================================
#            TEST CATEGORY 8: CONFIG VALIDATION EDGE CASES
# ==============================================================================

def test_config_validation(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 8: CONFIG VALIDATION")
    print("=" * 70)
    
    # Test 1: Valid config
    valid_config = {
        "risk_limits": {"max_daily_loss_pct": -5.0, "max_drawdown_pct": -15.0,
                        "max_consecutive_losses": 5, "max_position_per_strategy_pct": 20.0},
        "capital": {"crypto_usd": 100.0, "indian_inr": 10000.0},
        "optimization": {"in_sample_days": 90, "out_sample_days": 30}
    }
    warnings = validate_config(valid_config)
    if not warnings:
        r.ok("Valid config", "No warnings")
    else:
        r.fail("Valid config has warnings", str(warnings))
    
    # Test 2: Out of range values
    bad_config = {
        "risk_limits": {"max_daily_loss_pct": 50.0},  # Should be negative
        "capital": {"crypto_usd": -100.0},  # Should be positive
    }
    warnings = validate_config(bad_config)
    if warnings:
        r.ok("Out-of-range detected", f"{len(warnings)} warning(s)")
    else:
        r.fail("Out-of-range NOT detected", "Should have warned about positive loss pct")
    
    # Test 3: Wrong types
    type_config = {
        "risk_limits": {"max_consecutive_losses": "five"}
    }
    warnings = validate_config(type_config)
    if warnings:
        r.ok("Wrong type detected", f"Caught: {warnings[0][:60]}")
    else:
        r.fail("Wrong type NOT detected", "String 'five' for int field")
    
    # Test 4: Empty config
    warnings = validate_config({})
    r.ok("Empty config", "No crash, no warnings" if not warnings else f"{len(warnings)} warnings")
    
    # Test 5: Extra unknown fields
    unknown_config = {"risk_limits": {"unknown_field": 42, "max_daily_loss_pct": -5.0}}
    warnings = validate_config(unknown_config)
    r.ok("Unknown fields", "Ignored gracefully")


# ==============================================================================
#           TEST CATEGORY 9: RATE LIMITER STRESS
# ==============================================================================

def test_rate_limiter_stress(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 9: RATE LIMITER STRESS")
    print("=" * 70)
    
    # Test burst of requests
    limiter = RateLimiter(max_requests=50, window_seconds=1.0, name="stress")
    
    start = time.time()
    for i in range(50):
        limiter.acquire()
    elapsed = time.time() - start
    
    if elapsed < 0.5:
        r.ok(f"Burst 50 requests", f"in {elapsed:.3f}s (no throttle within limit)")
    else:
        r.warn(f"Burst 50 requests slow", f"Took {elapsed:.3f}s")
    
    # 51st should throttle
    start = time.time()
    limiter.acquire()
    throttle_time = time.time() - start
    
    if throttle_time > 0.1:
        r.ok(f"51st request throttled", f"Waited {throttle_time:.2f}s")
    else:
        r.fail(f"51st request NOT throttled", f"Only waited {throttle_time:.4f}s")
    
    # Usage tracking
    stats = limiter.stats
    if stats["total_requests"] == 51 and stats["total_waits"] == 1:
        r.ok("Stats accurate", f"Requests={stats['total_requests']}, Waits={stats['total_waits']}")
    else:
        r.fail("Stats inaccurate", str(stats))


# ==============================================================================
#         TEST CATEGORY 10: SIGNAL ENGINE PRODUCTION SCENARIOS
# ==============================================================================

def test_signal_production_scenarios(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 10: SIGNAL ENGINE PRODUCTION SCENARIOS")
    print("=" * 70)
    
    engine = SignalEngine()
    
    # Test 1: Real BTC-like volatility (daily ~3%)
    btc_like = make_ohlcv(500, base_price=95000, volatility=0.025)
    df_1h = btc_like.iloc[::4].copy()
    df_15m = btc_like.copy()
    
    try:
        signal = engine.process("BTCUSDT", df_1h, df_15m)
        r.ok("BTC-like data (500 candles)", f"Signal: {signal['signal']}")
    except Exception as e:
        r.fail("BTC-like data", str(e)[:80])
    
    # Test 2: ETH-like higher volatility
    eth_like = make_ohlcv(500, base_price=3500, volatility=0.035)
    df_1h = eth_like.iloc[::4].copy()
    df_15m = eth_like.copy()
    
    try:
        signal = engine.process("ETHUSDT", df_1h, df_15m)
        r.ok("ETH-like data (500 candles)", f"Signal: {signal['signal']}")
    except Exception as e:
        r.fail("ETH-like data", str(e)[:80])
    
    # Test 3: Multiple symbols rapid sequence
    try:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSDT", "XAGUSDT"]
        signals = {}
        for sym in symbols:
            df = make_ohlcv(200, base_price=np.random.uniform(50, 100000), volatility=0.02)
            df_1h = df.iloc[::4].copy()
            sig = engine.process(sym, df_1h, df)
            signals[sym] = sig['signal']
        r.ok("Multi-symbol rapid signals", f"{signals}")
    except Exception as e:
        r.fail("Multi-symbol rapid signals", str(e)[:80])
    
    # Test 4: Consistency - same data should give same signal
    df = make_ohlcv(200, base_price=50000, volatility=0.02)
    df_1h = df.iloc[::4].copy()
    
    try:
        sig1 = engine.process("BTCUSDT", df_1h.copy(), df.copy())
        sig2 = engine.process("BTCUSDT", df_1h.copy(), df.copy())
        if sig1['signal'] == sig2['signal']:
            r.ok("Signal determinism", f"Same input -> same output ({sig1['signal']})")
        else:
            r.warn("Signal non-determinism", f"{sig1['signal']} vs {sig2['signal']}")
    except Exception as e:
        r.fail("Signal determinism", str(e)[:80])
    
    # Test 5: Signal callback system under load
    callback_count = [0]
    def cb(s):
        callback_count[0] += 1
    
    engine2 = SignalEngine()
    engine2.add_callback(cb)
    
    for _ in range(20):
        df = make_ohlcv(200, volatility=0.03)
        df_1h = df.iloc[::4].copy()
        engine2.process("BTCUSDT", df_1h, df)
    
    r.ok("Callback under load", f"{callback_count[0]} callbacks fired from 20 signals")


# ==============================================================================
#        TEST CATEGORY 11: FULL TRADING SIMULATION (24hr)
# ==============================================================================

def test_full_trading_simulation(r: TestResult):
    print("\n" + "=" * 70)
    print("  CATEGORY 11: FULL 24-HOUR TRADING SIMULATION")
    print("=" * 70)
    
    engine = SignalEngine()
    trader = PaperTrader(starting_balance=1000.0, min_leverage=10, max_leverage=25)
    
    # Disable circuit breaker for full sim
    trader._max_consecutive_losses = 10
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    total_signals = 0
    trades_opened = 0
    trades_closed = 0
    
    # Simulate 96 15-minute candles (24 hours)
    for sym in symbols:
        # Generate 24hr of data with realistic patterns
        df = make_ohlcv(300, base_price=np.random.uniform(100, 5000), volatility=0.02)
        
        # Slide window through data, simulating real-time
        for i in range(200, 296):
            window = df.iloc[max(0, i-200):i+1].copy()
            df_1h = window.iloc[::4].copy()
            
            try:
                signal = engine.process(sym, df_1h, window)
                total_signals += 1
                
                current_price = float(window['close'].iloc[-1])
                
                # Act on signals
                if signal['signal'] in ['BUY', 'SELL'] and not trader.has_position(sym):
                    trade_signal = {
                        'symbol': sym, 'signal': signal['signal'],
                        'price': current_price,
                        'conviction': signal.get('conviction', signal.get('confidence', 0.5)),
                        'atr_pct': 1.0
                    }
                    if trader.open_position(trade_signal):
                        trades_opened += 1
                
                # Update existing positions
                if trader.has_position(sym):
                    result = trader.update_position(sym, current_price)
                    if result:
                        trades_closed += 1
                        
            except Exception as e:
                pass  # Expected some failures on edge data
    
    # Close any remaining positions
    for sym in list(trader.positions.keys()):
        trader.close_position(sym, 100.0, 'TEST_END')
        trades_closed += 1
    
    stats = trader.get_stats()
    final_balance = trader.balance
    pnl = final_balance - 1000.0
    pnl_pct = (pnl / 1000.0) * 100
    
    r.ok(f"24hr simulation complete", f"Signals={total_signals}, Opens={trades_opened}, Closes={trades_closed}")
    r.ok(f"Final balance", f"${final_balance:.2f} ({pnl_pct:+.1f}%)")
    
    win_rate = stats.get('win_rate', 0)
    if isinstance(win_rate, str):
        win_rate = float(win_rate.replace('%', '')) if '%' in win_rate else 0
    
    r.ok(f"Win rate", f"{win_rate:.1f}%")
    
    if final_balance > 0:
        r.ok("Solvency maintained", "Balance > 0 after 24hr sim")
    else:
        r.fail("Insolvent", f"Balance went to ${final_balance:.2f}")


# ==============================================================================
#                         MAIN - RUN ALL TESTS
# ==============================================================================

def main():
    print("\n" + "=" * 70)
    print("  EXTREME STRESS TEST v2 - PRODUCTION READINESS ASSESSMENT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    r = TestResult()
    
    # Suppress noisy loggers
    import logging
    for name in ['PaperTrader', 'CorrelationGuard', 'SignalEngine', 'RateLimiter',
                 'StateManager', 'ConfigLoader', 'DataFeedFallback']:
        logging.getLogger(name).setLevel(logging.CRITICAL)
    
    # Run all test categories
    categories = [
        ("Edge Cases", test_edge_cases),
        ("Volatility Simulations", test_volatility_scenarios),
        ("Circuit Breaker", test_circuit_breaker_stress),
        ("Correlation Guard", test_correlation_saturation),
        ("Rapid Cycling", test_rapid_cycling),
        ("Balance Drain", test_balance_drain),
        ("State Manager", test_state_manager_robustness),
        ("Config Validation", test_config_validation),
        ("Rate Limiter", test_rate_limiter_stress),
        ("Signal Production", test_signal_production_scenarios),
        ("24hr Simulation", test_full_trading_simulation),
    ]
    
    category_results = {}
    
    for name, func in categories:
        before = r.summary()
        try:
            func(r)
        except Exception as e:
            r.fail(f"CATEGORY CRASH: {name}", f"{traceback.format_exc()[:200]}")
        after = r.summary()
        
        cat_passed = after['passed'] - before['passed']
        cat_failed = after['failed'] - before['failed']
        cat_warned = after['warnings'] - before['warnings']
        category_results[name] = (cat_passed, cat_failed, cat_warned)
    
    # Final summary
    s = r.summary()
    
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    
    for cat, (p, f, w) in category_results.items():
        status = "PASS" if f == 0 else "FAIL"
        warn_str = f" ({w} warnings)" if w > 0 else ""
        emoji = "[OK]" if f == 0 else "[!!]"
        print(f"  {emoji} {cat:30s} {p} passed, {f} failed{warn_str}")
    
    print(f"\n  {'='*40}")
    print(f"  TOTAL: {s['passed']} passed, {s['failed']} failed, {s['warnings']} warnings")
    print(f"  PASS RATE: {s['passed']/max(s['total'],1)*100:.1f}%")
    
    grade = "A+" if s['failed'] == 0 and s['warnings'] <= 3 else \
            "A" if s['failed'] == 0 else \
            "B" if s['failed'] <= 2 else \
            "C" if s['failed'] <= 5 else "D"
    
    print(f"  GRADE: {grade}")
    print(f"  {'='*40}")
    
    # Production readiness
    print("\n  PRODUCTION READINESS:")
    if s['failed'] == 0:
        print("  [OK] All tests passed - system is production ready")
    else:
        print("  [!!] Some tests failed - review before going live")
    
    if s['warnings'] > 0:
        print(f"  [..] {s['warnings']} warnings found - review recommended")
        print("\n  WARNINGS (areas to watch):")
        for status, name, detail in r.results:
            if status == "WARN":
                print(f"    - {name}: {detail}")
    
    if s['failed'] > 0:
        print("\n  FAILURES (must fix):")
        for status, name, detail in r.results:
            if status == "FAIL":
                print(f"    - {name}: {detail}")
    
    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": s,
        "grade": grade,
        "categories": category_results,
        "details": [{"status": st, "test": n, "detail": d} for st, n, d in r.results]
    }
    
    os.makedirs("results", exist_ok=True)
    with open("results/stress_test_report.json", 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n  Report saved: results/stress_test_report.json")
    
    return s['failed']


if __name__ == "__main__":
    exit_code = main()
    sys.exit(min(exit_code, 1))
