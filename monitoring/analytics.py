"""
Analytics Dashboard — HTML report generator for trade performance.

Generates a self-contained HTML file with:
- Equity curve chart
- Per-symbol performance heatmap
- Win rate over time
- Trade distribution

Usage:
    python monitoring/analytics.py
    # Opens results/analytics_report.html
"""

import json
import glob
import os
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger("Analytics")


def load_trades() -> pd.DataFrame:
    """Load trade data from JSON logs."""
    json_files = glob.glob("results/paper_trades/*.json")
    
    all_trades = []
    for f in json_files:
        try:
            with open(f, 'r') as fh:
                trades = json.load(fh)
                all_trades.extend(trades)
        except Exception as e:
            logger.warning(f"Could not load {f}: {e}")
    
    if not all_trades:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_trades)
    return df


def generate_html_report(df: pd.DataFrame, output_path: str = "results/analytics_report.html"):
    """Generate self-contained HTML analytics report."""
    
    if df.empty:
        html = "<html><body><h1>No Trades Yet</h1><p>Start the bot and check back later.</p></body></html>"
        with open(output_path, 'w') as f:
            f.write(html)
        return output_path
    
    # Prepare data
    pnl_col = 'pnl' if 'pnl' in df.columns else 'pnl_usd'
    df[pnl_col] = df[pnl_col].astype(float)
    
    total_trades = len(df)
    wins = len(df[df[pnl_col] > 0])
    losses = total_trades - wins
    total_pnl = df[pnl_col].sum()
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    avg_win = df[df[pnl_col] > 0][pnl_col].mean() if wins > 0 else 0
    avg_loss = df[df[pnl_col] <= 0][pnl_col].mean() if losses > 0 else 0
    
    # Equity curve data
    starting_bal = 200.0
    equity = [starting_bal]
    for pnl in df[pnl_col].values:
        equity.append(equity[-1] + pnl)
    equity_json = json.dumps(equity)
    
    # Per-symbol stats
    symbol_stats = []
    sym_col = 'symbol' if 'symbol' in df.columns else df.columns[0]
    for sym in df[sym_col].unique():
        sdf = df[df[sym_col] == sym]
        s_pnl = sdf[pnl_col].sum()
        s_trades = len(sdf)
        s_wins = len(sdf[sdf[pnl_col] > 0])
        s_wr = (s_wins / s_trades * 100) if s_trades > 0 else 0
        symbol_stats.append({
            "symbol": sym, "pnl": round(s_pnl, 2),
            "trades": s_trades, "win_rate": round(s_wr, 1)
        })
    symbol_json = json.dumps(symbol_stats)
    
    # PnL distribution
    pnl_values = df[pnl_col].tolist()
    pnl_json = json.dumps([round(p, 2) for p in pnl_values])
    
    # Exit reasons
    reason_col = 'exit_reason' if 'exit_reason' in df.columns else 'close_reason'
    if reason_col in df.columns:
        reasons = df[reason_col].value_counts().to_dict()
    else:
        reasons = {}
    reasons_json = json.dumps(reasons)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bot_Algo Analytics Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117; color: #c9d1d9; padding: 20px;
  }}
  h1 {{ color: #58a6ff; margin-bottom: 10px; font-size: 28px; }}
  h2 {{ color: #8b949e; font-size: 18px; margin: 20px 0 10px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
  .card {{
    background: #161b22; border: 1px solid #30363d; border-radius: 10px;
    padding: 20px; text-align: center;
  }}
  .card .value {{ font-size: 28px; font-weight: bold; margin: 8px 0; }}
  .card .label {{ font-size: 12px; color: #8b949e; text-transform: uppercase; }}
  .green {{ color: #3fb950; }}
  .red {{ color: #f85149; }}
  .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin: 15px 0; }}
  canvas {{ max-height: 300px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
  th, td {{ padding: 10px 15px; text-align: left; border-bottom: 1px solid #30363d; }}
  th {{ color: #8b949e; font-size: 12px; text-transform: uppercase; }}
  .positive {{ color: #3fb950; }}
  .negative {{ color: #f85149; }}
  .timestamp {{ color: #484f58; font-size: 12px; margin-top: 5px; }}
</style>
</head>
<body>
<h1>Bot_Algo Analytics Dashboard</h1>
<p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="grid">
  <div class="card">
    <div class="label">Total P&L</div>
    <div class="value {'green' if total_pnl >= 0 else 'red'}">${total_pnl:+.2f}</div>
  </div>
  <div class="card">
    <div class="label">Total Trades</div>
    <div class="value">{total_trades}</div>
  </div>
  <div class="card">
    <div class="label">Win Rate</div>
    <div class="value {'green' if win_rate >= 50 else 'red'}">{win_rate:.1f}%</div>
  </div>
  <div class="card">
    <div class="label">Avg Win</div>
    <div class="value green">${avg_win:.2f}</div>
  </div>
  <div class="card">
    <div class="label">Avg Loss</div>
    <div class="value red">${avg_loss:.2f}</div>
  </div>
  <div class="card">
    <div class="label">Current Balance</div>
    <div class="value">${equity[-1]:.2f}</div>
  </div>
</div>

<div class="chart-container">
  <h2>Equity Curve</h2>
  <canvas id="equityChart"></canvas>
</div>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
  <div class="chart-container">
    <h2>P&L Distribution</h2>
    <canvas id="pnlChart"></canvas>
  </div>
  <div class="chart-container">
    <h2>Exit Reasons</h2>
    <canvas id="reasonChart"></canvas>
  </div>
</div>

<div class="chart-container">
  <h2>Per-Symbol Performance</h2>
  <table>
    <tr><th>Symbol</th><th>P&L</th><th>Trades</th><th>Win Rate</th></tr>
    {''.join(f'<tr><td>{s["symbol"]}</td><td class="{"positive" if s["pnl"]>=0 else "negative"}">${s["pnl"]:+.2f}</td><td>{s["trades"]}</td><td>{s["win_rate"]}%</td></tr>' for s in symbol_stats)}
  </table>
</div>

<script>
const equityData = {equity_json};
const pnlData = {pnl_json};
const reasons = {reasons_json};

// Equity Chart
new Chart(document.getElementById('equityChart'), {{
  type: 'line',
  data: {{
    labels: Array.from({{length: equityData.length}}, (_, i) => i),
    datasets: [{{
      label: 'Balance ($)',
      data: equityData,
      borderColor: '#58a6ff',
      backgroundColor: 'rgba(88,166,255,0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 0
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ display: false }},
      y: {{ grid: {{ color: '#21262d' }}, ticks: {{ color: '#8b949e' }} }}
    }}
  }}
}});

// PnL Distribution
const bins = 20;
const min = Math.min(...pnlData);
const max = Math.max(...pnlData);
const step = (max - min) / bins || 1;
const histogram = Array(bins).fill(0);
const labels = [];
for (let i = 0; i < bins; i++) {{
  const lo = min + i * step;
  labels.push(lo.toFixed(1));
  pnlData.forEach(v => {{ if (v >= lo && v < lo + step) histogram[i]++; }});
}}

new Chart(document.getElementById('pnlChart'), {{
  type: 'bar',
  data: {{
    labels: labels,
    datasets: [{{
      data: histogram,
      backgroundColor: histogram.map((_, i) => {{
        const v = min + i * step;
        return v >= 0 ? 'rgba(63,185,80,0.7)' : 'rgba(248,81,73,0.7)';
      }})
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#8b949e', maxRotation: 45 }} }},
      y: {{ grid: {{ color: '#21262d' }}, ticks: {{ color: '#8b949e' }} }}
    }}
  }}
}});

// Exit Reasons
const reasonLabels = Object.keys(reasons);
const reasonValues = Object.values(reasons);
const colors = ['#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7', '#79c0ff'];

new Chart(document.getElementById('reasonChart'), {{
  type: 'doughnut',
  data: {{
    labels: reasonLabels,
    datasets: [{{ data: reasonValues, backgroundColor: colors }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'right', labels: {{ color: '#c9d1d9' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Report generated: {output_path}")
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 50)
    print("  ANALYTICS DASHBOARD GENERATOR")
    print("=" * 50)
    
    df = load_trades()
    
    if df.empty:
        print("No trades found in results/paper_trades/")
        print("Generating empty report...")
    else:
        print(f"Found {len(df)} trades")
    
    path = generate_html_report(df)
    print(f"\nOpen in browser: {os.path.abspath(path)}")
