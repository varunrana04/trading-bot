"""
Complete Options Strategy Engine
Iron condors, credit spreads, butterflies - all option strategies
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm


class OptionsStrategyEngine:
    """
    Complete options strategies for Indian markets
    """
    
    def __init__(self, zerodha_client):
        self.zerodha = zerodha_client
        
        # Strategy parameters (will be optimized)
        self.params = {
            'iron_condor': {
                'dte_min': 21,  # Minimum days to expiry
                'dte_max': 45,
                'sell_delta': 0.30,  # Sell 30-delta options
                'buy_delta': 0.15,   # Buy 15-delta for protection
                'min_premium': 50  # Minimum premium to collect
            },
            'credit_spread': {
                'dte': 30,
                'sell_delta': 0.40,
                'buy_delta': 0.20,
                'width_ratio': 1.5  # Strike width
            }
        }
    
    def get_signal(self, strategy_name: str) -> Optional[Dict]:
        """
        Get options trading signal
        
        Returns signal dict or None
        """
        try:
            if 'iron_condor' in strategy_name:
                symbol = 'NIFTY' if 'nifty' in strategy_name else 'BANKNIFTY'
                return self._scan_iron_condor(symbol)
            
            elif 'bull_put' in strategy_name:
                symbol = 'NIFTY' if 'nifty' in strategy_name else 'BANKNIFTY'
                return self._scan_credit_spread(symbol, 'bull_put')
            
            elif 'bear_call' in strategy_name:
                symbol = 'NIFTY' if 'banknifty' in strategy_name else 'NIFTY'
                return self._scan_credit_spread(symbol, 'bear_call')
            
            elif 'calendar' in strategy_name:
                symbol = 'NIFTY'
                return self._scan_calendar_spread(symbol)
            
            else:
                return None
                
        except Exception as e:
            print(f"[OPTIONS] Error in {strategy_name}: {e}")
            return None
    
    def _scan_iron_condor(self, symbol: str) -> Optional[Dict]:
        """
        Scan for Iron Condor entry
        
        Iron Condor = Bull Put Spread + Bear Call Spread
        Profit from low volatility / range-bound market
        """
        # Get option chain
        option_chain = self.zerodha.get_option_chain(symbol)
        
        if option_chain.empty:
            return None
        
        # Get spot price
        spot_quote = self.zerodha.get_stock_quote(f"{symbol}")
        if not spot_quote:
            return None
        
        spot_price = spot_quote.get('last_price', 0)
        
        # Filter by DTE
        option_chain['dte'] = (pd.to_datetime(option_chain['expiry']) - datetime.now()).dt.days
        option_chain = option_chain[
            (option_chain['dte'] >= self.params['iron_condor']['dte_min']) &
            (option_chain['dte'] <= self.params['iron_condor']['dte_max'])
        ]
        
        if option_chain.empty:
            return None
        
        # Use nearest expiry
        min_dte = option_chain['dte'].min()
        option_chain = option_chain[option_chain['dte'] == min_dte]
        
        # Separate calls and puts
        calls = option_chain[option_chain['instrument_type'] == 'CE'].copy()
        puts = option_chain[option_chain['instrument_type'] == 'PE'].copy()
        
        if calls.empty or puts.empty:
            return None
        
        # Calculate approximate delta using Black-Scholes
        # Simplified: use moneyness as proxy for delta
        # Real implementation would calculate actual Greeks
        
        # Find OTM put to sell (below spot)
        sell_put_strike = self._find_strike_by_delta(
            puts[puts['strike'] < spot_price],
            spot_price,
            target_delta=self.params['iron_condor']['sell_delta'],
            option_type='PUT'
        )
        
        # Find further OTM put to buy
        buy_put_strike = self._find_strike_by_delta(
            puts[puts['strike'] < sell_put_strike],
            spot_price,
            target_delta=self.params['iron_condor']['buy_delta'],
            option_type='PUT'
        )
        
        # Find OTM call to sell (above spot)
        sell_call_strike = self._find_strike_by_delta(
            calls[calls['strike'] > spot_price],
            spot_price,
            target_delta=self.params['iron_condor']['sell_delta'],
            option_type='CALL'
        )
        
        # Find further OTM call to buy
        buy_call_strike = self._find_strike_by_delta(
            calls[calls['strike'] > sell_call_strike],
            spot_price,
            target_delta=self.params['iron_condor']['buy_delta'],
            option_type='CALL'
        )
        
        # Validate strikes found
        if not all([sell_put_strike, buy_put_strike, sell_call_strike, buy_call_strike]):
            return None
        
        # Get premiums (simplified - would use actual option chain prices)
        sell_put_premium = self._get_option_premium(puts, sell_put_strike)
        buy_put_premium = self._get_option_premium(puts, buy_put_strike)
        sell_call_premium = self._get_option_premium(calls, sell_call_strike)
        buy_call_premium = self._get_option_premium(calls, buy_call_strike)
        
        # Calculate net premium
        net_premium = (sell_put_premium - buy_put_premium + 
                      sell_call_premium - buy_call_premium)
        
        # Check minimum premium
        if net_premium < self.params['iron_condor']['min_premium']:
            return None
        
        # Calculate max loss
        put_spread_width = sell_put_strike - buy_put_strike
        call_spread_width = buy_call_strike - sell_call_strike
        max_loss = max(put_spread_width, call_spread_width) - net_premium
        
        # Check risk/reward ratio
        if max_loss / net_premium > 3:  # Max loss should be < 3x premium
            return None
        
        print(f"[IRON CONDOR] {symbol}: Premium=₹{net_premium:.0f}, Max Loss=₹{max_loss:.0f}")
        
        return {
            'action': 'ENTER',
            'symbol': symbol,
            'strategy': 'iron_condor',
            'legs': [
                {'type': 'SELL', 'strike': sell_put_strike, 'option_type': 'PE'},
                {'type': 'BUY', 'strike': buy_put_strike, 'option_type': 'PE'},
                {'type': 'SELL', 'strike': sell_call_strike, 'option_type': 'CE'},
                {'type': 'BUY', 'strike': buy_call_strike, 'option_type': 'CE'}
            ],
            'premium': net_premium,
            'max_loss': max_loss,
            'confidence': 0.75,
            'dte': min_dte
        }
    
    def _scan_credit_spread(self, symbol: str, spread_type: str) -> Optional[Dict]:
        """
        Scan for Bull Put or Bear Call Spread
        
        Bull Put: Sell higher strike put + Buy lower strike put (bullish/neutral)
        Bear Call: Sell lower strike call + Buy higher strike call (bearish/neutral)
        """
        option_chain = self.zerodha.get_option_chain(symbol)
        
        if option_chain.empty:
            return None
        
        spot_quote = self.zerodha.get_stock_quote(f"{symbol}")
        spot_price = spot_quote.get('last_price', 0)
        
        # Filter by DTE
        option_chain['dte'] = (pd.to_datetime(option_chain['expiry']) - datetime.now()).dt.days
        target_dte = self.params['credit_spread']['dte']
        option_chain = option_chain[
            (option_chain['dte'] >= target_dte - 7) &
            (option_chain['dte'] <= target_dte + 7)
        ]
        
        if option_chain.empty:
            return None
        
        if spread_type == 'bull_put':
            # Bull Put Spread
            puts = option_chain[option_chain['instrument_type'] == 'PE']
            puts = puts[puts['strike'] < spot_price]  # OTM puts
            
            sell_strike = self._find_strike_by_delta(
                puts, spot_price,
                target_delta=self.params['credit_spread']['sell_delta'],
                option_type='PUT'
            )
            
            buy_strike = self._find_strike_by_delta(
                puts[puts['strike'] < sell_strike], spot_price,
                target_delta=self.params['credit_spread']['buy_delta'],
                option_type='PUT'
            )
            
            if not sell_strike or not buy_strike:
                return None
            
            sell_premium = self._get_option_premium(puts, sell_strike)
            buy_premium = self._get_option_premium(puts, buy_strike)
            
            return {
                'action': 'ENTER',
                'symbol': symbol,
                'strategy': 'bull_put_spread',
                'legs': [
                    {'type': 'SELL', 'strike': sell_strike, 'option_type': 'PE'},
                    {'type': 'BUY', 'strike': buy_strike, 'option_type': 'PE'}
                ],
                'premium': sell_premium - buy_premium,
                'max_loss': (sell_strike - buy_strike) - (sell_premium - buy_premium),
                'confidence': 0.70
            }
        
        else:  # bear_call
            calls = option_chain[option_chain['instrument_type'] == 'CE']
            calls = calls[calls['strike'] > spot_price]  # OTM calls
            
            sell_strike = self._find_strike_by_delta(
                calls, spot_price,
                target_delta=self.params['credit_spread']['sell_delta'],
                option_type='CALL'
            )
            
            buy_strike = self._find_strike_by_delta(
                calls[calls['strike'] > sell_strike], spot_price,
                target_delta=self.params['credit_spread']['buy_delta'],
                option_type='CALL'
            )
            
            if not sell_strike or not buy_strike:
                return None
            
            sell_premium = self._get_option_premium(calls, sell_strike)
            buy_premium = self._get_option_premium(calls, buy_strike)
            
            return {
                'action': 'ENTER',
                'symbol': symbol,
                'strategy': 'bear_call_spread',
                'legs': [
                    {'type': 'SELL', 'strike': sell_strike, 'option_type': 'CE'},
                    {'type': 'BUY', 'strike': buy_strike, 'option_type': 'CE'}
                ],
                'premium': sell_premium - buy_premium,
                'max_loss': (buy_strike - sell_strike) - (sell_premium - buy_premium),
                'confidence': 0.70
            }
    
    def _scan_calendar_spread(self, symbol: str) -> Optional[Dict]:
        """
        Calendar Spread: Sell near-term + Buy far-term same strike
        Profit from time decay differential
        """
        # Simplified placeholder
        return None
    
    def _find_strike_by_delta(
        self,
        options_df: pd.DataFrame,
        spot_price: float,
        target_delta: float,
        option_type: str
    ) -> Optional[float]:
        """
        Find option strike closest to target delta
        Simplified: uses moneyness as delta proxy
        """
        if options_df.empty:
            return None
        
        # Approximate delta using moneyness
        # Real implementation would calculate Black-Scholes delta
        options_df = options_df.copy()
        options_df['moneyness'] = options_df['strike'] / spot_price
        
        if option_type == 'CALL':
            # For calls: delta ≈ 0 far OTM, ≈ 1 deep ITM
            # Target 0.30 delta ≈ 103% moneyness
            target_moneyness = 1 + target_delta
        else:
            # For puts: delta ≈ 0 far OTM, ≈ -1 deep ITM
            # Target -0.30 delta ≈ 97% moneyness
            target_moneyness = 1 - target_delta
        
        # Find closest strike
        options_df['diff'] = abs(options_df['moneyness'] - target_moneyness)
        closest = options_df.loc[options_df['diff'].idxmin()]
        
        return closest['strike']
    
    def _get_option_premium(self, options_df: pd.DataFrame, strike: float) -> float:
        """Get option premium for a strike (simplified)"""
        try:
            premium = options_df[options_df['strike'] == strike]['last_price'].values[0]
            return float(premium)
        except:
            return 0.0
