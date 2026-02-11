"""
DYNAMIC HEDGING SIMULATOR - Standalone System
Based on Options Volatility & Pricing Ch 8 (Natenberg)

Implements option replication through continuous delta hedging
Theoretical value = PV(sum of all cash flows)
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Literal
from greeks_calculator import GreeksCalculator

class DynamicHedgingSimulator:
    """
    Replicate option position through dynamic delta hedging
    
    Key Principle (Natenberg Ch 8):
    "In theory, we can replicate an option position through a dynamic hedging  
    process. The cost of this replication is equal to the sum of all the cash 
    flows resulting from the dynamic hedging process. The present value of 
    this sum is equal to the option's theoretical value."
    """
    
    def __init__(self, option_position: int, spot: float, strike: float,
                 expiry_days: int, volatility: float, risk_free_rate: float = 0.05,
                 option_type: Literal['call', 'put'] = 'call'):
        """
        Args:
            option_position: +1 for long, -1 for short
            spot: Initial underlying price
            strike: Strike price
            expiry_days: Days to expiration
            volatility: Annual volatility
            risk_free_rate: Risk-free rate
            option_type: 'call' or 'put'
        """
        self.position = option_position
        self.S0 = spot
        self.K = strike
        self.expiry_days = expiry_days
        self.sigma = volatility
        self.r = risk_free_rate
        self.option_type = option_type
        
        self.cash_flows = []
        self.hedging_log = []
        
    def simulate_price_path(self, num_days: int = None) -> np.ndarray:
        """
        Generate realistic price path using Geometric Brownian Motion
        
        dS = μ*S*dt + σ*S*dW
        """
        if num_days is None:
            num_days = self.expiry_days
        
        dt = 1/252  # Daily steps
        drift = self.r * dt
        diffusion = self.sigma * np.sqrt(dt)
        
        prices = [self.S0]
        for _ in range(num_days):
            random_shock = np.random.normal(0, 1)
            price_change = prices[-1] * (drift + diffusion * random_shock)
            new_price = prices[-1] + price_change
            prices.append(max(new_price, 0.01))  # Prevent negative prices
        
        return np.array(prices)
    
    def run_simulation(self, price_path: np.ndarray = None, 
                       rehedge_frequency: str = 'daily') -> Dict:
        """
        Execute dynamic hedging simulation
        
        Args:
            price_path: Custom price path (or None to generate)
            rehedge_frequency: 'daily', 'hourly', or 'continuous'
            
        Returns:
            Simulation results with P/L breakdown
        """
        if price_path is None:
            price_path = self.simulate_price_path()
        
        shares_held = 0  # Hedge position in underlying
        total_cash_flow = 0
        
        for day, spot_price in enumerate(price_path[:-1]):  # Exclude last day
            time_left = max((self.expiry_days - day) / 365, 0.001)
            
            # Calculate option's delta
            calc = GreeksCalculator(spot_price, self.K, time_left, self.sigma, self.r)
            option_delta = calc.delta(self.option_type)
            
            # Required hedge position (opposite to option delta)
            required_shares = -self.position * option_delta
            
            # Trade to rebalance
            shares_to_trade = required_shares - shares_held
            cash_flow = -shares_to_trade * spot_price  # Negative = cash out
            
            total_cash_flow += cash_flow
            shares_held = required_shares
            
            # Log this hedge
            self.hedging_log.append({
                'day': day,
                'spot_price': spot_price,
                'time_left_years': time_left,
                'option_delta': option_delta,
                'shares_held': shares_held,
                'shares_traded': shares_to_trade,
                'cash_flow': cash_flow,
                'cumulative_cash_flow': total_cash_flow
            })
        
        # Final settlement at expiration
        final_spot = price_path[-1]
        if self.option_type == 'call':
            option_payoff = max(final_spot - self.K, 0)
        else:
            option_payoff = max(self.K - final_spot, 0)
        
        # Unwind hedge position
        final_cash_flow = shares_held * final_spot
        total_cash_flow += final_cash_flow
        
        # Add option payoff
        total_pnl = total_cash_flow - (self.position * option_payoff)
        
        # Calculate theoretical value
        calc_initial = GreeksCalculator(self.S0, self.K, self.expiry_days/365, 
                                        self.sigma, self.r)
        theo_value = calc_initial.price(self.option_type)
        
        # Present value of cash flows
        pv_cash_flows = sum(
            cf['cash_flow'] / ((1 + self.r)**(cf['day']/365))
            for cf in self.hedging_log
        )
        pv_final = final_cash_flow / ((1 + self.r)**(self.expiry_days/365))
        total_pv = pv_cash_flows + pv_final
        
        return {
            'theoretical_value': theo_value * self.position,
            'total_cash_flow': total_cash_flow,
            'present_value': total_pv,
            'final_pnl': total_pnl,
            'replication_error': total_pv - (theo_value * self.position),
            'num_rehedges': len(self.hedging_log),
            'final_spot': final_spot,
            'option_payoff': option_payoff * self.position
        }
    
    def get_hedging_df(self) -> pd.DataFrame:
        """Return hedging history as DataFrame"""
        return pd.DataFrame(self.hedging_log)
    
    def plot_cash_flows(self):
        """Visualize cash flows over time"""
        if not self.hedging_log:
            print("No simulation data available")
            return
        
        df = self.get_hedging_df()
        
        print("\n" + "="*80)
        print("DYNAMIC HEDGING CASH FLOW SUMMARY")
        print("="*80)
        print(f"\nTotal Rehedges: {len(df)}")
        print(f"Avg Daily Cash Flow: Rs.{df['cash_flow'].mean():.2f}")
        print(f"Max Single Cash Flow: Rs.{df['cash_flow'].abs().max():.2f}")
        print(f"Final Cumulative: Rs.{df['cumulative_cash_flow'].iloc[-1]:.2f}")
        print("\n" + "="*80)


# Example - Standalone execution
if __name__ == "__main__":
    print("="*80)
    print("DYNAMIC HEDGING SIMULATOR - Standalone System")
    print("Based on Natenberg Ch 8")
    print("="*80)
    
    # Example: Hedge a short call position
    simulator = DynamicHedgingSimulator(
        option_position=-1,  # Short 1 call
        spot=23500,
        strike=23500,  # ATM
        expiry_days=30,
        volatility=0.20,
        risk_free_rate=0.07,  option_type='call'
    )
    
    print("\nRunning simulation...")
    print("  Position: SHORT 1 ATM Call")
    print("  Underlying: NIFTY @ 23500")
    print("  Expiry: 30 days")
    print("  Volatility: 20%")
    
    # Run simulation
    results = simulator.run_simulation()
    
    print("\n" + "-"*80)
    print("SIMULATION RESULTS")
    print("-"*80)
    print(f"Theoretical Value:  Rs.{results['theoretical_value']:.2f}")
    print(f"Replication PV:     Rs.{results['present_value']:.2f}")
    print(f"Replication Error:  Rs.{results['replication_error']:.2f}")
    print(f"Final P/L:          Rs.{results['final_pnl']:.2f}")
    print(f"\nNumber of Rehedges: {results['num_rehedges']}")
    print(f"Final Spot Price:   Rs.{results['final_spot']:.2f}")
    print(f"Option Payoff:      Rs.{results['option_payoff']:.2f}")
    print("\n" + "="*80)
    
    # Show cash flow summary
    simulator.plot_cash_flows()
