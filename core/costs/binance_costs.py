"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       BINANCE FUTURES COSTS                                   ║
║                                                                               ║
║  Complete transaction cost modeling for Binance futures trading.              ║
║  Includes: Trading fees, Funding rates, Liquidation, Slippage                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Costs included:
- Maker/Taker fees (0.02%/0.05% base, discounts with BNB)
- Funding rate payments (every 8 hours)
- Liquidation fees (1-1.5% of margin)
- Slippage estimation
- Position sizing with leverage

Author: Bot_Algo
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger("BinanceCosts")


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class VIPLevel(Enum):
    """Binance VIP levels for fee discounts"""
    VIP0 = 0
    VIP1 = 1
    VIP2 = 2
    VIP3 = 3
    VIP4 = 4


# Max leverage per symbol (Binance limits)
MAX_LEVERAGE = {
    'BTCUSDT': 125,
    'ETHUSDT': 100,
    'SOLUSDT': 75,
    'BNBUSDT': 75,
    'XRPUSDT': 75,
    'DOGEUSDT': 75,
    'ADAUSDT': 75,
    'DEFAULT': 50
}


@dataclass
class BinanceFeeRates:
    """Binance futures fee structure"""
    
    # VIP 0 rates (base rates)
    MAKER_FEE: float = 0.0002      # 0.02%
    TAKER_FEE: float = 0.0005      # 0.05%
    
    # BNB discount (10% off)
    BNB_DISCOUNT: float = 0.10     # 10%
    
    # Funding rate (base, actual varies)
    BASE_FUNDING_RATE: float = 0.0001  # 0.01% per 8h
    
    # Liquidation fee
    LIQUIDATION_FEE: float = 0.015  # 1.5% of margin
    
    # Maintenance margin rates (varies by position size)
    MAINTENANCE_MARGIN: Dict[str, float] = None
    
    def __post_init__(self):
        if self.MAINTENANCE_MARGIN is None:
            self.MAINTENANCE_MARGIN = {
                'BTCUSDT': 0.004,  # 0.4%
                'ETHUSDT': 0.005,  # 0.5%
                'DEFAULT': 0.01    # 1%
            }


