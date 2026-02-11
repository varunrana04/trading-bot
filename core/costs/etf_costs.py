"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       GOLD/SILVER ETF COSTS                                   ║
║                                                                               ║
║  Cost modeling for Gold/Silver ETF trading with correlation tracking.        ║
║  Covers: Nippon Gold ETF, Nippon Silver ETF, Tata Silver ETF                  ║
║  Correlation: XAUUSD, XAGUSD, MCX Gold/Silver, Shanghai                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Factors included:
- ETF expense ratios
- Tracking error estimation
- INR/USD correlation adjustments
- Customs duty and import premium
- Trading costs (same as equity on Zerodha)

Author: Bot_Algo
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
from enum import Enum
import logging

logger = logging.getLogger("ETFCosts")


# ═══════════════════════════════════════════════════════════════════════════════
#                           ETF DATA
# ═══════════════════════════════════════════════════════════════════════════════

class GoldSilverETF(Enum):
    """Available Gold/Silver ETFs in India"""
    NIPPON_GOLD = "GOLDBEES"         # Nippon India ETF Gold BeES
    NIPPON_SILVER = "SILVERBEES"     # Nippon India Silver ETF
    TATA_SILVER = "TATAGOLD"         # Tata Silver ETF (placeholder)
    SBI_GOLD = "SBIGETS"             # SBI Gold ETF
    HDFC_GOLD = "HDFCGOLD"           # HDFC Gold ETF


@dataclass
class ETFDetails:
    """Details for a specific ETF"""
    symbol: str
    name: str
    expense_ratio: float        # Annual expense ratio (%)
    tracking_error: float       # Annual tracking error (%)
    underlying: str             # Physical gold/silver
    benchmark: str              # International benchmark
    lot_size: int = 1           # ETFs trade in units of 1


# ETF Database
ETF_DATA = {
    GoldSilverETF.NIPPON_GOLD: ETFDetails(
        symbol="GOLDBEES",
        name="Nippon India ETF Gold BeES",
        expense_ratio=0.80,      # 0.80% annual
        tracking_error=0.04,     # 0.04% average
        underlying="Physical Gold (99.5% purity)",
        benchmark="Domestic Gold Price"
    ),
    GoldSilverETF.NIPPON_SILVER: ETFDetails(
        symbol="SILVERBEES",
        name="Nippon India Silver ETF",
        expense_ratio=0.56,      # 0.56% annual
        tracking_error=0.50,     # Higher for silver
        underlying="Physical Silver",
        benchmark="Domestic Silver Price"
    ),
    GoldSilverETF.TATA_SILVER: ETFDetails(
        symbol="TATAGOLD",
        name="Tata Silver ETF",
        expense_ratio=0.45,
        tracking_error=0.40,
        underlying="Physical Silver",
        benchmark="Domestic Silver Price"
    )
}


@dataclass
class CorrelationFactors:
    """Factors affecting India vs International price correlation"""
    
    # Basic Customs Duty + Social Welfare Surcharge
    CUSTOMS_DUTY_GOLD: float = 0.1075      # 10.75% on gold
    CUSTOMS_DUTY_SILVER: float = 0.1075    # 10.75% on silver
    
    # Insurance and Freight (approximate)
    INSURANCE_FREIGHT: float = 0.005       # 0.5%
    
    # Warehouse/Delivery overheads
    WAREHOUSE_OVERHEAD: float = 0.002      # 0.2%
    
    # Total import premium (all inclusive)
    @property
    def total_gold_premium(self) -> float:
        return self.CUSTOMS_DUTY_GOLD + self.INSURANCE_FREIGHT + self.WAREHOUSE_OVERHEAD
    
    @property
    def total_silver_premium(self) -> float:
        return self.CUSTOMS_DUTY_SILVER + self.INSURANCE_FREIGHT + self.WAREHOUSE_OVERHEAD


@dataclass
class TradingCosts:
    """Zerodha equity/ETF trading costs"""
    
    # Brokerage
    BROKERAGE_PER_ORDER: float = 20.0      # ₹20 or 0.03% whichever is lower
    
    # STT (Securities Transaction Tax) - Delivery
    STT_DELIVERY: float = 0.001            # 0.1% on both buy and sell
    
    # Exchange Transaction Charges
    NSE_CHARGE: float = 0.0000325          # 0.00325%
    
    # GST
    GST_RATE: float = 0.18                 # 18%
    
    # Stamp Duty
    STAMP_DUTY: float = 0.00015            # 0.015% (on buy)
    
    # SEBI Turnover Fee
    SEBI_FEE: float = 0.000001             # ₹1 per crore
    
    # Demat Transaction Charges
    DEMAT_CHARGES: float = 13.5            # ₹13.5 per month (approx)


