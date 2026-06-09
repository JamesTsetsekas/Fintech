#!/usr/bin/env python3
"""
Stock Sector Performance Tool

Compares performance across different sectors using sector ETFs and representative stocks.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import argparse
import logging
import time
import os
import sys

# Add parent directory to path to import stock_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from stock_utils import get_sector_tickers_from_sp500

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

DARK_DIVERGING_HEATMAP = LinearSegmentedColormap.from_list(
    'dark_diverging_heatmap',
    ['#7f1d1d', '#2b0b0d', '#050608', '#0b1f17', '#166534'],
    N=256,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description='Stock Sector Performance Tool',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python stock_sector_performance.py                    # Use default sector ETFs
  python stock_sector_performance.py --period 2y        # 2 year period
  python stock_sector_performance.py --period 5y        # 5 year period
    """
)
parser.add_argument(
    '--period',
    default='1y',
    help='Time period for analysis (e.g., 1y, 2y, 5y)'
)
parser.add_argument(
    '--use-stocks',
    action='store_true',
    help='Use actual sector stocks from S&P 500 instead of ETFs (slower but more accurate)'
)
args = parser.parse_args()

PERIOD = args.period
USE_STOCKS = args.use_stocks

# Sector ETFs mapping
sector_etfs = {
    'Technology': 'XLK',
    'Healthcare': 'XLV',
    'Financials': 'XLF',
    'Consumer Discretionary': 'XLY',
    'Communication Services': 'XLC',
    'Industrials': 'XLI',
    'Consumer Staples': 'XLP',
    'Energy': 'XLE',
    'Utilities': 'XLU',
    'Real Estate': 'XLRE',
    'Materials': 'XLB',
}

# Representative stocks for each sector (if ETFs fail)
sector_stocks = {
    'Technology': ['AAPL', 'MSFT', 'NVDA'],
    'Healthcare': ['JNJ', 'UNH', 'PFE'],
    'Financials': ['JPM', 'BAC', 'WFC'],
    'Consumer Discretionary': ['AMZN', 'TSLA', 'HD'],
    'Communication Services': ['GOOGL', 'META', 'NFLX'],
    'Industrials': ['BA', 'CAT', 'GE'],
    'Consumer Staples': ['PG', 'KO', 'WMT'],
    'Energy': ['XOM', 'CVX', 'COP'],
    'Utilities': ['NEE', 'DUK', 'SO'],
    'Real Estate': ['AMT', 'PLD', 'EQIX'],
    'Materials': ['LIN', 'APD', 'ECL'],
}

print("Stock Sector Performance Analysis")
print("="*60)
print(f"Analyzing period: {PERIOD}\n")

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

# Download sector data
print("Downloading sector data...")
if USE_STOCKS:
    print("[INFO] Using live sector classifications from S&P 500 companies (this may take a few minutes)...")
sector_data = {}
sector_returns = {}

if USE_STOCKS:
    # Use dynamic sector fetching from S&P 500
    try:
        sector_mapping = get_sector_tickers_from_sp500()
        print(f"[INFO] Retrieved {len(sector_mapping)} sectors with live data")

        for sector, tickers in sector_mapping.items():
            if not tickers:
                continue

            print(f"Downloading {sector} ({len(tickers)} stocks)...", end=" ", flush=True)
            stock_prices = []

            # Use top 5 stocks by market cap from each sector
            for ticker in tickers[:5]:
                try:
                    ticker_obj = yf.Ticker(ticker)
                    hist = ticker_obj.history(start=start_date, end=end_date)
                    if not hist.empty:
                        if "Adj Close" in hist.columns:
                            stock_prices.append(hist["Adj Close"])
                        elif "Close" in hist.columns:
                            stock_prices.append(hist["Close"])
                    time.sleep(0.1)
                except:
                    continue

            if stock_prices:
                # Average the stock prices
                sector_data[sector] = pd.DataFrame(stock_prices).mean()
                print(f"[OK] (using {len(stock_prices)} stocks)")
            else:
                print("[FAILED] (No data)")
            time.sleep(0.3)
    except Exception as e:
        print(f"[ERROR] Failed to fetch dynamic sector data: {e}")
        print("[INFO] Falling back to ETF-based analysis...")
        USE_STOCKS = False

