"""
C++ Trading Engine Wrapper

Provides a Python interface to the C++ trading engine.
Falls back to pure Python implementations if C++ module is not available.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Try to import C++ module
try:
    from cpp_engine import trading_engine
    CPP_AVAILABLE = True
    logger.info("C++ trading engine loaded successfully")
except ImportError as e:
    CPP_AVAILABLE = False
    logger.warning(f"C++ trading engine not available: {e}. Using Python fallback.")


def is_cpp_available() -> bool:
    """Check if C++ engine is available."""
    return CPP_AVAILABLE


# ==================== Pattern Recognition ====================

def detect_patterns(df, lookback: int = 100) -> List[Dict]:
    """
    Detect candlestick patterns in OHLC data.
    
    Args:
        df: DataFrame with 'open', 'high', 'low', 'close' columns
        lookback: Number of bars to analyze
        
    Returns:
        List of detected patterns with name, type, confidence, index
    """
    if CPP_AVAILABLE:
        patterns = trading_engine.PatternRecognition().detect_all(
            df['open'].values.astype(np.float64),
            df['high'].values.astype(np.float64),
            df['low'].values.astype(np.float64),
            df['close'].values.astype(np.float64),
            lookback
        )
        return [
            {
                'name': p.name,
                'type': p.type,
                'confidence': p.confidence,
                'index': p.index,
                'description': p.description
            }
            for p in patterns
        ]
    else:
        # Fallback to Python
        from indicators.pattern_recognition import detect_all_patterns
        return detect_all_patterns(df, lookback)


def aggregate_pattern_signals(patterns: List[Dict], min_confidence: float = 0.7) -> Tuple[float, float]:
    """
    Aggregate patterns into a trading signal.
    
    Returns:
        (signal, confidence) where signal is -1 to +1
    """
    # Python implementation (works with both C++ and Python patterns)
    if not patterns:
        return 0.0, 0.0
    
    bullish_score = sum(p['confidence'] for p in patterns 
                        if p['type'] == 'bullish' and p['confidence'] >= min_confidence)
    bearish_score = sum(p['confidence'] for p in patterns 
                        if p['type'] == 'bearish' and p['confidence'] >= min_confidence)
    
    total = bullish_score + bearish_score
    if total < 1e-10:
        return 0.0, 0.0
    
    signal = (bullish_score - bearish_score) / total
    confidence = min(1.0, total / len(patterns))
    
    return signal, confidence


# ==================== Technical Indicators ====================

class FastIndicators:
    """Fast technical indicators using C++ when available."""
    
    @staticmethod
    def sma(data: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average."""
        if CPP_AVAILABLE:
            return trading_engine.Indicators.sma(data.astype(np.float64), period)
        else:
            import pandas as pd
            return pd.Series(data).rolling(window=period).mean().values
    
    @staticmethod
    def ema(data: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        if CPP_AVAILABLE:
            return trading_engine.Indicators.ema(data.astype(np.float64), period)
        else:
            import pandas as pd
            return pd.Series(data).ewm(span=period, adjust=False).mean().values
    
    @staticmethod
    def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        if CPP_AVAILABLE:
            return trading_engine.Indicators.rsi(close.astype(np.float64), period)
        else:
            import pandas as pd
            delta = pd.Series(close).diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return (100 - (100 / (1 + rs))).values
    
    @staticmethod
    def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """MACD indicator."""
        if CPP_AVAILABLE:
            return trading_engine.Indicators.macd(close.astype(np.float64), fast, slow, signal)
        else:
            import pandas as pd
            s = pd.Series(close)
            fast_ema = s.ewm(span=fast, adjust=False).mean()
            slow_ema = s.ewm(span=slow, adjust=False).mean()
            macd_line = fast_ema - slow_ema
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            return {
                'macd_line': macd_line.values,
                'signal_line': signal_line.values,
                'histogram': (macd_line - signal_line).values
            }
    
    @staticmethod
    def bollinger_bands(close: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
        """Bollinger Bands. Returns dict with 'upper', 'middle', 'lower', 'bandwidth' keys."""
        if CPP_AVAILABLE:
            return trading_engine.Indicators.bollinger_bands(close.astype(np.float64), period, std_dev)
        else:
            import pandas as pd
            s = pd.Series(close)
            middle = s.rolling(window=period).mean()
            std = s.rolling(window=period).std()
            # Handle zero std case
            std = std.fillna(0)
            middle = middle.fillna(close[0] if len(close) > 0 else 0)
            return {
                'upper': (middle + std_dev * std).values,
                'middle': middle.values,
                'lower': (middle - std_dev * std).values,
                'bandwidth': np.where(middle != 0, (2 * std_dev * std) / middle, 0).astype(np.float64)
            }
    
    @staticmethod
    def bollinger_bands_tuple(close: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands as tuple (upper, middle, lower) for legacy compatibility."""
        result = FastIndicators.bollinger_bands(close, period, std_dev)
        return result['upper'], result['middle'], result['lower']
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Average True Range."""
        if CPP_AVAILABLE:
            return trading_engine.Indicators.atr(
                high.astype(np.float64),
                low.astype(np.float64),
                close.astype(np.float64),
                period
            )
        else:
            import pandas as pd
            tr1 = pd.Series(high) - pd.Series(low)
            tr2 = abs(pd.Series(high) - pd.Series(close).shift())
            tr3 = abs(pd.Series(low) - pd.Series(close).shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            return tr.rolling(window=period).mean().values


# ==================== Order Book ====================

class FastOrderBook:
    """Fast order book implementation using C++ when available."""
    
    def __init__(self, symbol: str, depth_levels: int = 20):
        self.symbol = symbol
        self.depth_levels = depth_levels
        
        if CPP_AVAILABLE:
            self._book = trading_engine.OrderBook(symbol, depth_levels)
        else:
            self._book = None
            self._bids = {}
            self._asks = {}
    
    def update(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]], event_time: int = 0):
        """Update order book with new depth data."""
        if CPP_AVAILABLE:
            cpp_bids = [trading_engine.PriceLevel(p, q) for p, q in bids]
            cpp_asks = [trading_engine.PriceLevel(p, q) for p, q in asks]
            self._book.update(cpp_bids, cpp_asks, event_time)
        else:
            self._bids = {p: q for p, q in bids[:self.depth_levels]}
            self._asks = {p: q for p, q in asks[:self.depth_levels]}
    
    def get_mid_price(self) -> float:
        if CPP_AVAILABLE:
            return self._book.get_mid_price()
        else:
            if not self._bids or not self._asks:
                return 0.0
            return (max(self._bids.keys()) + min(self._asks.keys())) / 2
    
    def get_order_book_imbalance(self, levels: int = -1) -> float:
        if CPP_AVAILABLE:
            return self._book.get_order_book_imbalance(levels)
        else:
            bid_depth = sum(self._bids.values())
            ask_depth = sum(self._asks.values())
            total = bid_depth + ask_depth
            if total == 0:
                return 0.0
            return (bid_depth - ask_depth) / total


# ==================== Position Sizer ====================

class FastPositionSizer:
    """Fast position sizer using C++ when available."""
    
    def __init__(self, capital: float = 1000.0, max_risk: float = 0.02, 
                 max_position_pct: float = 0.20, kelly_fraction: float = 0.25):
        if CPP_AVAILABLE:
            self._sizer = trading_engine.PositionSizer(capital, max_risk, max_position_pct, kelly_fraction)
        else:
            self._sizer = None
            self.capital = capital
            self.max_risk = max_risk
            self.max_position_pct = max_position_pct
            self.wins = 0
            self.losses = 0
    
    def calculate_position_size(self, price: float, stop_loss: float, 
                                confidence: float = 1.0, regime_multiplier: float = 1.0) -> Dict:
        if CPP_AVAILABLE:
            result = self._sizer.calculate_position_size(price, stop_loss, confidence, regime_multiplier)
            return {
                'size': result.size,
                'risk_amount': result.risk_amount,
                'stop_distance': result.stop_distance,
                'kelly_fraction': result.kelly_fraction,
                'method': result.method
            }
        else:
            # Simple Python fallback
            stop_distance = abs(price - stop_loss)
            risk_amount = self.capital * self.max_risk * confidence
            size = risk_amount / stop_distance if stop_distance > 0 else 0
            max_size = (self.capital * self.max_position_pct) / price
            return {
                'size': min(size, max_size),
                'risk_amount': risk_amount,
                'stop_distance': stop_distance,
                'kelly_fraction': 0.0,
                'method': 'fixed_risk'
            }


# ==================== Kalman Filter ====================

class FastKalmanFilter:
    """Fast Kalman filter using C++ when available."""
    
    def __init__(self, process_noise: float = 0.01, measurement_noise: float = 0.1):
        if CPP_AVAILABLE:
            self._filter = trading_engine.KalmanFilter(process_noise, measurement_noise)
        else:
            self._filter = None
            self.estimate = 0.0
            self.error = 1.0
            self.process_noise = process_noise
            self.measurement_noise = measurement_noise
    
    def update(self, measurement: float) -> Dict:
        if CPP_AVAILABLE:
            state = self._filter.update(measurement)
            return {
                'estimate': state.estimate,
                'error_estimate': state.error_estimate,
                'velocity': state.velocity
            }
        else:
            # Simple Python Kalman update
            kalman_gain = self.error / (self.error + self.measurement_noise)
            prev_estimate = self.estimate
            self.estimate = self.estimate + kalman_gain * (measurement - self.estimate)
            self.error = (1 - kalman_gain) * self.error + self.process_noise
            return {
                'estimate': self.estimate,
                'error_estimate': self.error,
                'velocity': self.estimate - prev_estimate
            }
    
    @staticmethod
    def filter_series(data: np.ndarray, process_noise: float = 0.01, 
                      measurement_noise: float = 0.1) -> np.ndarray:
        if CPP_AVAILABLE:
            return trading_engine.KalmanFilter.filter_series(
                data.astype(np.float64), process_noise, measurement_noise
            )
        else:
            result = np.zeros_like(data)
            kf = FastKalmanFilter(process_noise, measurement_noise)
            for i, val in enumerate(data):
                state = kf.update(val)
                result[i] = state['estimate']
            return result


# ==================== Convenience Functions ====================

def get_engine_info() -> Dict[str, Any]:
    """Get information about the trading engine."""
    return {
        'cpp_available': CPP_AVAILABLE,
        'version': trading_engine.__version__ if CPP_AVAILABLE else 'python-fallback',
        'components': [
            'PatternRecognition',
            'OrderBook',
            'Indicators',
            'PositionSizer',
            'KalmanFilter'
        ]
    }


# Export main classes
__all__ = [
    'is_cpp_available',
    'detect_patterns',
    'aggregate_pattern_signals',
    'FastIndicators',
    'FastOrderBook',
    'FastPositionSizer',
    'FastKalmanFilter',
    'get_engine_info',
    'CPP_AVAILABLE'
]
