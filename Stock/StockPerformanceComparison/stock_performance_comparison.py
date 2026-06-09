#!/usr/bin/env python3
"""
Stock Performance Comparison Tool

Compares normalized performance of multiple stocks over time, showing
which stocks have outperformed or underperformed relative to each other.
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
    description='Stock Performance Comparison Tool',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python stock_performance_comparison.py                    # Use default asset list
  python stock_performance_comparison.py --source file      # Read from assets.txt
  python stock_performance_comparison.py --source sp500 --top 10    # Top 10 S&P 500
  python stock_performance_comparison.py --source nasdaq --top 20    # Top 20 NASDAQ
  python stock_performance_comparison.py --source sector --sector Technology --top 5
  python stock_performance_comparison.py --period 2y        # 2 year period
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
    help='Time period for analysis (e.g., 1y, 2y, 5y, 10y, or YYYY-MM-DD format)'
)
args = parser.parse_args()

DATA_SOURCE = args.source
ASSETS_FILE = args.file
SECTOR = args.sector
TOP_N = args.top
METRIC = args.metric
PERIOD = args.period

# Default assets list
default_assets = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "JPM",
    "JNJ",
    "V",
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
    # Assume it's a date string
    start_date = PERIOD

end_date = datetime.now().strftime('%Y-%m-%d')

print(f"Analyzing period: {start_date} to {end_date}\n")

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
        time.sleep(0.5)  # Delay to avoid rate limiting
    except Exception as e:
        error_msg = str(e)[:60] if len(str(e)) > 60 else str(e)
        print(f"[FAILED] (Error: {error_msg})")
        time.sleep(0.5)

if not data_dict:
    raise ValueError("Failed to download any stock data. Please check your internet connection and try again.")

# Create DataFrame
data = pd.DataFrame(data_dict)

# Normalize to starting value (100)
normalized_data = data.div(data.iloc[0]).mul(100)

# Calculate performance metrics
print("\n" + "="*60)
print("Performance Summary")
print("="*60)

performance_summary = []
for ticker in normalized_data.columns:
    start_val = normalized_data[ticker].iloc[0]
    end_val = normalized_data[ticker].iloc[-1]
    total_return = ((end_val - start_val) / start_val) * 100
    
    # Calculate annualized return if we have enough data
    days = (normalized_data.index[-1] - normalized_data.index[0]).days
    if days > 0:
        years = days / 365.25
        annualized_return = ((end_val / start_val) ** (1/years) - 1) * 100 if years > 0 else 0
    else:
        annualized_return = 0
    
    performance_summary.append({
        'Ticker': ticker,
        'Total Return %': f"{total_return:.2f}",
        'Annualized Return %': f"{annualized_return:.2f}",
        'Final Value': f"{end_val:.2f}"
    })

summary_df = pd.DataFrame(performance_summary)
summary_df = summary_df.sort_values('Total Return %', key=lambda x: x.str.replace('%', '').astype(float), ascending=False)
print("\n" + summary_df.to_string(index=False))

# Create visualization. Scale height and labels with ticker count so generated
# variants with larger universes stay readable.
ticker_count = len(normalized_data.columns)
fig_height = min(14, max(10, 8 + ticker_count * 0.2))
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, fig_height), height_ratios=[3, 1])

# Plot 1: Normalized Performance
colors = plt.cm.tab20(np.linspace(0, 1, max(ticker_count, 3)))
for i, ticker in enumerate(normalized_data.columns):
    ax1.plot(normalized_data.index, normalized_data[ticker], 
             label=ticker, linewidth=2, color=colors[i])

ax1.set_title('Stock Performance Comparison (Normalized to 100)', 
              fontsize=16, fontweight='bold', pad=20)
ax1.set_xlabel('Date', fontsize=12)
ax1.set_ylabel('Normalized Price (Starting = 100)', fontsize=12)
legend_cols = min(4, max(2, (ticker_count + 5) // 6))
legend_font_size = 8 if ticker_count <= 15 else 6
ax1.legend(loc='upper left', ncol=legend_cols, fontsize=legend_font_size, framealpha=0.85)
ax1.grid(True, alpha=0.3)
ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.5, linewidth=1)

# Plot 2: Returns Distribution
returns = data.pct_change().dropna()
returns_summary = []
for ticker in returns.columns:
    total_return = ((normalized_data[ticker].iloc[-1] - 100) / 100) * 100
    returns_summary.append({
        'Ticker': ticker,
        'Return': total_return
    })

returns_df = pd.DataFrame(returns_summary)
returns_df = returns_df.sort_values('Return', ascending=True)

bars = ax2.barh(returns_df['Ticker'], returns_df['Return'], 
                color=plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(returns_df))))
ax2.set_title('Total Return %', fontsize=12, fontweight='bold')
ax2.set_xlabel('Return (%)', fontsize=10)
ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
ax2.grid(True, alpha=0.3, axis='x')
return_min = returns_df['Return'].min()
return_max = returns_df['Return'].max()
return_span = max(return_max - return_min, 1)
label_offset = max(return_span * 0.015, 0.5)
ax2.set_xlim(min(0, return_min) - return_span * 0.08,
             max(0, return_max) + return_span * 0.12)
ax2.tick_params(axis='y', labelsize=8 if len(returns_df) <= 15 else 6)

# Add value labels on bars
for i, (ticker, return_val) in enumerate(zip(returns_df['Ticker'], returns_df['Return'])):
    ax2.text(return_val + (label_offset if return_val >= 0 else -label_offset), i,
             f'{return_val:.1f}%', 
             va='center', ha='left' if return_val >= 0 else 'right',
             fontsize=8 if len(returns_df) <= 15 else 6)

plt.tight_layout()
plt.savefig('stock_performance_comparison.png', dpi=300, bbox_inches='tight')
print("\n[OK] Chart saved as 'stock_performance_comparison.png'")
plt.close()