if not USE_STOCKS:
    # Use ETFs (faster, traditional method)
    for sector, etf in sector_etfs.items():
        try:
            print(f"Downloading {sector} ({etf})...", end=" ", flush=True)
            ticker_obj = yf.Ticker(etf)
            hist = ticker_obj.history(start=start_date, end=end_date)

            if not hist.empty and len(hist) > 0:
                if "Adj Close" in hist.columns:
                    sector_data[sector] = hist["Adj Close"]
                elif "Close" in hist.columns:
                    sector_data[sector] = hist["Close"]
                print("[OK]")
            else:
                # Try representative stocks
                print("[FAILED] (ETF failed, trying stocks)...", end=" ", flush=True)
                stock_prices = []
                for stock in sector_stocks[sector][:2]:  # Try first 2 stocks
                    try:
                        stock_obj = yf.Ticker(stock)
                        stock_hist = stock_obj.history(start=start_date, end=end_date)
                        if not stock_hist.empty:
                            if "Adj Close" in stock_hist.columns:
                                stock_prices.append(stock_hist["Adj Close"])
                            elif "Close" in stock_hist.columns:
                                stock_prices.append(stock_hist["Close"])
                    except:
                        pass

                if stock_prices:
                    # Average the stock prices
                    sector_data[sector] = pd.DataFrame(stock_prices).mean()
                    print("[OK] (using stocks)")
                else:
                    print("[FAILED] (No data)")
            time.sleep(0.5)
        except Exception as e:
            error_msg = str(e)[:50] if len(str(e)) > 50 else str(e)
            print(f"[FAILED] (Error: {error_msg})")
            time.sleep(0.5)

if not sector_data:
    raise ValueError("Failed to download any sector data.")

# Create DataFrame
data = pd.DataFrame(sector_data)

# Normalize to starting value (100)
normalized_data = data.div(data.iloc[0]).mul(100)

# Calculate performance metrics
print("\n" + "="*60)
print("Sector Performance Summary")
print("="*60)

performance_summary = []
for sector in normalized_data.columns:
    start_val = normalized_data[sector].iloc[0]
    end_val = normalized_data[sector].iloc[-1]
    total_return = ((end_val - start_val) / start_val) * 100
    
    # Calculate annualized return
    days = (normalized_data.index[-1] - normalized_data.index[0]).days
    if days > 0:
        years = days / 365.25
        annualized_return = ((end_val / start_val) ** (1/years) - 1) * 100 if years > 0 else 0
    else:
        annualized_return = 0
    
    # Calculate volatility
    returns = data[sector].pct_change().dropna()
    volatility = returns.std() * np.sqrt(252) * 100
    
    performance_summary.append({
        'Sector': sector,
        'Total Return %': f"{total_return:.2f}",
        'Annualized Return %': f"{annualized_return:.2f}",
        'Volatility %': f"{volatility:.2f}",
        'Final Value': f"{end_val:.2f}"
    })

summary_df = pd.DataFrame(performance_summary)
summary_df = summary_df.sort_values('Total Return %', 
                                     key=lambda x: x.str.replace('%', '').astype(float), 
                                     ascending=False)
print("\n" + summary_df.to_string(index=False))

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Stock Sector Performance Analysis', fontsize=16, fontweight='bold', y=0.995)

# Plot 1: Normalized Performance Over Time
ax1 = axes[0, 0]
colors = plt.cm.tab20(np.linspace(0, 1, len(normalized_data.columns)))
for i, sector in enumerate(normalized_data.columns):
    ax1.plot(normalized_data.index, normalized_data[sector], 
             label=sector, linewidth=2, color=colors[i])

ax1.set_title('Sector Performance (Normalized to 100)', fontsize=12, fontweight='bold')
ax1.set_xlabel('Date', fontsize=10)
ax1.set_ylabel('Normalized Price (Starting = 100)', fontsize=10)
sector_count = len(normalized_data.columns)
legend_cols = min(3, max(2, (sector_count + 5) // 6))
ax1.legend(loc='upper left', ncol=legend_cols,
           fontsize=8 if sector_count <= 12 else 6, framealpha=0.85)
ax1.grid(True, alpha=0.3)
ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.5, linewidth=1)

# Plot 2: Total Returns Bar Chart
ax2 = axes[0, 1]
returns_data = []
sectors_list = []
for sector in normalized_data.columns:
    total_return = ((normalized_data[sector].iloc[-1] - 100) / 100) * 100
    returns_data.append(total_return)
    sectors_list.append(sector)

# Sort by return
sorted_data = sorted(zip(sectors_list, returns_data), key=lambda x: x[1], reverse=True)
sectors_sorted, returns_sorted = zip(*sorted_data)

bars = ax2.barh(sectors_sorted, returns_sorted, 
                color=plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(returns_sorted))))
