"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                           SLIPPAGE SIMULATOR                                  ║
║                                                                               ║
║  Realistic slippage modeling for backtesting accuracy.                        ║
║  Handles: Market impact, bid-ask spread, volatility-based slippage            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Slippage Factors:
- Order type (market vs limit)
- Order size relative to volume
- Bid-ask spread
- Volatility (ATR-based)
- Time of day / session
- Asset liquidity class

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger("Slippage")


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"


class LiquidityClass(Enum):
    """Asset liquidity classification"""
    ULTRA_LIQUID = "ultra"      # BTC, ETH, NIFTY
    HIGH = "high"               # Large caps, major indices
    MEDIUM = "medium"           # Mid caps, less active
    LOW = "low"                 # Small caps, illiquid


@dataclass
class SlippageConfig:
    """Slippage simulation configuration"""
    
    # Base slippage rates by liquidity class (%)
    base_slippage: Dict[LiquidityClass, float] = None
    
    # Bid-ask spread by class (%)
    bid_ask_spread: Dict[LiquidityClass, float] = None
    
    # Volume impact factor
    volume_impact_factor: float = 0.1  # 10% of volume = base slippage
    
    # Volatility multiplier (ATR-based)
    volatility_multiplier: float = 0.5  # Slippage scales with ATR
    
    # Order type impact
    market_order_premium: float = 1.5   # 50% more slippage for market orders
    stop_order_premium: float = 2.0     # 100% more for stop orders (gaps)
    
    def __post_init__(self):
        if self.base_slippage is None:
            self.base_slippage = {
                LiquidityClass.ULTRA_LIQUID: 0.0005,  # 0.05%
                LiquidityClass.HIGH: 0.001,           # 0.10%
                LiquidityClass.MEDIUM: 0.002,         # 0.20%
                LiquidityClass.LOW: 0.005             # 0.50%
            }
        
        if self.bid_ask_spread is None:
            self.bid_ask_spread = {
                LiquidityClass.ULTRA_LIQUID: 0.0001,  # 0.01%
                LiquidityClass.HIGH: 0.0005,          # 0.05%
                LiquidityClass.MEDIUM: 0.001,         # 0.10%
                LiquidityClass.LOW: 0.003             # 0.30%
            }


