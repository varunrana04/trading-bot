#!/usr/bin/env python3
"""Diagnose why bot isn't taking positions - UPDATED with relaxed conditions"""
import sys
sys.path.insert(0, '.')

from data_feed import SimulatedDataFeed
from signal_engine import SignalEngine, IndicatorCalculator

symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XAUUSDT', 'XAGUSDT']
feed = SimulatedDataFeed(symbols, ['15m', '1h'])
engine = SignalEngine()

print('Fetching data...')
feed.fetch_latest()
print('Data fetched!\n')

for sym in symbols:
    df_1h = feed.get_dataframe(sym, '1h')
    df_15m = feed.get_dataframe(sym, '15m')
    
    if df_1h is None or df_15m is None:
        print(f'{sym}: NO DATA - symbol may not be available')
        continue
    
    direction = engine.get_1h_direction(df_1h)
    calc = IndicatorCalculator()
    df_1h_calc = calc.add_1h_indicators(df_1h)
    df = calc.add_15m_indicators(df_15m)
    row = df.iloc[-1]
    prev = df.iloc[-2]
    r = df_1h_calc.iloc[-1]
    
    print(f'=== {sym} ===')
    trend = 'BULLISH' if direction == 1 else 'BEARISH' if direction == -1 else 'NEUTRAL'
    
    # Show 1H analysis
    st_dir = 'UP' if r['st_dir'] == 1 else 'DOWN' if r['st_dir'] == -1 else 'FLAT'
    ema_stack_up = r['EMA_8'] > r['EMA_21'] > r['EMA_50']
    ema_stack_down = r['EMA_8'] < r['EMA_21'] < r['EMA_50']
    ema_partial_up = r['EMA_8'] > r['EMA_21']
    ema_partial_down = r['EMA_8'] < r['EMA_21']
    
    print(f'1H Analysis: SuperTrend={st_dir} | EMA Stack Up={ema_stack_up} Down={ema_stack_down}')
    print(f'1H Direction: {trend} (RELAXED: EMA stack OR (ST + partial EMA))')
    
    if direction == 1:
        # RELAXED 15m BUY conditions
        near_ema = -2.0 < row['dist_ema13'] < 1.5  # Relaxed from -1.0 to 0.5
        rsi_ok = 30 < row['RSI'] < 70  # Relaxed from 35-65
        macd_up = row['MACD'] > row['MACD_sig'] or row['MACD'] > prev['MACD']
        candle_up = row['body'] > 0
        vol_ok = row['vol_ratio'] > 0.5  # Relaxed from 0.7
        print(f'  15m BUY Conditions:')
        print(f'    near_ema={near_ema} (dist: {row["dist_ema13"]:.2f}%, need -2.0 to 1.5)')
        print(f'    rsi_ok={rsi_ok} (RSI: {row["RSI"]:.1f}, need 30-70)')
        print(f'    macd_up={macd_up}')
        print(f'    candle_up={candle_up} (body: {row["body"]:.2f})')
        print(f'    vol_ok={vol_ok} (ratio: {row["vol_ratio"]:.2f}, need >0.5)')
        score = sum([near_ema, rsi_ok, macd_up, candle_up, vol_ok])
        print(f'  SCORE: {score}/5 (need >= 2 for entry)')
        if score >= 2:
            print(f'  >>> WOULD ENTER LONG <<<')
    elif direction == -1:
        # RELAXED 15m SELL conditions
        near_ema = -1.5 < row['dist_ema13'] < 2.0  # Relaxed from -0.5 to 1.0
        rsi_ok = 30 < row['RSI'] < 70  # Relaxed from 35-65
        macd_down = row['MACD'] < row['MACD_sig'] or row['MACD'] < prev['MACD']
        candle_down = row['body'] < 0
        vol_ok = row['vol_ratio'] > 0.5  # Relaxed from 0.7
        print(f'  15m SELL Conditions:')
        print(f'    near_ema={near_ema} (dist: {row["dist_ema13"]:.2f}%, need -1.5 to 2.0)')
        print(f'    rsi_ok={rsi_ok} (RSI: {row["RSI"]:.1f}, need 30-70)')
        print(f'    macd_down={macd_down}')
        print(f'    candle_down={candle_down} (body: {row["body"]:.2f})')
        print(f'    vol_ok={vol_ok} (ratio: {row["vol_ratio"]:.2f}, need >0.5)')
        score = sum([near_ema, rsi_ok, macd_down, candle_down, vol_ok])
        print(f'  SCORE: {score}/5 (need >= 2 for entry)')
        if score >= 2:
            print(f'  >>> WOULD ENTER SHORT <<<')
    else:
        print('  NEUTRAL - no clear trend (conflicting signals)')
        print(f'    For BULLISH: need EMA stack OR (ST UP + EMA8>EMA21)')
        print(f'    For BEARISH: need EMA stack OR (ST DOWN + EMA8<EMA21)')
    print()