ax2.set_title('Total Return %', fontsize=12, fontweight='bold')
ax2.set_xlabel('Return (%)', fontsize=10)
ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
ax2.grid(True, alpha=0.3, axis='x')
return_min = min(returns_sorted)
return_max = max(returns_sorted)
return_span = max(return_max - return_min, 1)
label_offset = max(return_span * 0.015, 0.5)
ax2.set_xlim(min(0, return_min) - return_span * 0.08,
             max(0, return_max) + return_span * 0.12)

for i, (sector, return_val) in enumerate(zip(sectors_sorted, returns_sorted)):
    ax2.text(return_val + (label_offset if return_val >= 0 else -label_offset), i,
             f'{return_val:.1f}%', 
             va='center', ha='left' if return_val >= 0 else 'right',
             fontsize=8)

# Plot 3: Risk-Return Scatter
ax3 = axes[1, 0]
volatility_data = []
return_data = []
sectors_for_scatter = []
for sector in normalized_data.columns:
    returns = data[sector].pct_change().dropna()
    vol = returns.std() * np.sqrt(252) * 100
    
    days = (normalized_data.index[-1] - normalized_data.index[0]).days
    years = days / 365.25 if days > 0 else 1
    end_val = normalized_data[sector].iloc[-1]
    ann_return = ((end_val / 100) ** (1/years) - 1) * 100 if years > 0 else 0
    
    volatility_data.append(vol)
    return_data.append(ann_return)
    sectors_for_scatter.append(sector)

scatter = ax3.scatter(volatility_data, return_data, s=100, alpha=0.6, c=range(len(sectors_for_scatter)), 
                      cmap='tab20', edgecolors='black', linewidths=1)

label_offsets = [
    (8, 8), (-16, 8), (8, -16), (-16, -16),
    (10, 28), (-18, 26), (10, 8), (-18, 8),
    (10, -18), (-18, -18), (10, -32),
]
for i, sector in enumerate(sectors_for_scatter):
    offset = label_offsets[i % len(label_offsets)]
    ax3.annotate(sector, (volatility_data[i], return_data[i]),
                xytext=offset, textcoords='offset points',
                fontsize=8, ha='left' if offset[0] >= 0 else 'right', va='bottom')
ax3.margins(x=0.12, y=0.12)

ax3.set_title('Risk-Return Profile', fontsize=12, fontweight='bold')
ax3.set_xlabel('Volatility (Annualized %)', fontsize=10)
ax3.set_ylabel('Annualized Return (%)', fontsize=10)
ax3.grid(True, alpha=0.3)
ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax3.axvline(x=0, color='gray', linestyle='--', alpha=0.5)

# Plot 4: Sector Performance Heatmap (Monthly Returns)
ax4 = axes[1, 1]
monthly_returns = data.resample('ME').last().pct_change().dropna() * 100
monthly_returns.index = monthly_returns.index.strftime('%Y-%m')

# Transpose for better visualization
heatmap_data = monthly_returns.T

im = ax4.imshow(heatmap_data.values, aspect='auto', cmap=DARK_DIVERGING_HEATMAP, vmin=-10, vmax=10)
ax4.set_title('Monthly Returns Heatmap (%)', fontsize=12, fontweight='bold')
ax4.set_xlabel('Month', fontsize=10)
ax4.set_ylabel('Sector', fontsize=10)
ax4.set_yticks(range(len(heatmap_data.index)))
ax4.set_yticklabels(heatmap_data.index, fontsize=8)
ax4.set_xticks(range(0, len(heatmap_data.columns), max(1, len(heatmap_data.columns)//10)))
ax4.set_xticklabels([heatmap_data.columns[i] for i in range(0, len(heatmap_data.columns), max(1, len(heatmap_data.columns)//10))], 
                     rotation=45, ha='right', fontsize=7)

# Add colorbar
cbar = plt.colorbar(im, ax=ax4)
cbar.set_label('Return (%)', fontsize=9)

plt.tight_layout()
plt.savefig('stock_sector_performance.png', dpi=300, bbox_inches='tight')
print("\n[OK] Chart saved as 'stock_sector_performance.png'")
plt.close()