# ═══════════════════════════════════════════════════════════════════════════════
#                           COST CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class GoldSilverETFCosts:
    """
    Complete Gold/Silver ETF cost calculator with correlation tracking.
    
    Usage:
        calc = GoldSilverETFCosts(GoldSilverETF.NIPPON_GOLD)
        
        # Calculate trade costs
        costs = calc.calculate_trade_cost(
            price=5000,
            quantity=10,
            is_buy=True
        )
        
        # Estimate Indian price from international
        indian_price = calc.estimate_indian_price(
            international_price=2000,  # XAUUSD per ounce
            usd_inr=83.0
        )
    """
    
    def __init__(self, etf: GoldSilverETF):
        """
        Initialize calculator for specific ETF.
        
        Args:
            etf: The Gold/Silver ETF to calculate for
        """
        self.etf = etf
        self.details = ETF_DATA.get(etf)
        self.correlation = CorrelationFactors()
        self.costs = TradingCosts()
        
        if self.details is None:
            raise ValueError(f"Unknown ETF: {etf}")
        
        logger.debug(f"ETF cost calculator initialized for {self.details.name}")
    
    def calculate_trade_cost(
        self,
        price: float,
        quantity: int,
        is_buy: bool = True,
        holding_days: int = 1
    ) -> Dict[str, float]:
        """
        Calculate all costs for an ETF trade.
        
        Args:
            price: ETF price per unit
            quantity: Number of units
            is_buy: True for buy, False for sell
            holding_days: Expected holding period in days
            
        Returns:
            Dict with complete cost breakdown
        """
        turnover = price * quantity
        
        # Brokerage (min of ₹20 or 0.03%)
        brokerage = min(self.costs.BROKERAGE_PER_ORDER, turnover * 0.0003)
        
        # STT (on both buy and sell for delivery)
        stt = turnover * self.costs.STT_DELIVERY
        
        # Exchange charges
        exchange_charges = turnover * self.costs.NSE_CHARGE
        
        # SEBI fees
        sebi_fees = turnover * self.costs.SEBI_FEE
        
        # GST on (brokerage + exchange + SEBI)
        gst = (brokerage + exchange_charges + sebi_fees) * self.costs.GST_RATE
        
        # Stamp duty (buy side only)
        stamp_duty = turnover * self.costs.STAMP_DUTY if is_buy else 0
        
        # Total trading cost (one side)
        trading_cost = brokerage + stt + exchange_charges + sebi_fees + gst + stamp_duty
        
        # Expense ratio impact (prorated for holding period)
        daily_expense = (self.details.expense_ratio / 100) / 365
        expense_impact = turnover * daily_expense * holding_days
        
        # Tracking error impact
        daily_tracking = (self.details.tracking_error / 100) / 365
        tracking_impact = turnover * daily_tracking * holding_days
        
        return {
            'etf': self.details.symbol,
            'price': price,
            'quantity': quantity,
            'turnover': turnover,
            'brokerage': brokerage,
            'stt': stt,
            'exchange_charges': exchange_charges,
            'sebi_fees': sebi_fees,
            'gst': gst,
            'stamp_duty': stamp_duty,
            'trading_cost': trading_cost,
            'holding_days': holding_days,
            'expense_ratio_impact': expense_impact,
            'tracking_error_impact': tracking_impact,
            'total_one_way': trading_cost,
            'total_round_trip': trading_cost * 2 + expense_impact + tracking_impact
        }
    
    def estimate_indian_price(
        self,
        international_price: float,
        usd_inr: float,
        metal: str = 'gold'
    ) -> Dict[str, float]:
        """
        Estimate Indian price from international price.
        
        For Gold: 1 troy ounce = 31.1035 grams
        For Silver: 1 troy ounce = 31.1035 grams
        
        Args:
            international_price: XAUUSD or XAGUSD price per troy ounce
            usd_inr: Current USD/INR exchange rate
            metal: 'gold' or 'silver'
            
        Returns:
            Dict with price conversion details
        """
        # Troy ounce to grams
        GRAMS_PER_OUNCE = 31.1035
        
        # Get premium based on metal
        if metal.lower() == 'gold':
            premium = self.correlation.total_gold_premium
        else:
            premium = self.correlation.total_silver_premium
        
        # Base price in INR per gram
        base_price_per_gram = (international_price / GRAMS_PER_OUNCE) * usd_inr
        
        # Add import premium
        indian_price_per_gram = base_price_per_gram * (1 + premium)
        
        # 10 gram price (common unit for gold)
        price_10g = indian_price_per_gram * 10
        
        # 1 kg price (common for silver)
        price_1kg = indian_price_per_gram * 1000
        
        return {
            'international_price_oz': international_price,
            'usd_inr': usd_inr,
            'metal': metal,
            'base_price_per_gram_inr': base_price_per_gram,
            'import_premium_pct': premium * 100,
            'indian_price_per_gram': indian_price_per_gram,
            'price_10g': price_10g,
            'price_1kg': price_1kg,
            'etf_approx_price': indian_price_per_gram  # ETFs typically track 1g
        }
    
    def calculate_correlation_opportunity(
        self,
        international_price: float,
        indian_etf_price: float,
        usd_inr: float,
        metal: str = 'gold'
    ) -> Dict[str, float]:
        """
        Identify arbitrage opportunities between international and Indian prices.
        
        Args:
            international_price: XAUUSD or XAGUSD
            indian_etf_price: Current ETF price
            usd_inr: USD/INR rate
            metal: 'gold' or 'silver'
            
        Returns:
            Dict with correlation analysis
        """
        estimated = self.estimate_indian_price(international_price, usd_inr, metal)
        fair_value = estimated['indian_price_per_gram']
        
        # Premium/discount to fair value
        premium_discount = ((indian_etf_price - fair_value) / fair_value) * 100
        
        # Historical typical range
        typical_premium_range = (-2.0, 3.0)  # -2% to +3% is normal
        
        opportunity = 'NONE'
        if premium_discount < typical_premium_range[0]:
            opportunity = 'BUY'  # ETF trading at unusual discount
        elif premium_discount > typical_premium_range[1]:
            opportunity = 'SELL'  # ETF trading at unusual premium
        
        return {
            'international_price': international_price,
            'indian_etf_price': indian_etf_price,
            'fair_value': fair_value,
            'premium_discount_pct': premium_discount,
            'typical_range': typical_premium_range,
            'opportunity': opportunity,
            'confidence': 'HIGH' if abs(premium_discount) > 5.0 else 'LOW'
        }
    
    def estimate_holding_return(
        self,
        buy_price: float,
        sell_price: float,
        quantity: int,
        holding_days: int
    ) -> Dict[str, float]:
        """
        Calculate net return after all costs.
        
        Args:
            buy_price: Entry price
            sell_price: Exit price
            quantity: Number of units
            holding_days: Holding period
            
        Returns:
            Dict with return analysis
        """
        # Gross P&L
        gross_pnl = (sell_price - buy_price) * quantity
        gross_return_pct = ((sell_price - buy_price) / buy_price) * 100
        
        # Buy costs
        buy_costs = self.calculate_trade_cost(buy_price, quantity, is_buy=True, holding_days=holding_days)
        
        # Sell costs
        sell_costs = self.calculate_trade_cost(sell_price, quantity, is_buy=False, holding_days=0)
        
        # Total costs
        total_costs = buy_costs['trading_cost'] + sell_costs['trading_cost'] + \
                      buy_costs['expense_ratio_impact'] + buy_costs['tracking_error_impact']
        
        # Net P&L
        net_pnl = gross_pnl - total_costs
        investment = buy_price * quantity
        net_return_pct = (net_pnl / investment) * 100
        
        return {
            'buy_price': buy_price,
            'sell_price': sell_price,
            'quantity': quantity,
            'investment': investment,
            'gross_pnl': gross_pnl,
            'gross_return_pct': gross_return_pct,
            'total_costs': total_costs,
            'net_pnl': net_pnl,
            'net_return_pct': net_return_pct,
            'holding_days': holding_days,
            'annualized_return': (net_return_pct / holding_days) * 365 if holding_days > 0 else 0
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                           MULTI-ETF COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

def compare_etfs(metal: str = 'gold') -> Dict:
    """
    Compare available ETFs for a metal type.
    
    Args:
        metal: 'gold' or 'silver'
        
    Returns:
        Comparison of ETF costs and characteristics
    """
    if metal.lower() == 'gold':
        etfs = [GoldSilverETF.NIPPON_GOLD, GoldSilverETF.SBI_GOLD, GoldSilverETF.HDFC_GOLD]
    else:
        etfs = [GoldSilverETF.NIPPON_SILVER, GoldSilverETF.TATA_SILVER]
    
    comparison = []
    for etf in etfs:
        if etf in ETF_DATA:
            details = ETF_DATA[etf]
            comparison.append({
                'symbol': details.symbol,
                'name': details.name,
                'expense_ratio': details.expense_ratio,
                'tracking_error': details.tracking_error,
                'total_annual_drag': details.expense_ratio + details.tracking_error
            })
    
    return {
        'metal': metal,
        'etfs': comparison,
        'recommended': min(comparison, key=lambda x: x['total_annual_drag']) if comparison else None
    }


def print_cost_breakdown(
    etf: GoldSilverETF,
    price: float = 5000,
    quantity: int = 10,
    holding_days: int = 30
):
    """Print detailed cost breakdown."""
    calc = GoldSilverETFCosts(etf)
    
    print(f"\n{'='*60}")
    print(f"GOLD/SILVER ETF COSTS - {calc.details.name}")
    print(f"Price: Rs.{price} | Qty: {quantity} | Hold: {holding_days} days")
    print(f"{'='*60}")
    
    costs = calc.calculate_trade_cost(price, quantity, is_buy=True, holding_days=holding_days)
    
    print(f"\nETF Details:")
    print(f"  Expense Ratio:    {calc.details.expense_ratio}% annually")
    print(f"  Tracking Error:   {calc.details.tracking_error}% annually")
    
    print(f"\nTrading Costs (One-Way):")
    print(f"  Brokerage:        ₹{costs['brokerage']:.2f}")
    print(f"  STT:              ₹{costs['stt']:.2f}")
    print(f"  Exchange Charges: ₹{costs['exchange_charges']:.4f}")
    print(f"  SEBI Fees:        ₹{costs['sebi_fees']:.6f}")
    print(f"  GST:              ₹{costs['gst']:.2f}")
    print(f"  Stamp Duty:       ₹{costs['stamp_duty']:.2f}")
    print(f"  {'-'*40}")
    print(f"  TOTAL (One-Way):  ₹{costs['total_one_way']:.2f}")
    
    print(f"\nHolding Costs ({holding_days} days):")
    print(f"  Expense Ratio:    ₹{costs['expense_ratio_impact']:.2f}")
    print(f"  Tracking Error:   ₹{costs['tracking_error_impact']:.2f}")
    
    print(f"\n  TOTAL ROUND-TRIP: ₹{costs['total_round_trip']:.2f}")
    print(f"  As % of Investment: {(costs['total_round_trip'] / costs['turnover']) * 100:.3f}%")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo: Nippon Gold ETF
    print_cost_breakdown(GoldSilverETF.NIPPON_GOLD, price=5000, quantity=10, holding_days=30)
    
    # Demo: Nippon Silver ETF
    print_cost_breakdown(GoldSilverETF.NIPPON_SILVER, price=70, quantity=100, holding_days=30)
    
    # Price estimation
    calc = GoldSilverETFCosts(GoldSilverETF.NIPPON_GOLD)
    estimate = calc.estimate_indian_price(
        international_price=2000,  # XAUUSD at $2000/oz
        usd_inr=83.0,
        metal='gold'
    )
    print(f"\nPrice Estimation (XAUUSD $2000, USD/INR 83):")
    print(f"  Base price/gram:  ₹{estimate['base_price_per_gram_inr']:.2f}")
    print(f"  Import premium:   {estimate['import_premium_pct']:.2f}%")
    print(f"  Indian price/gram: ₹{estimate['indian_price_per_gram']:.2f}")
    print(f"  Price per 10g:    ₹{estimate['price_10g']:,.2f}")
    
    # Correlation opportunity
    opp = calc.calculate_correlation_opportunity(
        international_price=2000,
        indian_etf_price=5200,  # Example ETF price
        usd_inr=83.0,
        metal='gold'
    )
    print(f"\nCorrelation Analysis:")
    print(f"  Fair Value:       ₹{opp['fair_value']:.2f}")
    print(f"  Current ETF:      ₹{opp['indian_etf_price']:.2f}")
    print(f"  Premium/Discount: {opp['premium_discount_pct']:.2f}%")
    print(f"  Opportunity:      {opp['opportunity']}")
    
    # ETF Comparison
    comparison = compare_etfs('gold')
    print(f"\nGold ETF Comparison:")
    for etf in comparison['etfs']:
        print(f"  {etf['symbol']}: ER={etf['expense_ratio']}%, TE={etf['tracking_error']}%")
