# strategies/ensemble.py
"""
Universal Ensemble Strategy Framework
Combines all indicators, advanced strategies, and pattern recognition
Works across all markets: Crypto (BTC, ETH), Indian Options (Nifty, BankNifty, Sensex)
All timeframes: 5m, 15m, 30m, 1h, 1d
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List


class UniversalEnsembleStrategy:
    """
    Configurable ensemble that combines multiple signal sources
    with optimizable weights and enable/disable flags
    """
    
    def __init__(self, config: Dict = None):
        """
       Initialize ensemble with configuration
        
        Config parameters:
        - Component enable flags (use_indicators, use_kalman, etc.)
        - Component weights (indicator_weight, kalman_weight, etc.)
        - Confidence thresholds (min_indicator_confidence, etc.)
        """
        self.config = config or self.get_default_config()
        self.component_scores = {}  # Track individual component contributions
        
    @staticmethod
    def get_default_config() -> Dict:
        """Default configuration - all components enabled with equal weights"""
        return {
            # Component enable/disable flags
            'use_indicators': True,        # Traditional indicators (RSI, MACD, EMA, ADX)
            'use_kalman': True,           # Kalman filter predictions
            'use_vpin': True,             # VPIN market microstructure
            'use_patterns': True,         # Candlestick + chart patterns
            'use_hurst': True,            # Hurst exponent (trend strength)
            'use_garch': False,           # GARCH volatility (optional, slower)
            
            # Component weights (how much each contributes to final score)
            'indicator_weight': 1.0,      # Traditional indicators
            'kalman_weight': 1.5,        # Kalman predictions (often powerful)
            'pattern_weight': 2.0,       # Pattern confirmation (high value)
            'hurst_weight': 1.0,         # Trend persistence
            'vpin_weight': 0.5,          # Market safety (more of a filter)
            'garch_weight': 0.5,         # Volatility forecast
            
            # Minimum confidence thresholds per component
            'min_indicator_confidence': 0.5,
            'min_pattern_confidence': 0.7,
            'min_kalman_confidence': 0.3,
            
            # Final decision thresholds
            'buy_threshold': 2.0,         # Min score for BUY signal
            'sell_threshold': -2.0,       # Min score for SELL signal
        }
    
    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Tuple[str, float, Dict]:
        """
        Generate trading signal using ensemble of strategies
        
        Returns:
            signal: 'BUY', 'SELL', or 'HOLD'
            confidence: 0.0-1.0
            details: Dict with component scores
        """
        total_score = 0
        max_possible_score = 0
        self.component_scores = {}
        
        # 1. TRADITIONAL INDICATORS
        if self.config['use_indicators']:
            score, conf = self._calculate_indicator_score(df)
            if conf >= self.config['min_indicator_confidence']:
                weighted_score = score * self.config['indicator_weight']
                total_score += weighted_score
                max_possible_score += self.config['indicator_weight']
                self.component_scores['indicators'] = {'score': score, 'confidence': conf, 'weighted': weighted_score}
        
        # 2. KALMAN FILTER
        if self.config['use_kalman']:
            score, conf = self._calculate_kalman_score(df, symbol)
            if conf >= self.config['min_kalman_confidence']:
                weighted_score = score * self.config['kalman_weight']
                total_score += weighted_score
                max_possible_score += self.config['kalman_weight']
                self.component_scores['kalman'] = {'score': score, 'confidence': conf, 'weighted': weighted_score}
        
        # 3. PATTERN RECOGNITION
        if self.config['use_patterns']:
            score, conf = self._calculate_pattern_score(df)
            if conf >= self.config['min_pattern_confidence']:
                weighted_score = score * self.config['pattern_weight']
                total_score += weighted_score
                max_possible_score += self.config['pattern_weight']
                self.component_scores['patterns'] = {'score': score, 'confidence': conf, 'weighted': weighted_score}
        
        # 4. HURST EXPONENT
        if self.config['use_hurst']:
            score = self._calculate_hurst_score(df)
            weighted_score = score * self.config['hurst_weight']
            total_score += weighted_score
            max_possible_score += self.config['hurst_weight']
            self.component_scores['hurst'] = {'score': score, 'weighted': weighted_score}
        
        # 5. VPIN SAFETY CHECK
        if self.config['use_vpin']:
            can_trade, vpin_score = self._calculate_vpin_safety(df)
            if not can_trade:
                # VPIN says market is toxic, return HOLD
                return 'HOLD', 0.5, {'reason': 'VPIN toxic market', 'components': self.component_scores}
            # Add VPIN contribution if market is safe
            weighted_score = vpin_score * self.config['vpin_weight']
            total_score += weighted_score
            max_possible_score += self.config['vpin_weight']
            self.component_scores['vpin'] = {'score': vpin_score, 'weighted': weighted_score}
        
        # 6. GARCH VOLATILITY (OPTIONAL)
        if self.config.get('use_garch', False):
            score = self._calculate_garch_score(df)
            weighted_score = score * self.config['garch_weight']
            total_score += weighted_score
            max_possible_score += self.config['garch_weight']
            self.component_scores['garch'] = {'score': score, 'weighted': weighted_score}
        
        # FINAL DECISION
        # Normalize confidence
        confidence = abs(total_score) / max_possible_score if max_possible_score > 0 else 0.5
        confidence = min(max(confidence, 0.0), 1.0)  # Clamp to [0, 1]
        
        # Decision logic
        if total_score >= self.config['buy_threshold']:
            signal = 'BUY'
        elif total_score <= self.config['sell_threshold']:
            signal = 'SELL'
        else:
            signal = 'HOLD'
            confidence = 0.5
        
        details = {
            'total_score': total_score,
            'max_score': max_possible_score,
            'components': self.component_scores
        }
        
        return signal, confidence, details
    
    def _calculate_indicator_score(self, df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate score from traditional indicators (RSI, MACD, EMA, ADX)"""
        if len(df) < 100:
            return 0.0, 0.0
        
        latest = df.iloc[-1]
        score = 0
        
        # EMA trend
        if 'EMA_50' in df.columns and 'EMA_100' in df.columns and 'EMA_200' in df.columns:
            if latest['EMA_50'] > latest['EMA_100'] > latest['EMA_200']:
                score += 1  # Bullish trend
            elif latest['EMA_50'] < latest['EMA_100'] < latest['EMA_200']:
                score -= 1  # Bearish trend
        
        # MACD
        if 'MACD' in df.columns and 'MACD_signal' in df.columns:
            if latest['MACD'] > latest['MACD_signal'] and latest.get('MACD_hist', 0) > 0:
                score += 1  # Bullish momentum
            elif latest['MACD'] < latest['MACD_signal'] and latest.get('MACD_hist', 0) < 0:
                score -= 1  # Bearish momentum
        
        # RSI
        if 'RSI' in df.columns:
            rsi = latest['RSI']
            if 45 < rsi < 75:
                score += 0.5  # Bullish zone
            elif 25 < rsi < 55:
                score -= 0.5  # Bearish zone
        
        # Normalize to -1 to +1 range
        max_score = 2.5
        normalized_score = score / max_score
        confidence = abs(score) / max_score
        
        return normalized_score, confidence
    
    def _calculate_kalman_score(self, df: pd.DataFrame, symbol: str) -> Tuple[float, float]:
        """Calculate score from Kalman filter predictions"""
        try:
            from strategies.advanced import AdaptiveKalmanFilter
            
            if len(df) < 10:
                return 0.0, 0.0
            
            # Use recent prices for Kalman
            prices = df['close'].tail(50).values
            kf = AdaptiveKalmanFilter()
            
            # Update filter with prices
            for price in prices[:-1]:
                kf.update(price)
            
            # Predict next price
            current_price = prices[-1]
            predicted_price, uncertainty = kf.predict(steps=1)
            
            # Calculate expected change
            change_pct = ((predicted_price - current_price) / current_price) * 100
            
            # Score based on prediction
            if change_pct > 0.1:
                score = min(change_pct / 1.0, 1.0)  # Bullish, cap at 1.0
                confidence = 1.0 - min(uncertainty / current_price, 1.0)
            elif change_pct < -0.1:
                score = max(change_pct / 1.0, -1.0)  # Bearish, cap at -1.0
                confidence = 1.0 - min(uncertainty / current_price, 1.0)
            else:
                score = 0.0
                confidence = 0.5
            
            return score, confidence
        except Exception:
            return 0.0, 0.0
    
    def _calculate_pattern_score(self, df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate score from pattern recognition"""
        try:
            from indicators.pattern_recognition import detect_all_patterns, aggregate_pattern_signals
            
            if len(df) < 20:
                return 0.0, 0.0
            
            # Detect patterns
            patterns = detect_all_patterns(df, lookback=100)
            signal_data = aggregate_pattern_signals(patterns, min_confidence=0.7)
            
            # Return normalized score
            score = signal_data['signal']  # -1, 0, or +1
            confidence = signal_data['confidence']
            
            return float(score), confidence
        except Exception:
            return 0.0, 0.0
    
    def _calculate_hurst_score(self, df: pd.DataFrame) -> float:
        """Calculate score from Hurst exponent (trend strength)"""
        try:
            from strategies.advanced import UncorrelatedFeatures
            
            if len(df) < 50:
                return 0.0
            
            prices = df['close'].tail(50).values
            hurst = UncorrelatedFeatures.get_hurst_exponent(prices)
            
            # Hurst > 0.5: trending, Hurst < 0.5: mean-reverting
            # Use current trend direction
            recent_return = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10]
            
            if hurst > 0.6:  # Strong trend
                if recent_return > 0:
                    return 1.0  # Uptrend continuation
                else:
                    return -1.0  # Downtrend continuation
            elif hurst < 0.4:  # Mean reverting
                if recent_return > 0.05:
                    return -0.5  # Overbought, expect reversion
                elif recent_return < -0.05:
                    return 0.5  # Oversold, expect bounce
            
            return 0.0
        except Exception:
            return 0.0
    
    def _calculate_vpin_safety(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """Check if market is safe to trade (VPIN)"""
        try:
            from strategies.advanced import VPIN
            
            if len(df) < 30:
                return True, 0.0
            
            vpin = VPIN()
            latest = df.iloc[-1]
            
            # Update VPIN
            vpin_value = vpin.update(latest['close'], latest['volume'])
            can_trade, reason = vpin.should_trade()
            
            # Return safety flag and small score contribution
            score = -0.5 if not can_trade else 0.1
            return can_trade, score
        except Exception:
            return True, 0.0
    
    def _calculate_garch_score(self, df: pd.DataFrame) -> float:
        """Calculate score from GARCH volatility forecast (optional, slower)"""
        # Placeholder - would implement GARCH volatility forecasting
        # For now, return neutral
        return 0.0
