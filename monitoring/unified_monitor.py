"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              UNIFIED MONITOR - Advanced Performance Dashboard               ║
║  Track Both Crypto and Indian Markets with Professional Metrics             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Run this anytime to see current trading status:
    python monitoring/unified_monitor.py
"""
import glob
import pandas as pd
import numpy as np
from datetime import datetime
import os
import json


# ═══════════════════════════════════════════════════════════════════════════════
#                         PERFORMANCE METRICS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_sharpe_ratio(returns, risk_free_rate=0.0, annualize=True):
    """
    Calculate Sharpe Ratio from a list of trade returns.
    
    Args:
        returns: List of percentage returns per trade
        risk_free_rate: Daily risk-free rate (default 0)
        annualize: Whether to annualize (assumes ~365 trades/year)
    """
    if len(returns) < 2:
        return 0.0
    
    arr = np.array(returns)
    excess = arr - risk_free_rate
    
    if np.std(excess) == 0:
        return 0.0
    
    sharpe = np.mean(excess) / np.std(excess)
    
    if annualize:
        sharpe *= np.sqrt(252)  # Annualize
    
    return round(sharpe, 2)


def calculate_sortino_ratio(returns, risk_free_rate=0.0):
    """
    Calculate Sortino Ratio (penalizes only downside volatility).
    """
    if len(returns) < 2:
        return 0.0
    
    arr = np.array(returns)
    excess = arr - risk_free_rate
    downside = arr[arr < 0]
    
    if len(downside) == 0 or np.std(downside) == 0:
        return float('inf') if np.mean(excess) > 0 else 0.0
    
    sortino = np.mean(excess) / np.std(downside)
    return round(sortino * np.sqrt(252), 2)


def calculate_max_drawdown(equity_curve):
    """
    Calculate maximum drawdown from an equity curve.
    
    Args:
        equity_curve: List of cumulative balance values
    
    Returns:
        (max_drawdown_pct, peak_value, trough_value)
    """
    if len(equity_curve) < 2:
        return 0.0, 0.0, 0.0
    
    arr = np.array(equity_curve)
    peak = np.maximum.accumulate(arr)
    drawdown = (arr - peak) / peak * 100
    
    max_dd = np.min(drawdown)
    max_dd_idx = np.argmin(drawdown)
    peak_idx = np.argmax(arr[:max_dd_idx + 1]) if max_dd_idx > 0 else 0
    
    return round(max_dd, 2), arr[peak_idx], arr[max_dd_idx]


def calculate_expectancy(wins, losses, avg_win, avg_loss):
    """
    Calculate expected value per trade.
    """
    total = wins + losses
    if total == 0:
        return 0.0
    
    win_rate = wins / total
    loss_rate = losses / total
    
    expectancy = (win_rate * avg_win) - (loss_rate * abs(avg_loss))
    return round(expectancy, 2)


def calculate_profit_factor(total_wins, total_losses):
    """Calculate ratio of gross wins to gross losses."""
    if total_losses == 0:
        return float('inf') if total_wins > 0 else 0.0
    return round(total_wins / abs(total_losses), 2)


def format_streak(trades_pnl):
    """Calculate current and max win/loss streaks."""
    if not trades_pnl:
        return 0, 0, 0, 0
    
    current_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    current_type = None
    
    for pnl in trades_pnl:
        if pnl > 0:
            if current_type == 'win':
                current_streak += 1
            else:
                current_streak = 1
                current_type = 'win'
            max_win_streak = max(max_win_streak, current_streak)
        else:
            if current_type == 'loss':
                current_streak += 1
            else:
                current_streak = 1
                current_type = 'loss'
            max_loss_streak = max(max_loss_streak, current_streak)
    
    # Current streak (positive for wins, negative for losses)
    current = current_streak if current_type == 'win' else -current_streak
    
    return current, max_win_streak, max_loss_streak


# ═══════════════════════════════════════════════════════════════════════════════
#                           MONITOR FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def monitor_crypto():
    """Monitor crypto (BTC/ETH/SOL/XAU/XAG) paper trading"""
    print("\n" + "=" * 70)
    print("[CRYPTO] Multi-Asset Paper Trading")
    print("=" * 70)
    
    # Find latest crypto log
    logs = glob.glob("trade_log_*.csv") + glob.glob("results/paper_trades/*.json")
    if not logs:
        print("[*] Bot is running, waiting for signals...")
        print("    No trades executed yet")
        return
    
    # Try CSV logs first
    csv_logs = glob.glob("trade_log_*.csv")
    json_logs = glob.glob("results/paper_trades/*.json")
    
    df = None
    
    if csv_logs:
        latest_log = max(csv_logs, key=os.path.getmtime)
        print(f"[FILE] Log: {latest_log}")
        try:
            df = pd.read_csv(latest_log)
        except Exception as e:
            print(f"[!] Error reading CSV log: {e}")
    
    if df is None and json_logs:
        latest_log = max(json_logs, key=os.path.getmtime)
        print(f"[FILE] Log: {latest_log}")
        try:
            with open(latest_log, 'r') as f:
                trades_data = json.load(f)
            df = pd.DataFrame(trades_data)
        except Exception as e:
            print(f"[!] Error reading JSON log: {e}")
    
    if df is None or len(df) == 0:
        print("[*] Bot is running, no closed trades yet")
        return
    
    # Normalize column names
    pnl_col = 'pnl_usd' if 'pnl_usd' in df.columns else 'pnl'
    
    # Calculate basic stats
    df[pnl_col] = df[pnl_col].astype(float)
    total_pnl = df[pnl_col].sum()
    wins = len(df[df[pnl_col] > 0])
    losses = len(df) - wins
    win_rate = (wins / len(df) * 100) if len(df) > 0 else 0
    
    # ── Capital Summary ──
    starting_capital = 200.0
    current_capital = starting_capital + total_pnl
    
    print(f"\n{'─' * 40}")
    print(f"  💰 CAPITAL")
    print(f"{'─' * 40}")
    print(f"   Starting:    ${starting_capital:.2f}")
    print(f"   Current:     ${current_capital:.2f}")
    print(f"   P/L:         ${total_pnl:+.2f}")
    print(f"   ROI:         {(total_pnl/starting_capital*100):+.2f}%")
    
    # ── Per Symbol Breakdown ──
    print(f"\n{'─' * 40}")
    print(f"  📊 PER SYMBOL")
    print(f"{'─' * 40}")
    
    symbol_col = 'symbol' if 'symbol' in df.columns else df.columns[0]
    for symbol in df[symbol_col].unique():
        sym_df = df[df[symbol_col] == symbol]
        sym_pnl = sym_df[pnl_col].sum()
        sym_trades = len(sym_df)
        sym_wins = len(sym_df[sym_df[pnl_col] > 0])
        sym_wr = (sym_wins / sym_trades * 100) if sym_trades > 0 else 0
        print(f"   {symbol:8} ${sym_pnl:+7.2f} | {sym_trades} trades | WR: {sym_wr:.0f}%")
    
    # ── Advanced Performance Metrics ──
    returns = df[pnl_col].tolist()
    pnl_pct_returns = [r / starting_capital * 100 for r in returns]
    
    # Build equity curve
    equity = [starting_capital]
    for pnl in returns:
        equity.append(equity[-1] + pnl)
    
    sharpe = calculate_sharpe_ratio(pnl_pct_returns)
    sortino = calculate_sortino_ratio(pnl_pct_returns)
    max_dd, peak, trough = calculate_max_drawdown(equity)
    
    avg_win = df[df[pnl_col] > 0][pnl_col].mean() if wins > 0 else 0
    avg_loss = df[df[pnl_col] <= 0][pnl_col].mean() if losses > 0 else 0
    total_win_amt = df[df[pnl_col] > 0][pnl_col].sum() if wins > 0 else 0
    total_loss_amt = abs(df[df[pnl_col] <= 0][pnl_col].sum()) if losses > 0 else 0
    
    expectancy = calculate_expectancy(wins, losses, avg_win, abs(avg_loss))
    profit_factor = calculate_profit_factor(total_win_amt, total_loss_amt)
    current_streak, max_win_streak, max_loss_streak = format_streak(returns)
    
    print(f"\n{'─' * 40}")
    print(f"  📈 PERFORMANCE METRICS")
    print(f"{'─' * 40}")
    print(f"   Total Trades: {len(df)}")
    print(f"   Wins:         {wins} ({win_rate:.1f}%)")
    print(f"   Losses:       {losses}")
    print(f"   Avg Win:      ${avg_win:.2f}")
    print(f"   Avg Loss:     ${avg_loss:.2f}")
    
    print(f"\n{'─' * 40}")
    print(f"  🎯 RISK METRICS")
    print(f"{'─' * 40}")
    print(f"   Sharpe Ratio:   {sharpe}")
    sortino_str = f"{sortino}" if sortino != float('inf') else "∞ (no losses)"
    print(f"   Sortino Ratio:  {sortino_str}")
    print(f"   Max Drawdown:   {max_dd:.2f}%")
    print(f"   Profit Factor:  {profit_factor}")
    print(f"   Expectancy:     ${expectancy:.2f}/trade")
    
    print(f"\n{'─' * 40}")
    print(f"  🔥 STREAKS")
    print(f"{'─' * 40}")
    streak_emoji = "🟢" if current_streak > 0 else "🔴" if current_streak < 0 else "⚪"
    print(f"   Current:        {streak_emoji} {abs(current_streak)} {'wins' if current_streak > 0 else 'losses'}")
    print(f"   Best Win Run:   {max_win_streak}")
    print(f"   Worst Loss Run: {max_loss_streak}")
    
    # ── Holding Time ──
    if 'entry_time' in df.columns and 'exit_time' in df.columns:
        try:
            df['entry_dt'] = pd.to_datetime(df['entry_time'])
            df['exit_dt'] = pd.to_datetime(df['exit_time'])
            df['hold_mins'] = (df['exit_dt'] - df['entry_dt']).dt.total_seconds() / 60
            avg_hold = df['hold_mins'].mean()
            
            print(f"\n{'─' * 40}")
            print(f"  ⏱️  TIMING")
            print(f"{'─' * 40}")
            
            if avg_hold > 60:
                print(f"   Avg Hold Time:  {avg_hold/60:.1f} hours")
            else:
                print(f"   Avg Hold Time:  {avg_hold:.0f} minutes")
            
            win_hold = df[df[pnl_col] > 0]['hold_mins'].mean() if wins > 0 else 0
            loss_hold = df[df[pnl_col] <= 0]['hold_mins'].mean() if losses > 0 else 0
            print(f"   Avg Win Hold:   {win_hold:.0f} min")
            print(f"   Avg Loss Hold:  {loss_hold:.0f} min")
        except Exception:
            pass
    
    # ── Recent Trades ──
    time_col = 'timestamp' if 'timestamp' in df.columns else ('exit_time' if 'exit_time' in df.columns else None)
    
    print(f"\n{'─' * 40}")
    print(f"  📋 LAST 5 TRADES")
    print(f"{'─' * 40}")
    
    recent = df.tail(5)
    for _, trade in recent.iterrows():
        pnl = float(trade[pnl_col])
        emoji = "🟢" if pnl > 0 else "🔴"
        sym = trade.get('symbol', '???')
        side = trade.get('side', trade.get('direction', '?'))
        lev = trade.get('leverage', '?')
        reason = trade.get('close_reason', trade.get('exit_reason', '?'))
        ts = str(trade.get(time_col, trade.get('entry_time', '')))[:16] if time_col else ''
        print(f"   {emoji} {ts} | {sym:8} {side:5} {lev}x | ${pnl:+7.2f} | {reason}")
    
    # ── Circuit Breakers ──
    print(f"\n{'─' * 40}")
    print(f"  🚨 CIRCUIT BREAKERS")
    print(f"{'─' * 40}")
    
    last_3 = df.tail(3)[pnl_col].tolist()
    consecutive_losses = 0
    for pnl in reversed(last_3):
        if pnl < 0:
            consecutive_losses += 1
        else:
            break
    
    print(f"   Consecutive losses:  {consecutive_losses}/3")
    daily_loss = df.tail(10)[pnl_col].sum()
    print(f"   Recent 10-trade PnL: ${daily_loss:+.2f}")
    
    if consecutive_losses >= 3:
        print(f"   ⚠️  WARNING: Consider pausing trading!")
    elif max_dd < -10:
        print(f"   ⚠️  WARNING: Max drawdown exceeds 10%!")
    else:
        print(f"   ✅ All systems nominal")


def monitor_indian():
    """Monitor Indian markets (Nifty/BankNifty) - when active"""
    print(f"\n{'═' * 70}")
    print("[INDIAN] Nifty/BankNifty Markets")
    print("=" * 70)
    
    state_file = "options_trade_state.json"
    
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            print("[*] Status: RUNNING")
            
            if 'NIFTY' in state or 'BANKNIFTY' in state or 'SENSEX' in state:
                total_pnl = 0
                total_trades = 0
                
                for symbol in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    if symbol in state:
                        pnl = state[symbol].get('pnl', 0)
                        trades = len(state[symbol].get('trades', []))
                        positions = len(state[symbol].get('positions', []))
                        
                        total_pnl += pnl
                        total_trades += trades
                        
                        if positions > 0 or trades > 0:
                            print(f"   {symbol:10} P/L: Rs.{pnl:,.2f} | Positions: {positions} | Trades: {trades}")
                
                print(f"\n   Total P/L: Rs.{total_pnl:,.2f}")
                print(f"   Total Trades: {total_trades}")
        except Exception as e:
            print(f"[*] Status: RUNNING (state file exists, error: {e})")
    else:
        print("[*] Status: NOT RUNNING")
        print("    Start: python trade_indian_options.py")


def main():
    print("\n" + "═" * 70)
    print("  📊 UNIFIED TRADING MONITOR")
    print("═" * 70)
    print(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    monitor_crypto()
    monitor_indian()
    
    print(f"\n{'═' * 70}")
    print("  💡 TIPS:")
    print("   • Crypto bot checks every 30 seconds")
    print("   • Run this anytime: python monitoring/unified_monitor.py")
    print("   • Sharpe > 1.0 = good, > 2.0 = excellent")
    print("   • Profit Factor > 1.5 = solid edge")
    print("═" * 70 + "\n")

if __name__ == "__main__":
    main()