# ═══════════════════════════════════════════════════════════════════════════════
#                           COST CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class BinanceFuturesCosts:
    """
    Complete Binance futures cost calculator.
    
    Usage:
        costs = BinanceFuturesCosts('BTCUSDT')
        
        # Calculate trade costs
        result = costs.calculate_trade_cost(
            entry_price=42000,
            quantity=0.1,
            leverage=10,
            is_maker=False
        )
        
        # Get liquidation price
        liq = costs.calculate_liquidation_price(
            entry_price=42000,
            leverage=10,
            is_long=True
        )
    """
    
    def __init__(
        self,
        symbol: str = 'BTCUSDT',
        vip_level: VIPLevel = VIPLevel.VIP0,
        use_bnb: bool = True,
        slippage_pct: float = 0.001  # 0.1% default slippage
    ):
        """
        Initialize cost calculator.
        
        Args:
            symbol: Trading pair (BTCUSDT, ETHUSDT, etc.)
            vip_level: Binance VIP level for fee discounts
            use_bnb: Whether paying fees with BNB (10% discount)
            slippage_pct: Estimated slippage percentage
        """
        self.symbol = symbol.upper()
        self.vip_level = vip_level
        self.use_bnb = use_bnb
        self.slippage_pct = slippage_pct
        self.rates = BinanceFeeRates()
        self.max_leverage = MAX_LEVERAGE.get(self.symbol, MAX_LEVERAGE['DEFAULT'])
        
        logger.debug(f"Binance cost calculator initialized for {symbol}")
    
    def get_effective_fee(self, is_maker: bool = False) -> float:
        """Get effective fee rate after discounts."""
        base_fee = self.rates.MAKER_FEE if is_maker else self.rates.TAKER_FEE
        
        # Apply BNB discount
        if self.use_bnb:
            base_fee *= (1 - self.rates.BNB_DISCOUNT)
        
        # Apply VIP discount (simplified)
        vip_discount = self.vip_level.value * 0.05  # 5% per VIP level
        base_fee *= (1 - vip_discount)
        
        return base_fee
    
    def calculate_trade_cost(
        self,
        entry_price: float,
        quantity: float,
        leverage: int = 1,
        is_maker: bool = False,
        holding_hours: float = 0,
        funding_rate: float = None
    ) -> Dict[str, float]:
        """
        Calculate all costs for a futures trade.
        
        Args:
            entry_price: Entry price in USDT
            quantity: Position size in base currency (e.g., 0.1 BTC)
            leverage: Leverage used (1-125x)
            is_maker: True for limit orders, False for market
            holding_hours: Expected holding time in hours
            funding_rate: Current funding rate (uses base rate if None)
            
        Returns:
            Dict with complete cost breakdown
        """
        # Validate leverage
        leverage = min(leverage, self.max_leverage)
        
        # Position value
        notional_value = entry_price * quantity
        margin_required = notional_value / leverage
        
        # Trading fee (on notional value)
        fee_rate = self.get_effective_fee(is_maker)
        trading_fee = notional_value * fee_rate
        
        # Slippage (on notional value)
        slippage_cost = notional_value * self.slippage_pct
        
        # Funding payments (every 8 hours)
        if funding_rate is None:
            funding_rate = self.rates.BASE_FUNDING_RATE
        
        funding_periods = holding_hours / 8
        funding_cost = notional_value * funding_rate * funding_periods
        
        # Total entry cost
        entry_cost = trading_fee + slippage_cost
        
        # Estimated exit cost (assume same fees)
        exit_cost = trading_fee + slippage_cost
        
        # Total round-trip cost
        total_cost = entry_cost + exit_cost + abs(funding_cost)
        
        return {
            'symbol': self.symbol,
            'notional_value': notional_value,
            'margin_required': margin_required,
            'leverage': leverage,
            'fee_rate': fee_rate,
            'trading_fee_entry': trading_fee,
            'trading_fee_exit': trading_fee,
            'slippage_entry': slippage_cost,
            'slippage_exit': slippage_cost,
            'funding_rate': funding_rate,
            'funding_periods': funding_periods,
            'funding_cost': funding_cost,
            'total_entry_cost': entry_cost,
            'total_exit_cost': exit_cost,
            'total_round_trip': total_cost,
            'cost_as_pct_of_margin': (total_cost / margin_required) * 100 if margin_required > 0 else 0
        }
    
    def calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: int,
        is_long: bool = True,
        margin_type: str = 'isolated'
    ) -> Dict[str, float]:
        """
        Calculate liquidation price for a position.
        
        Args:
            entry_price: Entry price
            leverage: Leverage used
            is_long: True for long, False for short
            margin_type: 'isolated' or 'cross'
            
        Returns:
            Dict with liquidation details
        """
        # Get maintenance margin rate
        mm_rate = self.rates.MAINTENANCE_MARGIN.get(
            self.symbol, 
            self.rates.MAINTENANCE_MARGIN['DEFAULT']
        )
        
        # For isolated margin:
        # Long: Liq Price = Entry × (1 - 1/Leverage + MM_Rate)
        # Short: Liq Price = Entry × (1 + 1/Leverage - MM_Rate)
        
        if is_long:
            liq_price = entry_price * (1 - (1 / leverage) + mm_rate)
            distance_pct = (entry_price - liq_price) / entry_price * 100
        else:
            liq_price = entry_price * (1 + (1 / leverage) - mm_rate)
            distance_pct = (liq_price - entry_price) / entry_price * 100
        
        return {
            'entry_price': entry_price,
            'liquidation_price': liq_price,
            'leverage': leverage,
            'direction': 'LONG' if is_long else 'SHORT',
            'distance_to_liq_pct': distance_pct,
            'maintenance_margin_rate': mm_rate,
            'margin_type': margin_type
        }
    
    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_loss_pct: float,
        risk_per_trade_pct: float = 2.0,
        max_leverage: int = None
    ) -> Dict[str, float]:
        """
        Calculate optimal position size based on risk management.
        
        Args:
            capital: Total trading capital in USDT
            entry_price: Entry price
            stop_loss_pct: Stop loss percentage from entry
            risk_per_trade_pct: Max % of capital to risk per trade
            max_leverage: Maximum leverage to use (defaults to symbol max)
            
        Returns:
            Dict with position sizing details
        """
        if max_leverage is None:
            max_leverage = self.max_leverage
        
        # Risk amount in USDT
        risk_amount = capital * (risk_per_trade_pct / 100)
        
        # Position size where stop_loss_pct loss = risk_amount
        # position_size = risk_amount / (entry_price × stop_loss_pct)
        position_size = risk_amount / (entry_price * (stop_loss_pct / 100))
        
        # Notional value
        notional_value = position_size * entry_price
        
        # Required leverage
        required_leverage = notional_value / capital
        
        # Cap leverage
        actual_leverage = min(required_leverage, max_leverage)
        
        # Adjust position if leverage capped
        if required_leverage > max_leverage:
            max_notional = capital * max_leverage
            position_size = max_notional / entry_price
            notional_value = max_notional
        
        # Margin required
        margin_required = notional_value / actual_leverage
        
        return {
            'capital': capital,
            'risk_per_trade_pct': risk_per_trade_pct,
            'risk_amount': risk_amount,
            'stop_loss_pct': stop_loss_pct,
            'position_size': position_size,
            'notional_value': notional_value,
            'leverage_required': required_leverage,
            'leverage_used': actual_leverage,
            'margin_required': margin_required,
            'leverage_capped': required_leverage > max_leverage
        }
    
    def estimate_breakeven_move(
        self,
        entry_price: float,
        quantity: float,
        leverage: int,
        holding_hours: float = 0
    ) -> Dict[str, float]:
        """
        Calculate minimum price move needed to break even after costs.
        
        Args:
            entry_price: Entry price
            quantity: Position size
            leverage: Leverage used
            holding_hours: Expected holding time
            
        Returns:
            Dict with breakeven analysis
        """
        costs = self.calculate_trade_cost(
            entry_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            is_maker=False,
            holding_hours=holding_hours
        )
        
        total_cost = costs['total_round_trip']
        notional = costs['notional_value']
        
        # Breakeven move = total_cost / quantity
        breakeven_move = total_cost / quantity
        breakeven_pct = (breakeven_move / entry_price) * 100
        
        return {
            'entry_price': entry_price,
            'total_costs': total_cost,
            'breakeven_move_price': breakeven_move,
            'breakeven_pct': breakeven_pct,
            'breakeven_price_long': entry_price + breakeven_move,
            'breakeven_price_short': entry_price - breakeven_move,
            'cost_as_pct_of_notional': (total_cost / notional) * 100
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           QUICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_binance_cost(
    symbol: str,
    entry_price: float,
    quantity: float,
    leverage: int = 1,
    holding_hours: float = 0
) -> float:
    """Quick function to estimate total round-trip cost."""
    calc = BinanceFuturesCosts(symbol)
    result = calc.calculate_trade_cost(
        entry_price=entry_price,
        quantity=quantity,
        leverage=leverage,
        holding_hours=holding_hours
    )
    return result['total_round_trip']


def get_liquidation_price(
    symbol: str,
    entry_price: float,
    leverage: int,
    is_long: bool = True
) -> float:
    """Quick function to get liquidation price."""
    calc = BinanceFuturesCosts(symbol)
    result = calc.calculate_liquidation_price(
        entry_price=entry_price,
        leverage=leverage,
        is_long=is_long
    )
    return result['liquidation_price']


def print_cost_breakdown(
    symbol: str,
    entry_price: float,
    quantity: float,
    leverage: int = 10,
    holding_hours: float = 24
):
    """Print detailed cost breakdown."""
    calc = BinanceFuturesCosts(symbol)
    
    print(f"\n{'='*60}")
    print(f"BINANCE FUTURES COSTS - {symbol}")
    print(f"Entry: ${entry_price:,.2f} | Qty: {quantity} | Leverage: {leverage}x")
    print(f"{'='*60}")
    
    costs = calc.calculate_trade_cost(
        entry_price=entry_price,
        quantity=quantity,
        leverage=leverage,
        holding_hours=holding_hours
    )
    
    print(f"\nPosition Details:")
    print(f"  Notional Value:    ${costs['notional_value']:,.2f}")
    print(f"  Margin Required:   ${costs['margin_required']:,.2f}")
    print(f"  Fee Rate:          {costs['fee_rate']*100:.4f}%")
    
    print(f"\nCost Breakdown:")
    print(f"  Trading Fee (Entry):  ${costs['trading_fee_entry']:.4f}")
    print(f"  Trading Fee (Exit):   ${costs['trading_fee_exit']:.4f}")
    print(f"  Slippage (Entry):     ${costs['slippage_entry']:.4f}")
    print(f"  Slippage (Exit):      ${costs['slippage_exit']:.4f}")
    print(f"  Funding ({costs['funding_periods']:.1f} periods): ${costs['funding_cost']:.4f}")
    print(f"  {'-'*40}")
    print(f"  TOTAL ROUND-TRIP:     ${costs['total_round_trip']:.4f}")
    print(f"  Cost as % of Margin:  {costs['cost_as_pct_of_margin']:.2f}%")
    
    # Liquidation
    liq = calc.calculate_liquidation_price(entry_price, leverage, is_long=True)
    print(f"\nLiquidation (Long):")
    print(f"  Liq Price:            ${liq['liquidation_price']:,.2f}")
    print(f"  Distance:             {liq['distance_to_liq_pct']:.2f}%")
    
    # Breakeven
    be = calc.estimate_breakeven_move(entry_price, quantity, leverage, holding_hours)
    print(f"\nBreakeven:")
    print(f"  Min Move Required:    ${be['breakeven_move_price']:.2f} ({be['breakeven_pct']:.3f}%)")
    print(f"  Breakeven (Long):     ${be['breakeven_price_long']:,.2f}")
    print(f"  Breakeven (Short):    ${be['breakeven_price_short']:,.2f}")
    
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo: BTC trade
    print_cost_breakdown('BTCUSDT', entry_price=42000, quantity=0.1, leverage=10, holding_hours=24)
    
    # Demo: ETH trade
    print_cost_breakdown('ETHUSDT', entry_price=2200, quantity=1.0, leverage=20, holding_hours=48)
    
    # Position sizing example
    calc = BinanceFuturesCosts('BTCUSDT')
    sizing = calc.calculate_position_size(
        capital=1000,  # $1000 capital
        entry_price=42000,
        stop_loss_pct=2.0,  # 2% stop loss
        risk_per_trade_pct=2.0  # Risk 2% per trade
    )
    print(f"Position Sizing for $1000 capital:")
    print(f"  Position Size: {sizing['position_size']:.6f} BTC")
    print(f"  Notional: ${sizing['notional_value']:,.2f}")
    print(f"  Leverage: {sizing['leverage_used']:.1f}x")
    print(f"  Margin: ${sizing['margin_required']:,.2f}")
