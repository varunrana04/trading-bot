"""
VPIN - Volume-Synchronized Probability of Informed Trading
Market microstructure indicator for detecting toxic order flow
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, List, Optional
from collections import deque


class VPIN:
    """
    VPIN (Volume-Synchronized Probability of Informed Trading)
    
    Theory:
    - High VPIN = informed traders active → market about to move → avoid trading
    - Low VPIN = uninformed/noise traders → safe liquidity → good for trading
    
    Calculation:
    1. Divide volume into buckets of equal size
    2. Classify each bucket as buy or sell using tick rule
    3. Calculate order imbalance: |Buy Vol - Sell Vol| / Total Vol
    4. VPIN = moving average of order imbalance
    
    Interpretation:
    - VPIN > 0.8 → Very toxic (avoid)
    - 0.6 < VPIN < 0.8 → Toxic (reduce size)
    - 0.4 < VPIN < 0.6 → Normal
    - VPIN < 0.4 → Safe (increase size)
    """
    
    def __init__(
        self,
        bucket_volume: float = 100.0,  # Volume per bucket
        num_buckets: int = 50,          # Buckets for MA
        high_threshold: float = 0.8,
        low_threshold: float = 0.4
    ):
        """
        Initialize VPIN calculator
        
        Args:
            bucket_volume: Volume size for each bucket
            num_buckets: Number of buckets for moving average
            high_threshold: VPIN above this = toxic
            low_threshold: VPIN below this = safe
        """
        self.bucket_volume = bucket_volume
        self.num_buckets = num_buckets
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        
        # State
        self.current_bucket_volume = 0
        self.current_buy_volume = 0
        self.current_sell_volume = 0
        self.bucket_imbalances = deque(maxlen=num_buckets)
        self.last_price = None
    
    def update(
        self,
        price: float,
        volume: float,
        is_buy: Optional[bool] = None
    ) -> float:
        """
        Update VPIN with new trade
        
        Args:
            price: Trade price
            volume: Trade volume
            is_buy: True if buy, False if sell, None to infer from tick rule
            
        Returns:
            Current VPIN value
        """
        # Classify as buy or sell using tick rule if not provided
        if is_buy is None:
            if self.last_price is not None:
                if price > self.last_price:
                    is_buy = True  # Uptick = buy
                elif price < self.last_price:
                    is_buy = False  # Downtick = sell
                else:
                    is_buy = True  # Zero tick = assume buy
            else:
                is_buy = True  # First trade, assume buy
        
        self.last_price = price
        
        # Add to current bucket
        self.current_bucket_volume += volume
        
        if is_buy:
            self.current_buy_volume += volume
        else:
            self.current_sell_volume += volume
        
        # Check if bucket is full
        if self.current_bucket_volume >= self.bucket_volume:
            # Calculate order imbalance for this bucket
            total_vol = self.current_buy_volume + self.current_sell_volume
            
            if total_vol > 0:
                imbalance = abs(self.current_buy_volume - self.current_sell_volume) / total_vol
                self.bucket_imbalances.append(imbalance)
            
            # Reset bucket
            self.current_bucket_volume = 0
            self.current_buy_volume = 0
            self.current_sell_volume = 0
        
        return self.get_vpin()
    
    def get_vpin(self) -> float:
        """
        Get current VPIN value
        
        Returns:
            VPIN (0 to 1)
        """
        if len(self.bucket_imbalances) == 0:
            return 0.5  # Neutral if no data
        
        # VPIN = average order imbalance
        return np.mean(self.bucket_imbalances)
    
    def get_toxicity_level(self) -> str:
        """
        Get current market toxicity level
        
        Returns:
            'VERY_TOXIC' | 'TOXIC' | 'NORMAL' | 'SAFE'
        """
        vpin = self.get_vpin()
        
        if vpin > self.high_threshold:
            if vpin > 0.9:
                return 'VERY_TOXIC'
            return 'TOXIC'
        elif vpin < self.low_threshold:
            return 'SAFE'
        else:
            return 'NORMAL'
    
    def get_position_size_multiplier(self) -> float:
        """
        Get recommended position size multiplier based on VPIN
        
        Returns:
            Multiplier (0.25 to 1.5)
        """
        toxicity = self.get_toxicity_level()
        
        multipliers = {
            'VERY_TOXIC': 0.25,  # Reduce to 25%
            'TOXIC': 0.5,        # Reduce to 50%
            'NORMAL': 1.0,       # Normal size
            'SAFE': 1.5          # Increase to 150%
        }
        
        return multipliers[toxicity]
    
    def should_trade(self) -> Tuple[bool, str]:
        """
        Determine if it's safe to trade
        
        Returns:
            (should_trade, reason)
        """
        toxicity = self.get_toxicity_level()
        vpin = self.get_vpin()
        
        if toxicity == 'VERY_TOXIC':
            return False, f"VPIN too high ({vpin:.3f}) - informed trading detected"
        elif toxicity == 'TOXIC':
            return True, f"VPIN elevated ({vpin:.3f}) - reduce size"
        else:
            return True, f"VPIN normal ({vpin:.3f}) - safe to trade"


class OrderBookImbalance:
    """
    Enhanced Order Book Imbalance (complement to VPIN)
    """
    
    def __init__(
        self,
        depth_levels: int = 5,
        threshold: float = 0.6
    ):
        """
        Args:
            depth_levels: Number of order book levels to analyze
            threshold: Imbalance threshold for signals
        """
        self.depth_levels = depth_levels
        self.threshold = threshold
    
    def calculate_obi(
        self,
        bids: List[Tuple[float, float]],  # [(price, size), ...]
        asks: List[Tuple[float, float]]
    ) -> float:
        """
        Calculate Order Book Imbalance
        
        OBI = (Bid Depth - Ask Depth) / (Bid Depth + Ask Depth)
        
        Args:
            bids: List of (price, size) for bids
            asks: List of (price, size) for asks
            
        Returns:
            OBI (-1 to +1)
        """
        # Sum volumes at top N levels
        bid_depth = sum(size for _, size in bids[:self.depth_levels])
        ask_depth = sum(size for _, size in asks[:self.depth_levels])
        
        total_depth = bid_depth + ask_depth
        
        if total_depth == 0:
            return 0.0
        
        obi = (bid_depth - ask_depth) / total_depth
        
        return obi
    
    def get_signal(self, obi: float) -> Dict:
        """
        Get trading signal from OBI
        
        Args:
            obi: Order book imbalance
            
        Returns:
            Signal dictionary
        """
        if obi > self.threshold:
            return {
                'signal': 'LONG',
                'strength': abs(obi),
                'reason': f'Strong bid pressure (OBI={obi:.3f})'
            }
        elif obi < -self.threshold:
            return {
                'signal': 'SHORT',
                'strength': abs(obi),
                'reason': f'Strong ask pressure (OBI={obi:.3f})'
            }
        else:
            return {
                'signal': 'HOLD',
                'strength': 0,
                'reason': f'Balanced book (OBI={obi:.3f})'
            }


# Example usage
if __name__ == "__main__":
    print("VPIN - Market Microstructure Analysis")
    print("=" * 60)
    
    # Create VPIN calculator
    vpin = VPIN(
        bucket_volume=100.0,
        num_buckets=50,
        high_threshold=0.8,
        low_threshold=0.4
    )
    
    print("\nVPIN initialized:")
    print("  Bucket size: 100 volume units")
    print("  Moving average: 50 buckets")
    print("  Toxic threshold: >0.8")
    print("  Safe threshold: <0.4")
    
    print("\nInterpretation:")
    print("  VPIN > 0.8 → Informed traders → AVOID")
    print("  VPIN < 0.4 → Noise traders → SAFE")
    
    # Create OBI calculator
    obi = OrderBookImbalance(depth_levels=5, threshold=0.6)
    
    print("\n" + "=" * 60)
    print("Order Book Imbalance (OBI) initialized:")
    print("  Analyzes top 5 levels")
    print("  Signal threshold: ±0.6")
    
    print("\nReady to analyze market microstructure")
