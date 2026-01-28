#!/usr/bin/env python3
"""
================================================================================
                    SIGNAL ENGINE - REAL-TIME SIGNALS
================================================================================
Generates trading signals in real-time using balanced strategy.
1hr for direction, 15m for entry timing.
================================================================================
"""

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SignalEngine")


class IndicatorCalculator:
    """Calculate indicators on DataFrame"""
    
    @staticmethod
    def add_1h_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add 1hr trend indicators"""
        df = df.copy()
        
        # EMAs
        df['EMA_8'] = df['close'].ewm(span=8, adjust=False).mean()
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # Supertrend
        hl2 = (df['high'] + df['low']) / 2
        tr = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        ], axis=1).max(axis=1)
        atr = tr.rolling(10).mean().bfill()
        
        upper = hl2 + (2.5 * atr)
        lower = hl2 - (2.5 * atr)
        
        n = len(df)
        st = np.zeros(n)
        direction = np.zeros(n)
        st[0] = df['close'].iloc[0] if n > 0 else 0
        
        for i in range(1, n):
            ub = upper.iloc[i] if not pd.isna(upper.iloc[i]) else st[i-1]
            lb = lower.iloc[i] if not pd.isna(lower.iloc[i]) else st[i-1]
            
            if ub < st[i-1] or df['close'].iloc[i-1] > st[i-1]:
                st[i] = ub
            else:
                st[i] = st[i-1]
            
            if df['close'].iloc[i] > st[i]:
                if direction[i-1] != 1:
                    st[i] = lb
                direction[i] = 1
            else:
                if direction[i-1] != -1:
                    st[i] = ub
                direction[i] = -1
        
        df['st_dir'] = direction
        
        return df
    
    @staticmethod
    def add_15m_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add 15m entry indicators"""
        df = df.copy()
        
        # Fast EMAs
        df['EMA_5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['EMA_13'] = df['close'].ewm(span=13, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=10, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=10, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        
        # MACD
        exp8 = df['close'].ewm(span=8, adjust=False).mean()
        exp17 = df['close'].ewm(span=17, adjust=False).mean()
        df['MACD'] = exp8 - exp17
        df['MACD_sig'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # ATR
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        tr1 = pd.Series(high - low)
        tr2 = pd.Series(np.abs(high - np.roll(close, 1)))
        tr3 = pd.Series(np.abs(low - np.roll(close, 1)))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(10).mean()
        df['ATR_pct'] = df['ATR'] / df['close'] * 100
        
        # Volume
        df['vol_MA'] = df['volume'].rolling(12).mean()
        df['vol_ratio'] = df['volume'] / (df['vol_MA'] + 1e-10)
        
        # Candle body
        df['body'] = df['close'] - df['open']
        
        # Distance from EMA
        df['dist_ema13'] = (df['close'] - df['EMA_13']) / df['EMA_13'] * 100
        
        return df


class SignalEngine:
    """Real-time signal generation engine"""
    
    def __init__(self):
        self.calc = IndicatorCalculator()
        self.callbacks: List[Callable] = []
        self.last_signals: Dict[str, Dict] = {}  # symbol -> last signal
        
        # Track last signal time to avoid duplicates
        self.last_signal_time: Dict[str, datetime] = {}
    
    def add_callback(self, callback: Callable):
        """Add callback for signal events"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, signal: Dict):
        """Notify all callbacks of new signal"""
        for cb in self.callbacks:
            try:
                cb(signal)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_1h_direction(self, df_1h: pd.DataFrame) -> int:
        """Get trend direction from 1hr data - RELAXED VERSION
        
        Uses SuperTrend OR EMA stack (instead of requiring both).
        Also considers partial EMA alignment.
        """
        if df_1h is None or len(df_1h) < 50:
            return 0
        
        df = self.calc.add_1h_indicators(df_1h)
        row = df.iloc[-1]
        
        st_up = row['st_dir'] == 1
        st_down = row['st_dir'] == -1
        
        # Full EMA stack
        ema_up = row['EMA_8'] > row['EMA_21'] > row['EMA_50']
        ema_down = row['EMA_8'] < row['EMA_21'] < row['EMA_50']
        
        # Partial EMA alignment (just fast > slow)
        ema_partial_up = row['EMA_8'] > row['EMA_21']
        ema_partial_down = row['EMA_8'] < row['EMA_21']
        
        # RELAXED: SuperTrend OR full EMA stack OR (SuperTrend + partial EMA)
        bullish = ema_up or (st_up and ema_partial_up)
        bearish = ema_down or (st_down and ema_partial_down)
        
        if bullish and not bearish:
            return 1  # Bullish
        elif bearish and not bullish:
            return -1  # Bearish
        else:
            return 0  # Neutral (conflicting or no signal)
    
    def check_15m_entry(self, df_15m: pd.DataFrame, direction: int, symbol: str = "") -> Dict:
        """Check for entry opportunity on 15m"""
        if df_15m is None or len(df_15m) < 30:
            return {"signal": "HOLD", "reason": "Insufficient data"}
        
        df = self.calc.add_15m_indicators(df_15m)
        df = df.ffill().fillna(0)
        
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else row
        
        # RELAXED Entry conditions (widened EMA distance, lowered score threshold)
        if direction == 1:  # Looking for BUY
            near_ema = -2.0 < row['dist_ema13'] < 1.5  # Relaxed from -1.0 to 0.5
            rsi_ok = 30 < row['RSI'] < 70  # Relaxed from 35-65
            macd_up = row['MACD'] > row['MACD_sig'] or row['MACD'] > prev['MACD']
            candle_up = row['body'] > 0
            vol_ok = row['vol_ratio'] > 0.5  # Relaxed from 0.7
            
            conditions = [near_ema, rsi_ok, macd_up, candle_up, vol_ok]
            score = sum(conditions)
            
            # Log condition status for debugging
            logger.info(f"📊 {symbol} BUY CHECK: near_ema={near_ema}({row['dist_ema13']:.2f}%) rsi={rsi_ok}({row['RSI']:.1f}) macd={macd_up} candle={candle_up} vol={vol_ok}({row['vol_ratio']:.2f}) => {score}/5")
            
            if score >= 2:  # Relaxed from 3
                return {
                    "signal": "BUY",
                    "score": score,
                    "conviction": score / 5.0,
                    "price": row['close'],
                    "atr_pct": row['ATR_pct'],
                    "conditions": {
                        "near_ema": near_ema,
                        "rsi_ok": rsi_ok,
                        "macd_up": macd_up,
                        "candle_up": candle_up,
                        "vol_ok": vol_ok
                    }
                }
        
        elif direction == -1:  # Looking for SELL
            near_ema = -1.5 < row['dist_ema13'] < 2.0  # Relaxed from -0.5 to 1.0
            rsi_ok = 30 < row['RSI'] < 70  # Relaxed from 35-65
            macd_down = row['MACD'] < row['MACD_sig'] or row['MACD'] < prev['MACD']
            candle_down = row['body'] < 0
            vol_ok = row['vol_ratio'] > 0.5  # Relaxed from 0.7
            
            conditions = [near_ema, rsi_ok, macd_down, candle_down, vol_ok]
            score = sum(conditions)
            
            # Log condition status for debugging
            logger.info(f"📊 {symbol} SELL CHECK: near_ema={near_ema}({row['dist_ema13']:.2f}%) rsi={rsi_ok}({row['RSI']:.1f}) macd={macd_down} candle={candle_down} vol={vol_ok}({row['vol_ratio']:.2f}) => {score}/5")
            
            if score >= 2:  # Relaxed from 3
                return {
                    "signal": "SELL",
                    "score": score,
                    "conviction": score / 5.0,
                    "price": row['close'],
                    "atr_pct": row['ATR_pct'],
                    "conditions": {
                        "near_ema": near_ema,
                        "rsi_ok": rsi_ok,
                        "macd_down": macd_down,
                        "candle_down": candle_down,
                        "vol_ok": vol_ok
                    }
                }
        
        return {"signal": "HOLD", "reason": f"Score {score}/5 < 2 required"}
    
    def process(self, symbol: str, df_1h: pd.DataFrame, df_15m: pd.DataFrame) -> Dict:
        """Process data and generate signal"""
        
        # Get 1hr trend direction
        direction = self.get_1h_direction(df_1h)
        
        if direction == 0:
            # Log why trend is neutral for debugging
            if df_1h is not None and len(df_1h) >= 50:
                df = self.calc.add_1h_indicators(df_1h)
                row = df.iloc[-1]
                st_dir = 'UP' if row['st_dir'] == 1 else 'DOWN' if row['st_dir'] == -1 else 'FLAT'
                ema_up = row['EMA_8'] > row['EMA_21'] > row['EMA_50']
                ema_down = row['EMA_8'] < row['EMA_21'] < row['EMA_50']
                logger.info(f"⏸️ {symbol} NEUTRAL: ST={st_dir} EMA_stack_up={ema_up} EMA_stack_down={ema_down}")
            
            signal = {
                "symbol": symbol,
                "signal": "HOLD",
                "direction": "NEUTRAL",
                "reason": "No clear trend (ST and EMA not aligned)",
                "timestamp": datetime.now().isoformat()
            }
        else:
            trend_str = "BULLISH" if direction == 1 else "BEARISH"
            logger.info(f"📈 {symbol} 1H TREND: {trend_str} - checking 15m entry...")
            
            # Check 15m entry
            entry = self.check_15m_entry(df_15m, direction, symbol)
            
            signal = {
                "symbol": symbol,
                "signal": entry.get("signal", "HOLD"),
                "direction": trend_str,
                "score": entry.get("score", 0),
                "conviction": entry.get("conviction", 0),
                "price": entry.get("price", 0),
                "atr_pct": entry.get("atr_pct", 0),
                "reason": entry.get("reason", ""),
                "timestamp": datetime.now().isoformat()
            }
        
        # Store and notify if signal changed
        last = self.last_signals.get(symbol, {})
        if signal['signal'] != last.get('signal', 'HOLD') and signal['signal'] != 'HOLD':
            self._notify_callbacks(signal)
            logger.info(f"🚀 SIGNAL: {symbol} {signal['signal']} @ {signal.get('price', 0):.2f} (score: {signal.get('score', 0)}/5)")
        
        self.last_signals[symbol] = signal
        return signal
    
    def get_last_signal(self, symbol: str) -> Optional[Dict]:
        """Get the last signal for a symbol"""
        return self.last_signals.get(symbol)


if __name__ == "__main__":
    # Test signal engine
    from data_feed import SimulatedDataFeed
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    # Create data feed and fetch data
    feed = SimulatedDataFeed(symbols, ["15m", "1h"])
    feed.fetch_latest()
    
    # Create signal engine
    engine = SignalEngine()
    
    def on_signal(signal):
        print(f"NEW SIGNAL: {signal}")
    
    engine.add_callback(on_signal)
    
    # Process each symbol
    for sym in symbols:
        df_1h = feed.get_dataframe(sym, "1h")
        df_15m = feed.get_dataframe(sym, "15m")
        
        signal = engine.process(sym, df_1h, df_15m)
        print(f"{sym}: {signal['signal']} - {signal.get('reason', signal.get('direction', ''))}")
