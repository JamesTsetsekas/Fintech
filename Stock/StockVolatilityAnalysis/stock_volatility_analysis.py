#!/usr/bin/env python3
"""
Stock Volatility Analysis Tool

Analyzes volatility metrics including rolling volatility, beta (relative to S&P 500),
and volatility comparison across multiple stocks.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import argparse
import os
import sys
import logging
import time

# Add parent directory to path to import stock_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stock_utils import get_stocks_from_source, get_assets_from_file

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description='Stock Volatility Analysis Tool',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python stock_volatility_analysis.py                    # Use default asset list
  python stock_volatility_analysis.py --source file      # Read from assets.txt
  python stock_volatility_analysis.py --source sp500 --top 10    # Top 10 S&P 500
  python stock_volatility_analysis.py --source sector --sector Technology --top 5
  python stock_volatility_analysis.py --period 2y        # 2 year period
  python stock_volatility_analysis.py --window 30         # 30-day rolling window
    """
)
parser.add_argument(
    '--source', 
    choices=['default', 'file', 'sp500', 'nasdaq', 'dow', 'sector'],
    default='default',
    help='Data source: default, file, sp500, nasdaq, dow, or sector'
)
parser.add_argument(
    '--file',
    default='assets.txt',
    help='Path to file with tickers (one per line). Used when --source=file'
)
parser.add_argument(
    '--sector',
    help='Sector name (required when --source=sector). Options: Technology, Healthcare, Financials, etc.'
)
parser.add_argument(
    '--top',
    type=int,
    help='Return only top N stocks (by market cap, return, or volatility)'
)
parser.add_argument(
    '--metric',
    choices=['market_cap', 'return', 'volatility'],
    default='market_cap',
    help='Metric for top N selection (default: market_cap)'
)
parser.add_argument(
    '--period',
    default='1y',
    help='Time period for analysis (e.g., 1y, 2y, 5y)'
)
parser.add_argument(
    '--window',
    type=int,
    default=30,
    help='Rolling window for volatility calculation (default: 30 days)'
)
args = parser.parse_args()

DATA_SOURCE = args.source
ASSETS_FILE = args.file
SECTOR = args.sector
TOP_N = args.top
METRIC = args.metric
PERIOD = args.period
WINDOW = args.window

# Default assets list
default_assets = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "TSLA",
    "JPM",
    "JNJ",
    "SPY",  # S&P 500 ETF for beta calculation
]

# Determine which assets to use
if DATA_SOURCE == 'file':
    assets = get_assets_from_file(ASSETS_FILE)
    print(f"Loaded {len(assets)} tickers from {ASSETS_FILE}")
elif DATA_SOURCE in ['sp500', 'nasdaq', 'dow', 'sector']:
    assets = get_stocks_from_source(DATA_SOURCE, TOP_N, SECTOR, PERIOD, METRIC)
    source_desc = DATA_SOURCE.upper()
    if SECTOR:
        source_desc += f" ({SECTOR})"
    if TOP_N:
        source_desc += f" - Top {TOP_N} by {METRIC}"
    print(f"Using {len(assets)} tickers from {source_desc}")
else:
    assets = default_assets
    print(f"Using default list with {len(assets)} tickers")

# Remove duplicates
assets = list(dict.fromkeys(assets))

# Ensure SPY is included for beta calculation
if 'SPY' not in assets and '^GSPC' not in assets:
    assets.append('SPY')

print(f"\nTotal unique assets to analyze: {len(assets)}")
print(f"Assets: {', '.join(assets)}\n")

# Calculate start date based on period
if PERIOD.endswith('y'):
    years = int(PERIOD[:-1])
    start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
elif PERIOD.endswith('m'):
    months = int(PERIOD[:-1])
    start_date = (datetime.now() - timedelta(days=months*30)).strftime('%Y-%m-%d')
else:
    start_date = PERIOD

end_date = datetime.now().strftime('%Y-%m-%d')

print(f"Analyzing period: {start_date} to {end_date}")
print(f"Rolling window: {WINDOW} days\n")

# Download stock data
print("Downloading stock data...")
data_dict = {}
for ticker in assets:
    try:
        print(f"Downloading {ticker}...", end=" ", flush=True)
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(start=start_date, end=end_date)
        
        if not hist.empty and len(hist) > 0:
            if "Adj Close" in hist.columns:
                data_dict[ticker] = hist["Adj Close"]
            elif "Close" in hist.columns:
                data_dict[ticker] = hist["Close"]
            print("[OK]")
        else:
            print(f"[FAILED] (No data)")
        time.sleep(0.5)
    except Exception as e:
        error_msg = str(e)[:60] if len(str(e)) > 60 else str(e)
        print(f"[FAILED] (Error: {error_msg})")
        time.sleep(0.5)

