"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       ML CONFIDENCE SCORING                                   ║
║                                                                               ║
║  Machine learning based confidence scoring for trade signals.                 ║
║  Uses historical signal outcomes to predict current signal quality.           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Features:
- Train on historical signal outcomes
- Feature engineering from price/indicator data
- Confidence score 0-1 for each signal
- Position sizing based on confidence

Author: Bot_Algo
Last Updated: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger("MLConfidence")


# ═══════════════════════════════════════════════════════════════════════════════
#                           FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════════

class FeatureEngineer:
    """
    Create features from price data for ML model.
    """
    
    def __init__(self):
        self.feature_names = []
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create all features from OHLCV data."""
        df = df.copy()
        
        close_col = 'close' if 'close' in df.columns else 'Close'
        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'
        volume_col = 'volume' if 'volume' in df.columns else 'Volume'
        
        close = df[close_col]
        high = df[high_col]
        low = df[low_col]
        
        # === Price-based features ===
        
        # Returns at different timeframes
        df['ret_1'] = close.pct_change(1)
        df['ret_3'] = close.pct_change(3)
        df['ret_5'] = close.pct_change(5)
        df['ret_10'] = close.pct_change(10)
        
        # Volatility at different timeframes
        df['vol_5'] = close.pct_change().rolling(5).std()
        df['vol_10'] = close.pct_change().rolling(10).std()
        df['vol_20'] = close.pct_change().rolling(20).std()
        df['vol_ratio'] = df['vol_5'] / (df['vol_20'] + 0.0001)
        
        # === Momentum features ===
        
        # RSI
        for period in [5, 7, 14]:
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).ewm(span=period).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(span=period).mean()
            rs = gain / (loss + 0.0001)
            df[f'rsi_{period}'] = 100 - (100 / (1 + rs))
        
        # RSI difference (momentum of RSI)
        df['rsi_diff'] = df['rsi_7'].diff()
        
        # === Trend features ===
        
        # EMA distances
        for period in [8, 21, 50]:
            df[f'ema_{period}'] = close.ewm(span=period).mean()
            df[f'ema_dist_{period}'] = (close - df[f'ema_{period}']) / df[f'ema_{period}'] * 100
        
        # EMA slope
        df['ema_slope_8'] = df['ema_8'].diff(3) / df['ema_8'] * 100
        df['ema_slope_21'] = df['ema_21'].diff(3) / df['ema_21'] * 100
        
        # EMA alignment (1=bullish, -1=bearish, 0=mixed)
        df['ema_align'] = np.where(
            (df['ema_8'] > df['ema_21']) & (df['ema_21'] > df['ema_50']), 1,
            np.where((df['ema_8'] < df['ema_21']) & (df['ema_21'] < df['ema_50']), -1, 0)
        )
        
        # === Range features ===
        
        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = tr.ewm(span=14).mean()
        df['atr_pct'] = df['atr'] / close * 100
        
        # Range position
        df['high_20'] = high.rolling(20).max()
        df['low_20'] = low.rolling(20).min()
        df['range_pos'] = (close - df['low_20']) / (df['high_20'] - df['low_20'] + 0.0001)
        
        # === Volume features ===
        if volume_col in df.columns:
            vol = df[volume_col]
            df['vol_ratio_20'] = vol / vol.rolling(20).mean()
            df['vol_trend'] = vol.rolling(5).mean() / vol.rolling(20).mean()
        
        # === ADX (trend strength) ===
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        smoothed_tr = tr.rolling(14).sum()
        df['plus_di'] = 100 * (plus_dm.rolling(14).sum() / (smoothed_tr + 0.0001))
        df['minus_di'] = 100 * (minus_dm.rolling(14).sum() / (smoothed_tr + 0.0001))
        dx = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'] + 0.0001)
        df['adx'] = dx.rolling(14).mean()
        
        # DI difference
        df['di_diff'] = df['plus_di'] - df['minus_di']
        
        # Store feature names
        self.feature_names = [
            'ret_1', 'ret_3', 'ret_5', 'ret_10',
            'vol_5', 'vol_10', 'vol_20', 'vol_ratio',
            'rsi_5', 'rsi_7', 'rsi_14', 'rsi_diff',
            'ema_dist_8', 'ema_dist_21', 'ema_dist_50',
            'ema_slope_8', 'ema_slope_21', 'ema_align',
            'atr_pct', 'range_pos',
            'adx', 'di_diff'
        ]
        
        return df
    
    def get_feature_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """Get feature matrix from dataframe."""
        df = self.create_features(df)
        
        # Filter to only feature columns
        features = df[self.feature_names].copy()
        
        # Fill NaN with 0
        features = features.fillna(0)
        
        return features.values


# ═══════════════════════════════════════════════════════════════════════════════
#                           CONFIDENCE SCORER
# ═══════════════════════════════════════════════════════════════════════════════

class ConfidenceScorer:
    """
    ML-based confidence scoring for trade signals.
    
    Trains on historical signal outcomes to predict:
    - Will this signal result in a profitable trade?
    - Confidence level (0-1)
    """
    
    def __init__(self, lookforward: int = 5):
        self.lookforward = lookforward
        self.feature_eng = FeatureEngineer()
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def train(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        min_samples: int = 100
    ) -> Dict:
        """
        Train model on historical data.
        
        Args:
            df: OHLCV data
            signals: Trading signals (-1, 0, 1)
            min_samples: Minimum samples required
            
        Returns:
            Training metrics
        """
        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col]
        
        # Create features
        df_features = self.feature_eng.create_features(df)
        
        # Create target: was the signal profitable in next N bars?
        future_return = close.pct_change(self.lookforward).shift(-self.lookforward)
        
        # Label: 1 if signal direction matches return direction
        df_features['signal'] = signals
        df_features['future_ret'] = future_return
        df_features['target'] = np.where(
            signals * future_return > 0, 1,  # Correct direction
            np.where(signals == 0, 0.5, 0)   # Neutral or wrong
        )
        
        # Filter to only rows with signals
        mask = signals.abs() > 0
        df_filtered = df_features[mask].dropna()
        
        if len(df_filtered) < min_samples:
            logger.warning(f"Not enough samples: {len(df_filtered)} < {min_samples}")
            return {'success': False, 'samples': len(df_filtered)}
        
        # Get features and target
        X = df_filtered[self.feature_eng.feature_names].values
        y = (df_filtered['target'] > 0.5).astype(int).values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            min_samples_split=10,
            random_state=42
        )
        
        # Cross-validation score
        cv_scores = cross_val_score(self.model, X_scaled, y, cv=5)
        
        # Fit on all data
        self.model.fit(X_scaled, y)
        self.is_trained = True
        
        # Feature importance
        importances = dict(zip(
            self.feature_eng.feature_names,
            self.model.feature_importances_
        ))
        top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'success': True,
            'samples': len(df_filtered),
            'cv_accuracy': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'top_features': top_features
        }
    
    def predict_confidence(self, df: pd.DataFrame) -> pd.Series:
        """
        Predict confidence score for each bar.
        
        Returns:
            Series of confidence scores (0-1)
        """
        if not self.is_trained:
            return pd.Series(0.5, index=df.index)
        
        # Get features
        X = self.feature_eng.get_feature_matrix(df)
        X_scaled = self.scaler.transform(X)
        
        # Predict probabilities
        proba = self.model.predict_proba(X_scaled)[:, 1]
        
        return pd.Series(proba, index=df.index)
    
    def get_position_multiplier(self, confidence: float) -> float:
        """
        Get position size multiplier based on confidence.
        
        confidence < 0.4 → 0.5x position
        confidence 0.4-0.6 → 1.0x position  
        confidence > 0.6 → 1.5x position
        """
        if confidence < 0.4:
            return 0.5
        elif confidence < 0.6:
            return 1.0
        else:
            return 1.0 + (confidence - 0.6) * 1.25  # Up to 1.5x


# ═══════════════════════════════════════════════════════════════════════════════
#                           MAIN (Demo)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from stress_test import STRESS_PERIODS, fetch_period_data
    from strategies.hybrid_original import generate_original_signals
    from core.terminal_alerts import Color
    
    print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
    print(f"{Color.CYAN}ML CONFIDENCE SCORING - DEMO{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}\n")
    
    # Use only first 4 periods for training to be faster
    train_periods = STRESS_PERIODS[:4]
    test_periods = STRESS_PERIODS[4:]
    
    all_data = []
    all_signals = []
    
    print("Loading training data...")
    for period in train_periods:
        print(f"  {period.name}")
        df = fetch_period_data('BTCUSDT', period.start_date, period.end_date)
        if len(df) < 30:
            continue
        
        signals = generate_original_signals(df)
        all_data.append(df)
        all_signals.append(signals)
    
    # Concatenate
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_signals = pd.concat(all_signals, ignore_index=True)
    
    signal_count = int(combined_signals.abs().sum())
    print(f"\nTraining data: {len(combined_df)} bars, {signal_count} signals")
    
    # Train model
    print("\nTraining ML model...")
    scorer = ConfidenceScorer(lookforward=5)
    result = scorer.train(combined_df, combined_signals, min_samples=50)
    
    if result['success']:
        print(f"\n{Color.GREEN}Training successful!{Color.RESET}")
        print(f"  Samples: {result['samples']}")
        print(f"  CV Accuracy: {result['cv_accuracy']:.1%} ± {result['cv_std']:.1%}")
        print(f"\nTop Features:")
        for feat, imp in result['top_features']:
            print(f"  {feat}: {imp:.3f}")
        
        # Test on remaining periods
        print(f"\n{Color.BOLD}Testing on out-of-sample periods:{Color.RESET}")
        print("-" * 50)
        
        for period in test_periods:
            df = fetch_period_data('BTCUSDT', period.start_date, period.end_date)
            if len(df) < 30:
                continue
            
            confidence = scorer.predict_confidence(df)
            avg_conf = confidence.mean()
            
            print(f"{period.name}: Avg Confidence = {avg_conf:.2f}")
    else:
        print(f"{Color.RED}Training failed - not enough samples{Color.RESET}")
    
    print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
