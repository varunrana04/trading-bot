"""
Complete Crypto Arbitrage Strategy Implementation
Funding rate arb, basis trading, pairs trading, mean reversion
"""

from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class CryptoArbitrageEngine:
    """
    Market-neutral and directional crypto strategies
    """
    
    def __init__(self, binance_client):
        self.binance = binance_client
        
        # Strategy thresholds
        self.funding_arb_threshold = 0.02  # 0.02% per 8h = ~21% APY
        self.basis_threshold_high = 0.5  # 0.5% basis
        self.basis_threshold_low = 0.1
        self.pairs_z_threshold = 2.0
        
        # Historical data for pairs trading
        self.btc_eth_history = []
        self.hedge_ratio = 0.037  # Approximate BTC/ETH ratio
        
    def get_signal(self, strategy_name: str) -> Optional[Dict]:
        """
        Get crypto signal based on strategy
        
        Returns signal dict or None
        """
        try:
            if strategy_name == 'funding_rate_arb':
                return self._funding_rate_arbitrage()
            
            elif strategy_name == 'basis_trading':
                return self._basis_trading()
            
            elif strategy_name == 'btc_eth_pairs':
                return self._btc_eth_pairs_trading()
            
            elif strategy_name == 'mean_reversion_btc':
                return self._mean_reversion('BTCUSDT')
            
            elif strategy_name == 'momentum_breakout':
                return self._momentum_breakout('BTCUSDT')
            
            else:
                return None
                
        except Exception as e:
            print(f"[CRYPTO] Error in {strategy_name}: {e}")
            return None
    
    def _funding_rate_arbitrage(self) -> Optional[Dict]:
        """
        Funding Rate Arbitrage
        
        If funding rate is high and positive:
        - SHORT perpetual futures
        - BUY spot (hedge)
        - Collect funding payments
        """
        symbol = 'BTCUSDT'
        
        # Get current funding rate
        funding_rate = self.binance.get_funding_rate(symbol)
        
        # Annualize funding rate (paid every 8 hours)
        annualized_rate = funding_rate * 3 * 365  # 3 payments per day
        
        print(f"[FUNDING ARB] Current: {funding_rate:.4f} ({annualized_rate*100:.1f}% APY)")
        
        # Check if funding rate is attractive
        if funding_rate > self.funding_arb_threshold / 100:
            # Positive funding (longs pay shorts) - good for arbitrage
            return {
                'action': 'ARB',  # Special arbitrage signal
                'symbol': symbol,
                'strategy': 'funding_long_spot_short_perp',
                'funding_rate': funding_rate,
                'expected_apy': annualized_rate * 100,
                'confidence': 0.85,
                'leverage': 1  # No leverage for arb
            }
        
        elif funding_rate < -self.funding_arb_threshold / 100:
            # Negative funding (shorts pay longs)
            return {
                'action': 'ARB',
                'symbol': symbol,
                'strategy': 'funding_short_spot_long_perp',
                'funding_rate': funding_rate,
                'expected_apy': abs(annualized_rate) * 100,
                'confidence': 0.85,
                'leverage': 1
            }
        
        return None
    
    def _basis_trading(self) -> Optional[Dict]:
        """
        Basis Trading (Spot-Futures Spread)
        
        Trade when basis is outside normal range
        """
        symbol = 'BTCUSDT'
        
        # Calculate basis
        basis_pct = self.binance.calculate_basis(symbol)
        
        print(f"[BASIS] Current basis: {basis_pct:.3f}%")
        
        # If basis is too wide (futures overpriced)
        if basis_pct > self.basis_threshold_high:
            # Sell futures, buy spot (basis compression trade)
            return {
                'action': 'SHORT',
                'symbol': symbol,
                'basis': basis_pct,
                'confidence': 0.75,
                'leverage': 3
            }
        
        # If basis is too narrow/negative
        elif basis_pct < self.basis_threshold_low:
            # Buy futures, sell spot (basis expansion trade)
            return {
                'action': 'LONG',
                'symbol': symbol,
                'basis': basis_pct,
                'confidence': 0.70,
                'leverage': 3
            }
        
        return None
    
    def _btc_eth_pairs_trading(self) -> Optional[Dict]:
        """
        BTC/ETH Cointegration Pairs Trading
        
        Trade the spread between BTC and ETH
        """
        # Get current prices
        btc_price = self.binance.get_futures_price('BTCUSDT')
        eth_price = self.binance.get_futures_price('ETHUSDT')
        
        if btc_price == 0 or eth_price == 0:
            return None
        
        # Calculate spread
        spread = btc_price - (self.hedge_ratio * eth_price)
        
        # Update history
        self.btc_eth_history.append(spread)
        if len(self.btc_eth_history) > 100:
            self.btc_eth_history.pop(0)
        
        # Need at least 50 data points
        if len(self.btc_eth_history) < 50:
            return None
        
        # Calculate Z-score
        mean_spread = np.mean(self.btc_eth_history)
        std_spread = np.std(self.btc_eth_history)
        
        if std_spread == 0:
            return None
        
        z_score = (spread - mean_spread) / std_spread
        
        print(f"[PAIRS] BTC/ETH Z-Score: {z_score:.2f}")
        
        # Trade on Z-score
        if z_score > self.pairs_z_threshold:
            # Spread too wide: short BTC, long ETH
            return {
                'action': 'PAIRS_SHORT_BTC_LONG_ETH',
                'btc_symbol': 'BTCUSDT',
                'eth_symbol': 'ETHUSDT',
                'z_score': z_score,
                'confidence': 0.80,
                'leverage': 3
            }
        
        elif z_score < -self.pairs_z_threshold:
            # Spread too narrow: long BTC, short ETH
            return {
                'action': 'PAIRS_LONG_BTC_SHORT_ETH',
                'btc_symbol': 'BTCUSDT',
                'eth_symbol': 'ETHUSDT',
                'z_score': z_score,
                'confidence': 0.80,
                'leverage': 3
            }
        
        return None
    
    def _mean_reversion(self, symbol: str) -> Optional[Dict]:
        """
        Mean Reversion Strategy
        
        Trade when price deviates from 200-period MA
        """
        # Get historical data
        df = self.binance.get_historical_klines(symbol, interval='1h', limit=250)
        
        if df.empty or len(df) < 200:
            return None
        
        # Calculate indicators
        df['MA_200'] = df['close'].rolling(200).mean()
        df['STD_200'] = df['close'].rolling(200).std()
        
        current = df.iloc[-1]
        
        # Calculate Z-score
        z_score = (current['close'] - current['MA_200']) / current['STD_200']
        
        # Check ADX for regime (mean reverting vs trending)
        # Simplified: assume mean reverting if no strong trend
        
        if z_score > 2.5:
            # Price too high, expect mean reversion
            return {
                'action': 'SHORT',
                'symbol': symbol,
                'price': current['close'],
                'z_score': z_score,
                'confidence': 0.70,
                'leverage': 5
            }
        
        elif z_score < -2.5:
            # Price too low
            return {
                'action': 'LONG',
                'symbol': symbol,
                'price': current['close'],
                'z_score': z_score,
                'confidence': 0.70,
                'leverage': 5
            }
        
        return None
    
    def _momentum_breakout(self, symbol: str) -> Optional[Dict]:
        """
        Momentum Breakout Strategy
        
        Trade breakouts with high ATR
        """
        # Get historical data
        df = self.binance.get_historical_klines(symbol, interval='1h', limit=100)
        
        if df.empty or len(df) < 50:
            return None
        
        # Calculate ATR
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift())
        df['low_close'] = abs(df['low'] - df['close'].shift())
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['ATR'] = df['true_range'].rolling(14).mean()
        
        # 20-period high/low
        df['high_20'] = df['high'].rolling(20).max()
        df['low_20'] = df['low'].rolling(20).min()
        
        # Volume
        df['volume_ma'] = df['volume'].rolling(20).mean()
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Calculate ATR percentile
        atr_values = df['ATR'].tail(100).values
        atr_percentile = (current['ATR'] > np.percentile(atr_values, 80))
        
        # Breakout long
        if (current['close'] > current['high_20'] and 
            atr_percentile and
            current['volume'] > current['volume_ma'] * 1.5):
            
            return {
                'action': 'LONG',
                'symbol': symbol,
                'price': current['close'],
                'atr': current['ATR'],
                'confidence': 0.65,
                'leverage': 5
            }
        
        # Breakout short
        elif (current['close'] < current['low_20'] and
              atr_percentile and
              current['volume'] > current['volume_ma'] * 1.5):
            
            return {
                'action': 'SHORT',
                'symbol': symbol,
                'price': current['close'],
                'atr': current['ATR'],
                'confidence': 0.65,
                'leverage': 5
            }
        
        return None