if not data_dict:
    raise ValueError("Failed to download any stock data.")

# Create DataFrame
data = pd.DataFrame(data_dict)

# Calculate returns
returns = data.pct_change().dropna()

# Get benchmark (SPY or ^GSPC)
benchmark_ticker = None
for ticker in ['SPY', '^GSPC']:
    if ticker in returns.columns:
        benchmark_ticker = ticker
        break

if benchmark_ticker is None:
    print("Warning: No benchmark found (SPY or ^GSPC). Beta calculations will be skipped.")
    benchmark_returns = None
    assets_to_plot = assets
else:
    benchmark_returns = returns[benchmark_ticker]
    # Remove benchmark from assets list for plotting
    assets_to_plot = [a for a in assets if a != benchmark_ticker]

# Calculate volatility metrics
print("\n" + "="*60)
print("Volatility Analysis Summary")
print("="*60)

volatility_summary = []

for ticker in assets_to_plot:
    if ticker not in returns.columns:
        continue
    
    ticker_returns = returns[ticker]
    
    # Annualized volatility (using daily returns)
    annual_vol = ticker_returns.std() * np.sqrt(252) * 100
    
    # Rolling volatility
    rolling_vol = ticker_returns.rolling(window=WINDOW).std() * np.sqrt(252) * 100
    
    # Calculate beta if benchmark is available
    if benchmark_returns is not None:
        # Align data
        aligned_returns = pd.DataFrame({
            'stock': ticker_returns,
            'benchmark': benchmark_returns
        }).dropna()
        
        if len(aligned_returns) > 0:
            covariance = aligned_returns['stock'].cov(aligned_returns['benchmark'])
            benchmark_variance = aligned_returns['benchmark'].var()
            beta = covariance / benchmark_variance if benchmark_variance > 0 else np.nan
        else:
            beta = np.nan
    else:
        beta = np.nan
    
    # Max drawdown
    cumulative = (1 + ticker_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    
    volatility_summary.append({
        'Ticker': ticker,
        'Annual Volatility %': f"{annual_vol:.2f}",
        'Beta': f"{beta:.2f}" if not np.isnan(beta) else "N/A",
        'Max Drawdown %': f"{max_drawdown:.2f}"
    })

summary_df = pd.DataFrame(volatility_summary)
summary_df = summary_df.sort_values('Annual Volatility %', 
                                     key=lambda x: x.str.replace('%', '').astype(float), 
                                     ascending=False)
print("\n" + summary_df.to_string(index=False))

# Create visualization. Scale layout for larger ticker sets used by the runner.
plot_tickers = [ticker for ticker in assets_to_plot if ticker in returns.columns]
plot_count = len(plot_tickers)
fig_height = min(18, max(12, 10 + plot_count * 0.18))
fig = plt.figure(figsize=(16, fig_height))
gs = fig.add_gridspec(3, 2, hspace=0.45, wspace=0.3, top=0.84)

# Plot 1: Rolling Volatility
ax1 = fig.add_subplot(gs[0, :])
for ticker in assets_to_plot:
    if ticker not in returns.columns:
        continue
    ticker_returns = returns[ticker]
    rolling_vol = ticker_returns.rolling(window=WINDOW).std() * np.sqrt(252) * 100
    ax1.plot(rolling_vol.index, rolling_vol.values, label=ticker, linewidth=2)

ax1.set_title(f'Rolling Volatility ({WINDOW}-Day Window, Annualized)', 
              fontsize=14, fontweight='bold')
ax1.set_xlabel('Date', fontsize=11)
ax1.set_ylabel('Volatility (%)', fontsize=11)
legend_cols = min(5, max(2, (plot_count + 4) // 5))
legend_font_size = 8 if plot_count <= 15 else 6
handles, labels = ax1.get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.935),
           ncol=legend_cols, fontsize=legend_font_size, framealpha=0.9)
ax1.grid(True, alpha=0.3)

# Plot 2: Annual Volatility Comparison
ax2 = fig.add_subplot(gs[1, 0])
vol_data = []
tickers_list = []
for ticker in assets_to_plot:
    if ticker not in returns.columns:
        continue
    annual_vol = returns[ticker].std() * np.sqrt(252) * 100
    vol_data.append(annual_vol)
    tickers_list.append(ticker)

bars = ax2.barh(tickers_list, vol_data, 
                color=plt.cm.viridis(np.linspace(0.2, 0.8, len(vol_data))))
ax2.set_title('Annual Volatility Comparison', fontsize=12, fontweight='bold')
ax2.set_xlabel('Volatility (%)', fontsize=10)
ax2.grid(True, alpha=0.3, axis='x')
if vol_data:
    vol_span = max(max(vol_data) - min(vol_data), 1)
    ax2.set_xlim(0, max(vol_data) + vol_span * 0.18)
ax2.tick_params(axis='y', labelsize=8 if len(tickers_list) <= 15 else 6)

for i, (ticker, vol) in enumerate(zip(tickers_list, vol_data)):
    label_offset = max((max(vol_data) - min(vol_data)) * 0.015, 0.4) if vol_data else 0.5
    ax2.text(vol + label_offset, i, f'{vol:.1f}%',
             va='center', ha='left', fontsize=8 if len(tickers_list) <= 15 else 6)

# Plot 3: Beta Comparison (if available)
ax3 = fig.add_subplot(gs[1, 1])
if benchmark_returns is not None:
    beta_data = []
    beta_tickers = []
    for ticker in assets_to_plot:
        if ticker not in returns.columns:
            continue
        aligned_returns = pd.DataFrame({
            'stock': returns[ticker],
            'benchmark': benchmark_returns
        }).dropna()
        
        if len(aligned_returns) > 0:
            covariance = aligned_returns['stock'].cov(aligned_returns['benchmark'])
            benchmark_variance = aligned_returns['benchmark'].var()
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
            beta_data.append(beta)
            beta_tickers.append(ticker)
    
    if beta_data:
        colors = ['red' if b < 0.8 else 'orange' if b < 1.2 else 'green' for b in beta_data]
        bars = ax3.barh(beta_tickers, beta_data, color=colors)
        ax3.axvline(x=1.0, color='black', linestyle='--', linewidth=1, label='Market (Beta=1)')
        ax3.set_title(f'Beta vs {benchmark_ticker}', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Beta', fontsize=10)
        ax3.legend(fontsize=9)
        ax3.grid(True, alpha=0.3, axis='x')
        beta_min = min(beta_data)
        beta_max = max(beta_data)
        beta_span = max(beta_max - beta_min, 0.5)
        ax3.set_xlim(min(0, beta_min) - beta_span * 0.08,
                     max(1.0, beta_max) + beta_span * 0.18)
        ax3.tick_params(axis='y', labelsize=8 if len(beta_tickers) <= 15 else 6)

        for i, (ticker, beta) in enumerate(zip(beta_tickers, beta_data)):
            ax3.text(beta + max(beta_span * 0.015, 0.02), i, f'{beta:.2f}',
                     va='center', ha='left', fontsize=8 if len(beta_tickers) <= 15 else 6)
else:
    ax3.text(0.5, 0.5, 'Beta calculation requires\nSPY or ^GSPC benchmark', 
             ha='center', va='center', transform=ax3.transAxes, fontsize=11)
    ax3.set_title('Beta Comparison', fontsize=12, fontweight='bold')

# Plot 4: Volatility Distribution
ax4 = fig.add_subplot(gs[2, :])
vol_data_all = []
for ticker in assets_to_plot:
    if ticker not in returns.columns:
        continue
    ticker_returns = returns[ticker]
    rolling_vol = ticker_returns.rolling(window=WINDOW).std() * np.sqrt(252) * 100
    vol_data_all.append(rolling_vol.dropna().values)

if vol_data_all:
    box_labels = [t for t in assets_to_plot if t in returns.columns]
    ax4.boxplot(vol_data_all, tick_labels=box_labels, vert=True)
    ax4.set_title(f'Volatility Distribution ({WINDOW}-Day Rolling)', 
                  fontsize=12, fontweight='bold')
    ax4.set_ylabel('Volatility (%)', fontsize=10)
    ax4.set_xlabel('Ticker', fontsize=10)
    label_rotation = 90 if len(box_labels) > 15 else 45
    ax4.tick_params(axis='x', rotation=label_rotation,
                    labelsize=7 if len(box_labels) > 15 else 8)
    ax4.grid(True, alpha=0.3, axis='y')

plt.suptitle('Stock Volatility Analysis', fontsize=16, fontweight='bold', y=0.985)
plt.savefig('stock_volatility_analysis.png', dpi=300, bbox_inches='tight')
print("\n[OK] Chart saved as 'stock_volatility_analysis.png'")
plt.close()
