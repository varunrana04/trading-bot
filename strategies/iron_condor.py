"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       IRON CONDOR STRATEGY                                    ║
║                                                                               ║
║  Weekly Iron Condor strategy for NIFTY/BANKNIFTY index options.               ║
║  Designed to profit from time decay in ranging markets.                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Iron Condor = Short Put Spread + Short Call Spread
- Profit when index stays within a range
- Limited risk, limited reward
- Best in low volatility, ranging markets

Entry Criteria:
- Days to expiry: 5-14 days
- India VIX < 18 (low volatility environment)
- No major events (budget, RBI policy)

Exit Criteria:
- Take profit: 50% of max profit
- Stop loss: 100% of premium collected
- Forced exit: 1 day before expiry

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger("IronCondorStrategy")


# ═══════════════════════════════════════════════════════════════════════════════
#                           LOT SIZES
# ═══════════════════════════════════════════════════════════════════════════════

LOT_SIZES = {
    'NIFTY': 50,
    'BANKNIFTY': 30,
    'SENSEX': 10,
}


# ═══════════════════════════════════════════════════════════════════════════════
#                           STRATEGY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IronCondorConfig:
    """Configuration for Iron Condor strategy."""
    
    # Strike selection
    short_delta: float = 0.15           # Delta for short strikes (~85% OTM)
    wing_width: int = 50                # Points between short and long strikes
    
    # Entry criteria
    min_dte: int = 5                    # Minimum days to expiry
    max_dte: int = 14                   # Maximum days to expiry
    max_vix: float = 18.0               # Maximum VIX for entry
    min_premium_collected: float = 0.05  # Min premium as % of wing width (5%)
    
    # Exit criteria
    take_profit_pct: float = 0.50       # Take profit at 50% of max profit
    stop_loss_pct: float = 1.00         # Stop at 100% loss (2x premium)
    min_dte_exit: int = 1               # Force exit 1 day before expiry
    
    # Risk management
    max_positions: int = 2              # Max concurrent Iron Condors
    capital_per_trade_pct: float = 0.10 # 10% of capital per trade
    
    # Adjustment
    adjustment_threshold: float = 0.30  # Adjust if price within 30% of short strike


@dataclass
class IronCondorPosition:
    """Represents an Iron Condor position."""
    symbol: str
    entry_date: datetime
    expiry_date: datetime
    
    # Strikes
    short_put: float
    long_put: float
    short_call: float
    long_call: float
    
    # Premiums (at entry)
    short_put_premium: float
    long_put_premium: float
    short_call_premium: float
    long_call_premium: float
    
    # Position details
    lots: int
    net_premium_collected: float  # Total credit received
    max_profit: float
    max_loss: float
    
    # Status
    is_open: bool = True
    exit_date: Optional[datetime] = None
    exit_reason: str = ""
    realized_pnl: float = 0.0
    
    def __post_init__(self):
        self.lot_size = LOT_SIZES.get(self.symbol, 50)
        self.quantity = self.lots * self.lot_size


# ═══════════════════════════════════════════════════════════════════════════════
#                           STRIKE SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_atm_strike(spot_price: float, strike_gap: int = 50) -> float:
    """Get ATM strike closest to spot price."""
    return round(spot_price / strike_gap) * strike_gap


