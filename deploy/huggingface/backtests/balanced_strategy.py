#!/usr/bin/env python3
"""
================================================================================
          BALANCED STRATEGY - 1HR DIRECTION + 15M ENTRY
================================================================================
Combines 1hr trend direction with 15m entry timing for:
- Higher trade frequency (5+ per day)
- Acceptable win rate (45%+)
- Positive returns

Logic:
1. 1hr determines trend direction (Supertrend + EMA)
2. 15m waits for pullback entry
3. Fast exits on 15m (shorter holds)
================================================================================
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict
from dataclasses import dataclass
import pandas as pd
import numpy as np
import logging
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from binance.client import Client
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    Client = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Balanced")


class BalancedSignals:
    """1hr trend + 15m entry"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
    
    def prepare_1h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare 1hr indicators"""
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
        atr = tr.rolling(10).mean().fillna(method='bfill')
        
        upper = hl2 + (2.5 * atr)
        lower = hl2 - (2.5 * atr)
        
        n = len(df)
        st = np.zeros(n)
        direction = np.zeros(n)
        st[0] = df['close'].iloc[0]
        
        for i in range(1, n):
            if upper.iloc[i] < st[i-1] or df['close'].iloc[i-1] > st[i-1]:
                st[i] = upper.iloc[i]
            else:
                st[i] = st[i-1]
            
            if df['close'].iloc[i] > st[i]:
                if direction[i-1] != 1:
                    st[i] = lower.iloc[i]
                direction[i] = 1
            else:
                if direction[i-1] != -1:
                    st[i] = upper.iloc[i]
                direction[i] = -1
        
        df['st_dir'] = direction
        
        return df
    
    def prepare_15m(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare 15m indicators"""
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
        
        # Candle
        df['body'] = df['close'] - df['open']
        
        # Distance from EMA
        df['dist_ema13'] = (df['close'] - df['EMA_13']) / df['EMA_13'] * 100
        
        return df
    
    def get_1h_direction(self, df_1h: pd.DataFrame, timestamp_15m) -> int:
        """Get 1hr trend direction at given 15m timestamp"""
        # Find the 1hr candle that contains this 15m time
        mask = df_1h['timestamp'] <= timestamp_15m
        if mask.sum() == 0:
            return 0
        
        idx = mask.sum() - 1
        row = df_1h.iloc[idx]
        
        # Check trend
        st_up = row['st_dir'] == 1
        ema_up = row['EMA_8'] > row['EMA_21'] > row['EMA_50']
        st_down = row['st_dir'] == -1
        ema_down = row['EMA_8'] < row['EMA_21'] < row['EMA_50']
        
        if st_up and ema_up:
            return 1  # Bullish
        elif st_down and ema_down:
            return -1  # Bearish
        else:
            return 0  # No clear trend
    
    def get_15m_entry(self, df_15m: pd.DataFrame, i: int, direction: int) -> Dict:
        """Check for 15m entry opportunity in trend direction"""
        if i < 20:
            return {"signal": "HOLD"}
        
        row = df_15m.iloc[i]
        prev = df_15m.iloc[i-1]
        
        # RELAXED Entry conditions for BUY (direction == 1)
        if direction == 1:
            # Pullback to EMA13 - RELAXED from -1.0 to 0.5
            near_ema = -2.0 < row['dist_ema13'] < 1.5
            
            # RSI - RELAXED from 35-65 to 30-70
            rsi_ok = 30 < row['RSI'] < 70
            
            # MACD turning up
            macd_up = row['MACD'] > row['MACD_sig'] or row['MACD'] > prev['MACD']
            
            # Bullish candle
            candle_up = row['body'] > 0
            
            # Volume OK - RELAXED from 0.7 to 0.5
            vol_ok = row['vol_ratio'] > 0.5
            
            conditions = [near_ema, rsi_ok, macd_up, candle_up, vol_ok]
            score = sum(conditions)
            
            # RELAXED from 3 to 2
            if score >= 2:
                return {
                    "signal": "BUY",
                    "score": score,
                    "conviction": score / 5.0
                }
        
        # RELAXED Entry conditions for SELL (direction == -1)
        elif direction == -1:
            # Rally to EMA13 - RELAXED from -0.5 to 1.0
            near_ema = -1.5 < row['dist_ema13'] < 2.0
            
            # RSI - RELAXED from 35-65 to 30-70
            rsi_ok = 30 < row['RSI'] < 70
            
            # MACD turning down
            macd_down = row['MACD'] < row['MACD_sig'] or row['MACD'] < prev['MACD']
            
            # Bearish candle
            candle_down = row['body'] < 0
            
            # Volume OK - RELAXED from 0.7 to 0.5
            vol_ok = row['vol_ratio'] > 0.5
            
            conditions = [near_ema, rsi_ok, macd_down, candle_down, vol_ok]
            score = sum(conditions)
            
            # RELAXED from 3 to 2
            if score >= 2:
                return {
                    "signal": "SELL",
                    "score": score,
                    "conviction": score / 5.0
                }
        
        return {"signal": "HOLD"}


