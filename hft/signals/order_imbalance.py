"""
Order Book Imbalance (OBI) Signal Generator
Primary HFT strategy using order flow analysis
"""

import time
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
from collections import deque
from hft.order_book import OrderBook

# Add root to path for uncorrelated features
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from strategies.advanced import UncorrelatedFeatures


class OBISignalGenerator:
    """
    Generate trading signals from Order Book Imbalance
    
    Strategy:
    - Monitor real-time order book imbalance
    - LONG when OBI > threshold (strong buy pressure)
    - SHORT when OBI < -threshold (strong sell pressure)
    - Exit when OBI reverses or profit target hit
    """
    
    def __init__(
        self,
        long_threshold: float = 0.30,
        short_threshold: float = -0.30,
        lookback_window: int = 10,
        min_spread_pct: float = 0.05
    ):
        """
        Args:
            long_threshold: OBI value to trigger LONG (default 0.30)
            short_threshold: OBI value to trigger SHORT (default -0.30)
            lookback_window: Number of OBI readings to smooth
            min_spread_pct: Minimum spread % to trade (avoid illiquid markets)
        """
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.lookback_window = lookback_window
        self.min_spread_pct = min_spread_pct
        
        # OBI history for smoothing
        self.obi_history = {}
        
        # Price history for uncorrelated features (last 60 midprices)
        self.price_history = {}
        
        # Performance tracking
        self.signal_count = 0
        self.last_signal = {}
        
    def _get_smoothed_obi(self, symbol: str, current_obi: float) -> float:
        """Apply exponential moving average to smooth OBI"""
        if symbol not in self.obi_history:
            self.obi_history[symbol] = deque(maxlen=self.lookback_window)
        
        self.obi_history[symbol].append(current_obi)
        
        # Simple moving average
        if len(self.obi_history[symbol]) == 0:
            return current_obi
        
        return sum(self.obi_history[symbol]) / len(self.obi_history[symbol])
    
    def generate_signal(
        self,
        symbol: str,
        order_book: OrderBook
    ) -> Tuple[str, float, Dict]:
        """
        Generate trading signal from order book
        
        Args:
            symbol: Trading symbol
            order_book: OrderBook instance
        
        Returns:
            Tuple of (signal, confidence, metadata)
            signal: 'LONG', 'SHORT', or 'HOLD'
            confidence: 0.0 to 1.0
            metadata: Additional signal info
        """
        start_time = time.time() * 1000
        
        # Check spread (avoid illiquid markets)
        spread_pct = order_book.get_spread_pct()
        if spread_pct is None or spread_pct > self.min_spread_pct:
            return 'HOLD', 0.0, {'reason': 'spread_too_wide', 'spread_pct': spread_pct}
        
        # Calculate OBI
        raw_obi = order_book.get_order_book_imbalance()
        smoothed_obi = self._get_smoothed_obi(symbol, raw_obi)
        
        # Get market data
        mid_price = order_book.get_mid_price()
        best_bid = order_book.get_best_bid()
        best_ask = order_book.get_best_ask()
        
        # Update price history for uncorrelated features
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=60)
        self.price_history[symbol].append(mid_price)
        
        # Calculate uncorrelated features if enough history
        hurst = 0.5
        entropy = 0.5
        uncor_weight = 1.0
        
        if len(self.price_history[symbol]) >= 50:
            import numpy as np
            prices = np.array(list(self.price_history[symbol]))
            hurst = UncorrelatedFeatures.get_hurst_exponent(prices)
            entropy = UncorrelatedFeatures.get_shannon_entropy(prices)
            
            # Adjust confidence based on uncorrelated features
            # In HFT, high Hurst (trending) is good for momentum
            # Low entropy (predictable) is good for any signal
            if hurst > 0.6:  # Strong trend
                uncor_weight *= 1.2  # Boost confidence
            elif hurst < 0.4:  # Mean reverting
                uncor_weight *= 0.9  # Reduce momentum signals
            
            if entropy > 0.8:  # High noise
                uncor_weight *= 0.7  # Reduce all signals
        
        # Generate signal
        signal = 'HOLD'
        confidence = 0.0
        
        if smoothed_obi >= self.long_threshold:
            # Strong buy pressure - LONG signal
            signal = 'LONG'
            # Confidence scales with OBI strength
            confidence = min(1.0, (smoothed_obi - self.long_threshold) / (1.0 - self.long_threshold))
            
        elif smoothed_obi <= self.short_threshold:
            # Strong sell pressure - SHORT signal
            signal = 'SHORT'
            # Confidence scales with OBI strength
            confidence = min(1.0, abs(smoothed_obi - self.short_threshold) / (1.0 - abs(self.short_threshold)))
        
        # Calculate latency
        end_time = time.time() * 1000
        latency_ms = end_time - start_time
        
        # Metadata
        metadata = {
            'obi_raw': raw_obi,
            'obi_smoothed': smoothed_obi,
            'mid_price': mid_price,
            'spread_pct': spread_pct,
            'bid_depth': order_book.get_bid_depth(),
            'ask_depth': order_book.get_ask_depth(),
            'latency_ms': latency_ms,
            'timestamp': int(time.time() * 1000),
            'hurst': hurst,
            'entropy': entropy,
            'uncor_weight': uncor_weight
        }
        
        # Track signals
        if signal != 'HOLD':
            self.signal_count += 1
            self.last_signal[symbol] = {
                'signal': signal,
                'confidence': confidence,
                'time': time.time()
            }
        
        return signal, confidence, metadata
    
    def should_exit(
        self,
        symbol: str,
        position_side: str,
        order_book: OrderBook,
        profit_pct: float,
        profit_target_pct: float = 0.03,
        stop_loss_pct: float = 0.015
    ) -> Tuple[bool, str]:
        """
        Determine if position should be exited
        
        Args:
            symbol: Trading symbol
            position_side: 'LONG' or 'SHORT'
            order_book: Current order book
            profit_pct: Current profit %
            profit_target_pct: Profit target %
            stop_loss_pct: Stop loss %
        
        Returns:
            (should_exit, reason)
        """
        # Check profit target
        if profit_pct >= profit_target_pct:
            return True, 'PROFIT_TARGET'
        
        # Check stop loss
        if profit_pct <= -stop_loss_pct:
            return True, 'STOP_LOSS'
        
        # Check OBI reversal
        current_obi = order_book.get_order_book_imbalance()
        smoothed_obi = self._get_smoothed_obi(symbol, current_obi)
        
        if position_side == 'LONG':
            # Exit LONG if strong sell pressure appears
            if smoothed_obi < -0.15:
                return True, 'OBI_REVERSAL'
        
        elif position_side == 'SHORT':
            # Exit SHORT if strong buy pressure appears
            if smoothed_obi > 0.15:
                return True, 'OBI_REVERSAL'
        
        return False, 'HOLD'
    
    def get_stats(self) -> Dict:
        """Get signal generator statistics"""
        return {
            'total_signals': self.signal_count,
            'long_threshold': self.long_threshold,
            'short_threshold': self.short_threshold,
            'last_signals': self.last_signal
        }


# Example usage
if __name__ == "__main__":
    from hft.order_book import OrderBook
    
    # Create signal generator
    signal_gen = OBISignalGenerator(
        long_threshold=0.30,
        short_threshold=-0.30,
        lookback_window=10
    )
    
    # Test with order book
    book = OrderBook('BTCUSDT')
    
    # Simulate strong buy pressure
    test_data = {
        'u': 1,
        'E': int(time.time() * 1000),
        'b': [['99000', '10.0'], ['98999', '8.0'], ['98998', '5.0']],  # Large bids
        'a': [['99001', '1.0'], ['99002', '0.5'], ['99003', '0.3']]   # Small asks
    }
    
    book.update(test_data)
    
    signal, confidence, metadata = signal_gen.generate_signal('BTCUSDT', book)
    
    print(f"Signal: {signal} (Confidence: {confidence:.2%})")
    print(f"OBI: {metadata['obi_smoothed']:.4f}")
    print(f"Spread: {metadata['spread_pct']:.4f}%")
    print(f"Latency: {metadata['latency_ms']:.2f}ms")