def select_iron_condor_strikes(
    spot_price: float,
    config: IronCondorConfig,
    symbol: str = 'NIFTY'
) -> Dict[str, float]:
    """
    Select strikes for Iron Condor based on spot price.
    
    For 15 delta (~85% OTM):
    - Short Put: ~1 std dev below ATM
    - Short Call: ~1 std dev above ATM
    - Wings: wing_width points outside shorts
    """
    strike_gap = 50 if symbol == 'NIFTY' else 100
    atm = calculate_atm_strike(spot_price, strike_gap)
    
    # Approximate delta calculation (using ~1% move per 15 delta)
    # For 15 delta, roughly 6-7% OTM
    otm_pct = 0.065  # 6.5% OTM
    
    short_put = calculate_atm_strike(spot_price * (1 - otm_pct), strike_gap)
    short_call = calculate_atm_strike(spot_price * (1 + otm_pct), strike_gap)
    
    return {
        'short_put': short_put,
        'long_put': short_put - config.wing_width,
        'short_call': short_call,
        'long_call': short_call + config.wing_width,
        'atm': atm,
        'spot': spot_price
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                           PREMIUM ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_option_premium(
    spot: float,
    strike: float,
    dte: int,
    is_call: bool,
    vix: float = 15.0
) -> float:
    """
    Estimate option premium using simplified Black-Scholes approximation.
    
    This is for backtesting - real trading uses actual market prices.
    """
    # Use VIX as volatility proxy (annualized)
    vol = vix / 100
    time_to_exp = dte / 365
    
    # Moneyness
    if is_call:
        otm_amount = strike - spot
    else:
        otm_amount = spot - strike
    
    otm_pct = otm_amount / spot
    
    # ATM premium approximation
    atm_premium = spot * vol * np.sqrt(time_to_exp) * 0.4
    
    # OTM decay (exponential)
    if otm_pct > 0:
        decay_factor = np.exp(-otm_pct * 20)  # Faster decay for OTM
        premium = atm_premium * decay_factor
    else:
        # ITM: add intrinsic value
        premium = atm_premium + abs(otm_amount)
    
    return max(premium, 0.5)  # Minimum premium


# ═══════════════════════════════════════════════════════════════════════════════
#                           STRATEGY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class IronCondorStrategy:
    """
    Iron Condor strategy engine.
    
    Usage:
        strategy = IronCondorStrategy(capital=100000, config=IronCondorConfig())
        
        # Check if should enter
        if strategy.should_enter(spot_price, vix, dte):
            position = strategy.create_position(spot_price, expiry, vix)
            strategy.add_position(position)
        
        # Check exits
        for pos in strategy.get_positions():
            if strategy.should_exit(pos, current_spot, current_dte):
                strategy.close_position(pos, current_spot)
    """
    
    def __init__(self, capital: float = 100000, config: IronCondorConfig = None):
        self.capital = capital
        self.config = config or IronCondorConfig()
        self.positions: List[IronCondorPosition] = []
        self.closed_positions: List[IronCondorPosition] = []
        
    def should_enter(
        self,
        spot_price: float,
        vix: float,
        dte: int,
        symbol: str = 'NIFTY'
    ) -> Tuple[bool, str]:
        """
        Check if conditions are right for new Iron Condor entry.
        
        Returns:
            (should_enter, reason)
        """
        # Check max positions
        open_count = len([p for p in self.positions if p.is_open])
        if open_count >= self.config.max_positions:
            return False, f"Max positions ({self.config.max_positions}) reached"
        
        # Check DTE
        if dte < self.config.min_dte:
            return False, f"DTE {dte} < min {self.config.min_dte}"
        if dte > self.config.max_dte:
            return False, f"DTE {dte} > max {self.config.max_dte}"
        
        # Check VIX
        if vix > self.config.max_vix:
            return False, f"VIX {vix:.1f} > max {self.config.max_vix}"
        
        # Check premium is sufficient
        strikes = select_iron_condor_strikes(spot_price, self.config, symbol)
        
        short_put_premium = estimate_option_premium(
            spot_price, strikes['short_put'], dte, False, vix
        )
        long_put_premium = estimate_option_premium(
            spot_price, strikes['long_put'], dte, False, vix
        )
        short_call_premium = estimate_option_premium(
            spot_price, strikes['short_call'], dte, True, vix
        )
        long_call_premium = estimate_option_premium(
            spot_price, strikes['long_call'], dte, True, vix
        )
        
        net_premium = (short_put_premium - long_put_premium + 
                       short_call_premium - long_call_premium)
        
        premium_ratio = net_premium / self.config.wing_width
        if premium_ratio < self.config.min_premium_collected:
            return False, f"Premium ratio {premium_ratio:.2%} < min {self.config.min_premium_collected:.0%}"
        
        return True, "All criteria met"
    
    def create_position(
        self,
        spot_price: float,
        expiry_date: datetime,
        vix: float,
        symbol: str = 'NIFTY'
    ) -> IronCondorPosition:
        """Create a new Iron Condor position."""
        dte = (expiry_date - datetime.now()).days
        
        strikes = select_iron_condor_strikes(spot_price, self.config, symbol)
        
        # Calculate premiums
        short_put_premium = estimate_option_premium(
            spot_price, strikes['short_put'], dte, False, vix
        )
        long_put_premium = estimate_option_premium(
            spot_price, strikes['long_put'], dte, False, vix
        )
        short_call_premium = estimate_option_premium(
            spot_price, strikes['short_call'], dte, True, vix
        )
        long_call_premium = estimate_option_premium(
            spot_price, strikes['long_call'], dte, True, vix
        )
        
        net_premium = (short_put_premium - long_put_premium + 
                       short_call_premium - long_call_premium)
        
        # Calculate lots based on capital allocation
        lot_size = LOT_SIZES.get(symbol, 50)
        max_loss_per_lot = (self.config.wing_width - net_premium) * lot_size
        capital_for_trade = self.capital * self.config.capital_per_trade_pct
        lots = max(1, int(capital_for_trade / max_loss_per_lot))
        
        position = IronCondorPosition(
            symbol=symbol,
            entry_date=datetime.now(),
            expiry_date=expiry_date,
            short_put=strikes['short_put'],
            long_put=strikes['long_put'],
            short_call=strikes['short_call'],
            long_call=strikes['long_call'],
            short_put_premium=short_put_premium,
            long_put_premium=long_put_premium,
            short_call_premium=short_call_premium,
            long_call_premium=long_call_premium,
            lots=lots,
            net_premium_collected=net_premium * lot_size * lots,
            max_profit=net_premium * lot_size * lots,
            max_loss=(self.config.wing_width - net_premium) * lot_size * lots
        )
        
        return position
    
    def add_position(self, position: IronCondorPosition):
        """Add position to portfolio."""
        self.positions.append(position)
        logger.info(f"Opened Iron Condor on {position.symbol}: "
                   f"{position.short_put}P/{position.short_call}C, "
                   f"Premium: Rs.{position.net_premium_collected:.0f}")
    
    def should_exit(
        self,
        position: IronCondorPosition,
        current_spot: float,
        current_dte: int
    ) -> Tuple[bool, str]:
        """Check if position should be exited."""
        if not position.is_open:
            return False, "Already closed"
        
        # Force exit before expiry
        if current_dte <= self.config.min_dte_exit:
            return True, "expiry_approaching"
        
        # Calculate current P&L (simplified)
        # In reality would use current option prices
        if current_spot < position.short_put:
            # Put side breached
            pnl_pct = -1.0
        elif current_spot > position.short_call:
            # Call side breached
            pnl_pct = -1.0
        else:
            # Within range - estimate time decay
            time_decay = 1 - (current_dte / max(1, (position.expiry_date - position.entry_date).days))
            pnl_pct = min(time_decay * 0.8, 1.0)  # 80% of max as target
        
        # Take profit
        if pnl_pct >= self.config.take_profit_pct:
            return True, "take_profit"
        
        # Stop loss
        if pnl_pct <= -self.config.stop_loss_pct:
            return True, "stop_loss"
        
        return False, "hold"
    
    def close_position(
        self,
        position: IronCondorPosition,
        current_spot: float,
        reason: str = "manual"
    ):
        """Close a position."""
        position.is_open = False
        position.exit_date = datetime.now()
        position.exit_reason = reason
        
        # Calculate realized P&L
        if current_spot >= position.long_put and current_spot <= position.long_call:
            # Expired within wings - max profit
            position.realized_pnl = position.max_profit
        elif current_spot < position.long_put:
            # Put side max loss
            position.realized_pnl = -position.max_loss
        elif current_spot > position.long_call:
            # Call side max loss
            position.realized_pnl = -position.max_loss
        elif current_spot < position.short_put:
            # Between short and long put
            loss = (position.short_put - current_spot) * position.quantity
            position.realized_pnl = position.net_premium_collected - loss
        else:
            # Between short and long call
            loss = (current_spot - position.short_call) * position.quantity
            position.realized_pnl = position.net_premium_collected - loss
        
        self.closed_positions.append(position)
        logger.info(f"Closed Iron Condor on {position.symbol}: "
                   f"P&L: Rs.{position.realized_pnl:.0f} ({reason})")
    
    def get_positions(self, open_only: bool = True) -> List[IronCondorPosition]:
        """Get positions."""
        if open_only:
            return [p for p in self.positions if p.is_open]
        return self.positions
    
    def get_portfolio_stats(self) -> Dict:
        """Get portfolio statistics."""
        open_positions = self.get_positions(open_only=True)
        closed = self.closed_positions
        
        total_realized_pnl = sum(p.realized_pnl for p in closed)
        wins = [p for p in closed if p.realized_pnl > 0]
        losses = [p for p in closed if p.realized_pnl <= 0]
        
        return {
            'total_trades': len(closed),
            'open_positions': len(open_positions),
            'total_pnl': total_realized_pnl,
            'win_rate': len(wins) / len(closed) * 100 if closed else 0,
            'avg_win': sum(p.realized_pnl for p in wins) / len(wins) if wins else 0,
            'avg_loss': sum(p.realized_pnl for p in losses) / len(losses) if losses else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           WFO COMPATIBLE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_signals_ic(df: pd.DataFrame, params: Dict = None) -> pd.Series:
    """
    Generate signals for Iron Condor backtesting.
    
    Signal = 1 on entry day, 0 otherwise
    (Iron Condors are weekly, not daily signals)
    """
    signals = pd.Series(0, index=df.index)
    
    # Simplified: enter every Thursday (weekly expiry)
    if isinstance(df.index, pd.DatetimeIndex):
        thursdays = df.index.dayofweek == 3
        signals[thursdays] = 1
    
    return signals


def optimize_parameters_ic(df: pd.DataFrame) -> Dict:
    """Return fixed iron condor parameters."""
    return {
        'wing_width': 50,
        'short_delta': 0.15,
        'take_profit_pct': 0.50,
        'stop_loss_pct': 1.00,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("IRON CONDOR STRATEGY - DEMO")
    print("=" * 60)
    
    # Create strategy
    strategy = IronCondorStrategy(capital=100000)
    
    # Simulate NIFTY price
    spot_price = 19500
    vix = 14.5
    expiry = datetime.now() + timedelta(days=7)
    dte = 7
    
    print(f"\nMarket Conditions:")
    print(f"  NIFTY: {spot_price}")
    print(f"  VIX: {vix}")
    print(f"  DTE: {dte}")
    
    # Check entry
    should_enter, reason = strategy.should_enter(spot_price, vix, dte, 'NIFTY')
    print(f"\nShould Enter: {should_enter}")
    print(f"Reason: {reason}")
    
    if should_enter:
        # Create position
        position = strategy.create_position(spot_price, expiry, vix, 'NIFTY')
        strategy.add_position(position)
        
        print(f"\nPosition Created:")
        print(f"  Short Put: {position.short_put}")
        print(f"  Long Put: {position.long_put}")
        print(f"  Short Call: {position.short_call}")
        print(f"  Long Call: {position.long_call}")
        print(f"  Premium Collected: Rs.{position.net_premium_collected:.0f}")
        print(f"  Max Profit: Rs.{position.max_profit:.0f}")
        print(f"  Max Loss: Rs.{position.max_loss:.0f}")
        print(f"  Lots: {position.lots}")
    else:
        # Create sample position for demo scenarios anyway
        position = strategy.create_position(spot_price, expiry, vix, 'NIFTY')
        print(f"\n(Creating sample position for scenario demo)")
        print(f"  Short Put: {position.short_put}")
        print(f"  Short Call: {position.short_call}")
    
    # Simulate exit scenarios
    print("\n" + "-" * 40)
    print("Exit Scenarios:")
    
    scenarios = [
        (19500, "Expiry at ATM"),
        (19200, "Short Put breached"),
        (19800, "Short Call breached"),
        (18800, "Max loss (Put)"),
        (20200, "Max loss (Call)"),
    ]
    
    for spot, desc in scenarios:
        pos_copy = IronCondorPosition(
            symbol='NIFTY',
            entry_date=datetime.now(),
            expiry_date=expiry,
            short_put=position.short_put,
            long_put=position.long_put,
            short_call=position.short_call,
            long_call=position.long_call,
            short_put_premium=position.short_put_premium,
            long_put_premium=position.long_put_premium,
            short_call_premium=position.short_call_premium,
            long_call_premium=position.long_call_premium,
            lots=position.lots,
            net_premium_collected=position.net_premium_collected,
            max_profit=position.max_profit,
            max_loss=position.max_loss
        )
        strategy.close_position(pos_copy, spot, "simulation")
        print(f"  {desc} ({spot}): P&L = Rs.{pos_copy.realized_pnl:,.0f}")
    
    print("\n" + "=" * 60)
