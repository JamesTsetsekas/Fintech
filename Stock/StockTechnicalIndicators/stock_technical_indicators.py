#!/usr/bin/env python3
"""
Stock Technical Indicators Tool

Analyzes and visualizes technical indicators including RSI, MACD, and Bollinger Bands
for multiple stocks.
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
from stock_utils import apply_dark_chart_style, get_assets_from_file, get_stocks_from_source

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description='Stock Technical Indicators Tool',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python stock_technical_indicators.py                    # Use default asset list
  python stock_technical_indicators.py --source file      # Read from assets.txt
  python stock_technical_indicators.py --source single --ticker AAPL      # Single stock
  python stock_technical_indicators.py --source sp500 --top 5    # Top 5 S&P 500
  python stock_technical_indicators.py --source sector --sector Technology --top 3
  python stock_technical_indicators.py --period 6m        # 6 month period
    """
)
parser.add_argument(
    '--source', 
    choices=['default', 'file', 'single', 'sp500', 'nasdaq', 'dow', 'sector'],
    default='default',
    help='Data source: default, file, single, sp500, nasdaq, dow, or sector'
)
parser.add_argument(
    '--file',
    default='assets.txt',
    help='Path to file with tickers (one per line). Used when --source=file'
)
parser.add_argument(
    '--ticker',
    default='AAPL',
    help='Single ticker to analyze (used when --source=single)'
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
    help='Time period for analysis (e.g., 6m, 1y, 2y)'
)
args = parser.parse_args()

DATA_SOURCE = args.source
ASSETS_FILE = args.file
TICKER = args.ticker
SECTOR = args.sector
TOP_N = args.top
METRIC = args.metric
PERIOD = args.period

# Default assets list
default_assets = [
    "AAPL",
    "MSFT",
    "GOOGL",
]

# Technical indicator functions
def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return sma, upper_band, lower_band

# Determine which assets to use
if DATA_SOURCE == 'file':
    assets = get_assets_from_file(ASSETS_FILE)
    print(f"Loaded {len(assets)} tickers from {ASSETS_FILE}")
elif DATA_SOURCE == 'single':
    assets = [TICKER]
    print(f"Analyzing single ticker: {TICKER}")
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
        time.sleep(0.5)
    except Exception as e:
        error_msg = str(e)[:60] if len(str(e)) > 60 else str(e)
        print(f"[FAILED] (Error: {error_msg})")
        time.sleep(0.5)

if not data_dict:
    raise ValueError("Failed to download any stock data.")

# Process each stock
for ticker, prices in data_dict.items():
    print(f"\n{'='*60}")
    print(f"Analyzing {ticker}")
    print(f"{'='*60}")
    
    # Calculate indicators
    rsi = calculate_rsi(prices)
    macd, signal, histogram = calculate_macd(prices)
    sma, upper_bb, lower_bb = calculate_bollinger_bands(prices)
    
    # Current indicator values
    current_price = prices.iloc[-1]
    current_rsi = rsi.iloc[-1]
    current_macd = macd.iloc[-1]
    current_signal = signal.iloc[-1]
    
    print(f"\nCurrent Price: ${current_price:.2f}")
    print(f"RSI (14): {current_rsi:.2f}", end="")
    if current_rsi > 70:
        print(" (Overbought)")
    elif current_rsi < 30:
        print(" (Oversold)")
    else:
        print(" (Neutral)")
    
    print(f"MACD: {current_macd:.4f}")
    print(f"Signal: {current_signal:.4f}")
    if current_macd > current_signal:
        print("MACD Signal: Bullish (MACD > Signal)")
    else:
        print("MACD Signal: Bearish (MACD < Signal)")
    
    # Create visualization for each stock
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), height_ratios=[2, 1, 1, 1])
    
    # Plot 1: Price with Bollinger Bands
    ax1 = axes[0]
    ax1.plot(prices.index, prices.values, label='Price', linewidth=2, color='#eef3f8')
    ax1.plot(sma.index, sma.values, label='SMA (20)', linewidth=1.5, color='#60a5fa', linestyle='--')
    ax1.fill_between(upper_bb.index, upper_bb.values, lower_bb.values, 
                     alpha=0.2, color='gray', label='Bollinger Bands')
    ax1.plot(upper_bb.index, upper_bb.values, linewidth=1, color='gray', linestyle=':')
    ax1.plot(lower_bb.index, lower_bb.values, linewidth=1, color='gray', linestyle=':')
    ax1.set_title(f'{ticker} - Price with Bollinger Bands', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Price ($)', fontsize=11)
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: RSI
    ax2 = axes[1]
    ax2.plot(rsi.index, rsi.values, label='RSI', linewidth=2, color='purple')
    ax2.axhline(y=70, color='red', linestyle='--', linewidth=1, label='Overbought (70)')
    ax2.axhline(y=30, color='green', linestyle='--', linewidth=1, label='Oversold (30)')
    ax2.fill_between(rsi.index, 30, 70, alpha=0.1, color='gray')
    ax2.set_title('RSI (14)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('RSI', fontsize=10)
    ax2.set_ylim(0, 100)
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: MACD
    ax3 = axes[2]
    ax3.plot(macd.index, macd.values, label='MACD', linewidth=2, color='#60a5fa')
    ax3.plot(signal.index, signal.values, label='Signal', linewidth=2, color='#f87171')
    ax3.bar(histogram.index, histogram.values, label='Histogram', alpha=0.3, color='gray')
    ax3.axhline(y=0, color='#cbd5e1', linestyle='-', linewidth=0.5)
    ax3.set_title('MACD (12, 26, 9)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('MACD', fontsize=10)
    ax3.legend(loc='upper left', fontsize=8)
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Volume (if available)
    ax4 = axes[3]
    try:
        ticker_obj = yf.Ticker(ticker)
        hist_full = ticker_obj.history(start=start_date, end=end_date)
        if 'Volume' in hist_full.columns:
            volume = hist_full['Volume']
            ax4.bar(volume.index, volume.values, alpha=0.6, color='blue', label='Volume')
            ax4.set_title('Volume', fontsize=12, fontweight='bold')
            ax4.set_ylabel('Volume', fontsize=10)
            ax4.set_xlabel('Date', fontsize=11)
            ax4.legend(loc='upper left', fontsize=8)
            ax4.grid(True, alpha=0.3, axis='y')
        else:
            ax4.text(0.5, 0.5, 'Volume data not available', 
                     ha='center', va='center', transform=ax4.transAxes, fontsize=11)
            ax4.set_xlabel('Date', fontsize=11)
    except:
        ax4.text(0.5, 0.5, 'Volume data not available', 
                 ha='center', va='center', transform=ax4.transAxes, fontsize=11)
        ax4.set_xlabel('Date', fontsize=11)
    
    apply_dark_chart_style(fig)
    plt.tight_layout()
    filename = f'{ticker}_technical_indicators.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    print(f"\n[OK] Chart saved as '{filename}'")
    plt.close()

print("\n" + "="*60)
print("Analysis complete!")
print("="*60)