@dataclass
class Trade:
    entry_time: str
    exit_time: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    leverage: int
    margin: float
    pnl: float
    pnl_pct: float
    exit_reason: str


class BalancedBacktester:
    """Backtester using 1hr direction + 15m entry"""
    
    def __init__(self):
        self.client = None
        if BINANCE_AVAILABLE:
            try:
                self.client = Client("", "", {"timeout": 30})
                logger.info("Connected")
            except:
                pass
        
        self.starting_balance = 1000.0
        self.risk = 0.035
        self.max_lev = 30
        self.min_lev = 10
        self.max_hold = 32  # 8 hours at 15m
        
        # Balanced exits
        self.tp_pct = 0.015  # 1.5%
        self.sl_pct = 0.008  # 0.8%
        self.trail_pct = 0.007
    
    def fetch(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        if not self.client:
            return self._dummy(symbol, interval, days)
        
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            
            delta_map = {
                "15m": timedelta(minutes=15),
                "1h": timedelta(hours=1)
            }
            delta = delta_map.get(interval, timedelta(hours=1))
            
            klines = []
            curr = start
            while curr < end:
                data = self.client.futures_klines(
                    symbol=symbol, interval=interval,
                    startTime=int(curr.timestamp()*1000),
                    endTime=int(end.timestamp()*1000),
                    limit=1000
                )
                if not data: break
                klines.extend(data)
                curr = datetime.fromtimestamp(data[-1][0]/1000) + delta
                if len(data) < 1000: break
            
            if not klines:
                return self._dummy(symbol, interval, days)
            
            df = pd.DataFrame(klines, columns=[
                'timestamp','open','high','low','close','volume',
                'close_time','quote_volume','trades','taker_buy_base',
                'taker_buy_quote','ignore'
            ])
            df = df.drop_duplicates(subset=['timestamp'])
            for c in ['open','high','low','close','volume']:
                df[c] = df[c].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            return df
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return self._dummy(symbol, interval, days)
    
    def _dummy(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        base = {"BTCUSDT": 42000, "ETHUSDT": 2200, "SOLUSDT": 100, "XAUUSDT": 2700, "XAGUSDT": 31}.get(symbol, 100)
        cpd = {"15m": 96, "1h": 24}.get(interval, 24)
        freq = {"15m": "15min", "1h": "1H"}.get(interval, "1H")
        n = int(cpd * days)
        
        np.random.seed(42)
        prices = [base]
        for _ in range(n-1):
            prices.append(max(prices[-1] + np.random.randn() * base * 0.002, base * 0.5))
        
        dates = pd.date_range(end=datetime.now(), periods=n, freq=freq)
        return pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p*(1+abs(np.random.randn())*0.004) for p in prices],
            'low': [p*(1-abs(np.random.randn())*0.004) for p in prices],
            'close': [p*(1+np.random.randn()*0.002) for p in prices],
            'volume': [np.random.randint(100,1000) for _ in prices]
        })
    
    def run(self, symbol: str, days: int = 30) -> Dict:
        logger.info(f"Running balanced backtest: {symbol} ({days} days)")
        
        sig_gen = BalancedSignals(symbol)
        
        # Fetch both timeframes
        df_1h = self.fetch(symbol, "1h", days)
        df_15m = self.fetch(symbol, "15m", days)
        
        logger.info(f"Data: 1h={len(df_1h)}, 15m={len(df_15m)}")
        
        # Prepare data
        df_1h = sig_gen.prepare_1h(df_1h)
        df_15m = sig_gen.prepare_15m(df_15m)
        
        df_15m = df_15m.iloc[50:].reset_index(drop=True)
        df_15m = df_15m.fillna(method='ffill').fillna(0)
        
        balance = self.starting_balance
        position = None
        trades = []
        last_exit_idx = -3
        
        for i in range(1, len(df_15m)):
            row = df_15m.iloc[i]
            
            # Exit logic
            if position:
                price = row['close']
                entry = position['entry']
                dir_ = position['dir']
                
                pnl_pct = (price - entry) / entry if dir_ == "BUY" else (entry - price) / entry
                position['max_pnl'] = max(position.get('max_pnl', 0), pnl_pct)
                
                exit_reason = None
                if pnl_pct >= self.tp_pct:
                    exit_reason = "TP"
                elif pnl_pct <= -self.sl_pct:
                    exit_reason = "SL"
                elif position['max_pnl'] > self.trail_pct and pnl_pct < position['max_pnl'] - self.trail_pct:
                    exit_reason = "TRAIL"
                elif position['hold'] >= self.max_hold:
                    exit_reason = "TIMEOUT"
                
                if exit_reason:
                    lev_pnl = pnl_pct * position['lev']
                    gross = position['margin'] * lev_pnl
                    cost = position['margin'] * position['lev'] * 0.0008
                    net = gross - cost
                    
                    balance += net
                    trades.append(Trade(
                        entry_time=position['time'],
                        exit_time=str(row['timestamp']),
                        symbol=symbol,
                        direction=dir_,
                        entry_price=entry,
                        exit_price=price,
                        leverage=position['lev'],
                        margin=position['margin'],
                        pnl=net,
                        pnl_pct=pnl_pct*100,
                        exit_reason=exit_reason
                    ))
                    position = None
                    last_exit_idx = i
                else:
                    position['hold'] += 1
            
            # Entry logic
            if position is None and i > last_exit_idx + 2:
                # Get 1hr trend direction
                direction = sig_gen.get_1h_direction(df_1h, row['timestamp'])
                
                if direction != 0:
                    # Check 15m entry
                    sig = sig_gen.get_15m_entry(df_15m, i, direction)
                    
                    if sig['signal'] != "HOLD":
                        conv = sig.get('conviction', 0.5)
                        margin = balance * self.risk * (0.5 + conv * 0.5)
                        margin = np.clip(margin, 10, min(100, balance * 0.12))
                        
                        lev = int(self.min_lev + conv * (self.max_lev - self.min_lev))
                        lev = np.clip(lev, self.min_lev, self.max_lev)
                        
                        position = {
                            'entry': row['close'],
                            'dir': sig['signal'],
                            'lev': lev,
                            'margin': margin,
                            'time': str(row['timestamp']),
                            'hold': 0
                        }
        
        # Close remaining
        if position:
            last = df_15m.iloc[-1]
            pnl_pct = (last['close'] - position['entry']) / position['entry']
            if position['dir'] == "SELL":
                pnl_pct = -pnl_pct
            net = position['margin'] * pnl_pct * position['lev']
            balance += net
            trades.append(Trade(
                entry_time=position['time'],
                exit_time=str(last['timestamp']),
                symbol=symbol,
                direction=position['dir'],
                entry_price=position['entry'],
                exit_price=last['close'],
                leverage=position['lev'],
                margin=position['margin'],
                pnl=net,
                pnl_pct=pnl_pct*100,
                exit_reason="END"
            ))
        
        return self._metrics(symbol, days, trades, balance)
    
    def _metrics(self, symbol, days, trades, balance) -> Dict:
        n = len(trades)
        if n == 0:
            return {"symbol": symbol, "error": "No trades", "total_trades": 0}
        
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl <= 0]
        
        win_rate = len(winners) / n * 100
        total_win = sum(t.pnl for t in winners)
        total_loss = abs(sum(t.pnl for t in losers))
        pf = total_win / total_loss if total_loss > 0 else float('inf')
        
        running = self.starting_balance
        peak = running
        max_dd = 0
        for t in trades:
            running += t.pnl
            peak = max(peak, running)
            dd = (peak - running) / peak * 100
            max_dd = max(max_dd, dd)
        
        ret = (balance - self.starting_balance) / self.starting_balance * 100
        
        if n > 1:
            pnls = [t.pnl for t in trades]
            sharpe = (np.mean(pnls) / (np.std(pnls) + 1e-10)) * np.sqrt(n / days * 252)
        else:
            sharpe = 0
        
        exits = {}
        for t in trades:
            exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
        
        return {
            "symbol": symbol,
            "days": days,
            "starting": self.starting_balance,
            "final": round(balance, 2),
            "return_pct": round(ret, 2),
            "total_trades": n,
            "trades_per_day": round(n / days, 2),
            "win_rate": round(win_rate, 2),
            "pf": round(pf, 2) if pf != float('inf') else "inf",
            "sharpe": round(sharpe, 2),
            "max_dd": round(max_dd, 2),
            "avg_win": round(sum(t.pnl for t in winners) / len(winners), 2) if winners else 0,
            "avg_loss": round(sum(t.pnl for t in losers) / len(losers), 2) if losers else 0,
            "exits": exits
        }