# Asset liquidity classification
ASSET_LIQUIDITY = {
    # Crypto
    'BTCUSDT': LiquidityClass.ULTRA_LIQUID,
    'ETHUSDT': LiquidityClass.ULTRA_LIQUID,
    'SOLUSDT': LiquidityClass.HIGH,
    'BNBUSDT': LiquidityClass.HIGH,
    'XRPUSDT': LiquidityClass.HIGH,
    'DOGEUSDT': LiquidityClass.MEDIUM,
    
    # Indian Indices
    'NIFTY': LiquidityClass.ULTRA_LIQUID,
    'BANKNIFTY': LiquidityClass.ULTRA_LIQUID,
    'SENSEX': LiquidityClass.HIGH,
    'FINNIFTY': LiquidityClass.MEDIUM,
    
    # Gold/Silver ETFs
    'GOLDBEES': LiquidityClass.HIGH,
    'SILVERBEES': LiquidityClass.MEDIUM,
    
    # Default
    'DEFAULT': LiquidityClass.MEDIUM
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           SLIPPAGE CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class SlippageSimulator:
    """
    Realistic slippage simulation for backtesting.
    
    Usage:
        slippage = SlippageSimulator('BTCUSDT')
        
        # Get slippage for a trade
        result = slippage.calculate(
            price=42000,
            size=1.0,
            order_type=OrderType.MARKET,
            is_buy=True,
            atr=500,
            volume=1000
        )
        
        print(f"Execution price: {result['execution_price']}")
    """
    
    def __init__(
        self,
        symbol: str,
        config: SlippageConfig = None
    ):
        """
        Initialize slippage simulator.
        
        Args:
            symbol: Trading symbol
            config: Slippage configuration
        """
        self.symbol = symbol.upper()
        self.config = config or SlippageConfig()
        self.liquidity = ASSET_LIQUIDITY.get(self.symbol, ASSET_LIQUIDITY['DEFAULT'])
        
        logger.debug(f"Slippage simulator for {symbol} (liquidity: {self.liquidity.value})")
    
    def calculate(
        self,
        price: float,
        size: float,
        order_type: OrderType = OrderType.MARKET,
        is_buy: bool = True,
        atr: float = None,
        volume: float = None,
        random_seed: int = None
    ) -> Dict[str, float]:
        """
        Calculate slippage for a trade.
        
        Args:
            price: Intended execution price
            size: Order size (in base currency or lots)
            order_type: Type of order
            is_buy: True for buy, False for sell
            atr: Average True Range (for volatility adjustment)
            volume: Average volume (for market impact)
            random_seed: Optional seed for reproducibility
            
        Returns:
            Dict with slippage analysis
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # 1. Base slippage
        base = self.config.base_slippage[self.liquidity]
        
        # 2. Bid-ask spread impact
        spread = self.config.bid_ask_spread[self.liquidity]
        spread_cost = spread / 2  # Half spread per side
        
        # 3. Order type premium
        if order_type == OrderType.MARKET:
            type_multiplier = self.config.market_order_premium
        elif order_type in [OrderType.STOP_MARKET, OrderType.STOP_LIMIT]:
            type_multiplier = self.config.stop_order_premium
        else:
            type_multiplier = 1.0
        
        # 4. Volume impact (if provided)
        volume_impact = 0.0
        if volume is not None and volume > 0:
            size_as_pct_of_volume = size / volume
            volume_impact = size_as_pct_of_volume * self.config.volume_impact_factor
        
        # 5. Volatility impact (if ATR provided)
        volatility_impact = 0.0
        if atr is not None and atr > 0:
            atr_pct = atr / price
            volatility_impact = atr_pct * self.config.volatility_multiplier
        
        # 6. Random component (market microstructure noise)
        random_component = np.random.uniform(-0.5, 1.5) * base
        
        # Total slippage percentage
        total_slippage_pct = (
            base * type_multiplier +
            spread_cost +
            volume_impact +
            volatility_impact +
            max(0, random_component)
        )
        
        # Slippage in price terms
        slippage_amount = price * total_slippage_pct
        
        # Direction: buys slip up, sells slip down
        if is_buy:
            execution_price = price + slippage_amount
        else:
            execution_price = price - slippage_amount
        
        return {
            'intended_price': price,
            'execution_price': execution_price,
            'slippage_amount': slippage_amount,
            'slippage_pct': total_slippage_pct * 100,
            'components': {
                'base': base * type_multiplier * 100,
                'spread': spread_cost * 100,
                'volume_impact': volume_impact * 100,
                'volatility_impact': volatility_impact * 100
            },
            'order_type': order_type.value,
            'direction': 'BUY' if is_buy else 'SELL',
            'liquidity_class': self.liquidity.value
        }
    
    def apply_to_trades(
        self,
        trades: pd.DataFrame,
        price_col: str = 'price',
        size_col: str = 'size',
        side_col: str = 'side',
        atr_col: str = None,
        volume_col: str = None
    ) -> pd.DataFrame:
        """
        Apply slippage to a DataFrame of trades.
        
        Args:
            trades: DataFrame with trade data
            price_col: Column name for price
            size_col: Column name for size
            side_col: Column name for side (buy/sell)
            atr_col: Optional column for ATR
            volume_col: Optional column for volume
            
        Returns:
            DataFrame with slippage-adjusted prices
        """
        result = trades.copy()
        result['slippage_pct'] = 0.0
        result['execution_price'] = 0.0
        
        for idx in trades.index:
            row = trades.loc[idx]
            
            is_buy = str(row[side_col]).lower() in ['buy', 'long', '1', 'true']
            atr = row[atr_col] if atr_col and atr_col in row else None
            volume = row[volume_col] if volume_col and volume_col in row else None
            
            slip = self.calculate(
                price=row[price_col],
                size=row.get(size_col, 1.0),
                is_buy=is_buy,
                atr=atr,
                volume=volume
            )
            
            result.loc[idx, 'slippage_pct'] = slip['slippage_pct']
            result.loc[idx, 'execution_price'] = slip['execution_price']
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
#                           QUICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_slippage(
    symbol: str,
    price: float,
    size: float = 1.0,
    order_type: OrderType = OrderType.MARKET
) -> float:
    """Quick function to estimate slippage percentage."""
    sim = SlippageSimulator(symbol)
    result = sim.calculate(price, size, order_type)
    return result['slippage_pct']


def get_execution_price(
    symbol: str,
    intended_price: float,
    is_buy: bool = True,
    order_type: OrderType = OrderType.MARKET
) -> float:
    """Get expected execution price after slippage."""
    sim = SlippageSimulator(symbol)
    result = sim.calculate(intended_price, 1.0, order_type, is_buy)
    return result['execution_price']


def print_slippage_analysis(
    symbol: str,
    price: float,
    size: float = 1.0,
    atr: float = None,
    volume: float = None
):
    """Print detailed slippage analysis."""
    sim = SlippageSimulator(symbol)
    
    print(f"\n{'='*50}")
    print(f"SLIPPAGE ANALYSIS - {symbol}")
    print(f"Price: ${price:,.2f} | Size: {size}")
    print(f"{'='*50}")
    
    for order_type in OrderType:
        result = sim.calculate(
            price=price,
            size=size,
            order_type=order_type,
            is_buy=True,
            atr=atr,
            volume=volume
        )
        
        print(f"\n{order_type.value.upper()}:")
        print(f"  Execution Price: ${result['execution_price']:,.2f}")
        print(f"  Slippage: {result['slippage_pct']:.4f}%")
        print(f"  Components:")
        for comp, val in result['components'].items():
            print(f"    {comp}: {val:.4f}%")
    
    print(f"\n{'='*50}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo: BTC slippage
    print_slippage_analysis('BTCUSDT', price=42000, size=0.5, atr=500, volume=1000)
    
    # Demo: NIFTY options slippage
    print_slippage_analysis('NIFTY', price=100, size=50, atr=5)
    
    # Demo: Compare liquidity classes
    print("\nSlippage by Liquidity Class (Market Order, $100):")
    for symbol, liq in ASSET_LIQUIDITY.items():
        if symbol != 'DEFAULT':
            sim = SlippageSimulator(symbol)
            result = sim.calculate(100, 1.0, OrderType.MARKET, is_buy=True)
            print(f"  {symbol:12} ({liq.value:6}): {result['slippage_pct']:.4f}%")