def run_balanced(days: int = 30):
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSDT", "XAGUSDT"]
    
    print("=" * 100)
    print("  BALANCED STRATEGY - 1HR DIRECTION + 15M ENTRY")
    print("  Target: 5+ trades/day with 45%+ win rate")
    print("=" * 100)
    
    results = {}
    bt = BalancedBacktester()
    total_trades = 0
    
    for sym in symbols:
        print(f"\n{'-' * 80}")
        print(f"  {sym}")
        print(f"{'-' * 80}")
        
        r = bt.run(sym, days)
        results[sym] = r
        
        if r.get("total_trades", 0) == 0:
            print(f"  ERROR: {r.get('error', 'No trades')}")
            continue
        
        total_trades += r['total_trades']
        
        print(f"  Trades:        {r['total_trades']} ({r['trades_per_day']}/day)")
        print(f"  Win Rate:      {r['win_rate']}%")
        print(f"  Profit Factor: {r['pf']}")
        print(f"  Sharpe:        {r['sharpe']}")
        print(f"  Return:        {r['return_pct']}%")
        print(f"  Max Drawdown:  {r['max_dd']}%")
        print(f"  Avg Win/Loss:  ${r['avg_win']} / ${r['avg_loss']}")
        print(f"  Final Balance: ${r['final']}")
        print(f"  Exits:         {r['exits']}")
    
    total_per_day = total_trades / days
    
    print("\n" + "=" * 100)
    print("  BALANCED SUMMARY")
    print("=" * 100)
    print(f"\n  {'Symbol':<12} {'Trades':<8} {'TPD':<8} {'Win%':<8} {'PF':<8} {'Return%':<10} {'MaxDD%'}")
    print("  " + "-" * 70)
    
    for sym, r in results.items():
        if r.get("total_trades", 0) > 0:
            print(f"  {sym:<12} {r['total_trades']:<8} {r['trades_per_day']:<8} {r['win_rate']:<8} "
                  f"{str(r['pf']):<8} {r['return_pct']:<10} {r['max_dd']}")
    
    print(f"\n  TOTAL TRADES/DAY: {total_per_day:.2f} (Target: 5+)")
    
    if total_per_day >= 5:
        print("  [OK] TARGET MET!")
    else:
        print(f"  [!!] Need {5 - total_per_day:.2f} more trades/day")
    
    os.makedirs("results", exist_ok=True)
    out = f"results/balanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n  Saved: {out}")
    print("=" * 100)
    
    return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30)
    args = p.parse_args()
    run_balanced(args.days)
