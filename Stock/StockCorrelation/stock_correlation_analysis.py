"""
Stock Correlation Analysis using Riskfolio
Based on Ray Dalio's principle of seeking uncorrelated returns
"""

# 1.0 Libraries & Data
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for automation
import riskfolio as rp
import pandas as pd
import yfinance as yf
import seaborn as sns
import matplotlib.pyplot as plt
import time
from datetime import datetime
import logging
import os
import sys
import argparse

# Add parent directory to path to import stock_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stock_utils import get_stocks_from_source, get_assets_from_file

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description='Stock Correlation Analysis using Riskfolio',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python stock_correlation_analysis.py                    # Use default asset list
  python stock_correlation_analysis.py --source file      # Read from assets.txt
  python stock_correlation_analysis.py --source sp500 --top 20    # Top 20 S&P 500
  python stock_correlation_analysis.py --source nasdaq --top 15   # Top 15 NASDAQ
  python stock_correlation_analysis.py --source sector --sector Technology --top 10
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
    help='Time period for performance-based filtering (default: 1y)'
)
args = parser.parse_args()

DATA_SOURCE = args.source
ASSETS_FILE = args.file
SECTOR = args.sector
TOP_N = args.top
METRIC = args.metric
PERIOD = args.period

# Default expanded assets list
default_assets = [
    "NVDA",
    "AAPL",
    "MSFT",
    "GOOG",
    "TSLA",
    "DIS",
    "AXP",
    "GLD",  # Gold ETF
    "^GSPC",  # SP500 benchmark
    "MRK",
    "FMC",
    "NEM",
    "MTD",
    "PNW",
    "EBAY",
    "LNT",
    "APD",
    "JNJ",
    "DOW",
    "PFG",
    "NTRS",
    "HD",
    "HWM",
    "HST",
    "STT",
    "IFF",
    "JKHY",
    "DRI",
    "ULTA",
    "URI",
    "EXPE",
    "PCAR",
    "PANW",
    "TT",
    "STX",
    "BX",
    "GPN",
    "FANG",
    "WDC",
    "AIZ",
    "VLO",
    "CHTR",
    "STE",
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
else:  # default
    assets = default_assets
    print(f"Using default list with {len(assets)} tickers")

# Remove duplicates while preserving order
seen = set()
assets = [x for x in assets if not (x in seen or seen.add(x))]

print(f"\nTotal unique assets to analyze: {len(assets)}")
print(f"Assets: {', '.join(assets[:20])}{'...' if len(assets) > 20 else ''}\n")

# Collect and format data with better error handling
print("Downloading stock data...")
print("This may take a moment due to API rate limits...\n")

# Download individually with better error handling
# yfinance 1.0 uses curl_cffi internally, so we don't need to pass a session
data_dict = {}
for ticker in assets:
    try:
        print(f"Downloading {ticker}...", end=" ", flush=True)
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(start="2018-01-01", end="2024-08-08")
        
        if not hist.empty and len(hist) > 0:
            # Prefer Adj Close, fallback to Close
            if "Adj Close" in hist.columns:
                data_dict[ticker] = hist["Adj Close"]
            elif "Close" in hist.columns:
                data_dict[ticker] = hist["Close"]
            print("[OK]")
        else:
            print(f"[FAILED] (No data)")
        time.sleep(1.5)  # Delay to avoid rate limiting
    except Exception as e:
        error_msg = str(e)[:80] if len(str(e)) > 80 else str(e)
        print(f"[FAILED] (Error: {error_msg})")
        time.sleep(1.5)

if not data_dict:
    raise ValueError("Failed to download any stock data. Please check your internet connection and try again.")

data = pd.DataFrame(data_dict)

print("\nData shape:", data.shape)
print("\nFirst few rows:")
print(data.head())

# Step 2: Convert Prices to Returns
print("\n" + "="*50)
print("Step 2: Converting Prices to Returns")
print("="*50)

# Returns
returns = data.pct_change().dropna()

# Validate we have data
if returns.empty:
    raise ValueError("No returns data available. Cannot proceed with analysis.")

print("\nReturns shape:", returns.shape)
print("\nFirst few rows of returns:")
print(returns.head())

# Median returns sorted
print("\nMedian returns (sorted):")
median_returns = returns.median().sort_values(ascending=False).to_frame()
print(median_returns)

# Step 3: Use Riskfolio's Plot Clusters
print("\n" + "="*50)
print("Step 3: Clustering Correlations")
print("="*50)

# Validate we have enough data for clustering (need at least 2 assets)
if len(returns.columns) < 2:
    raise ValueError(f"Need at least 2 assets for clustering. Only have {len(returns.columns)} asset(s).")

# Clustering Correlations
plt.figure(figsize=(12, 8))
try:
    ax = rp.plot_clusters(
        returns=returns,
        codependence='pearson',
        linkage='ward',
        k=None,
        max_k=10,
        leaf_order=True,
        dendrogram=True,
        ax=None
    )
    plt.title("Stock Correlation Clusters (Hierarchical Dendrogram)", fontsize=14, fontweight='bold')
    
    # Save without tight_layout to avoid colorbar compatibility issues
    # bbox_inches='tight' will handle the layout automatically
    plt.savefig('correlation_clusters.png', dpi=300, bbox_inches='tight', pad_inches=0.2)
    print("\nCorrelation cluster plot saved as 'correlation_clusters.png'")
    plt.close()  # Close instead of show() for automation
    # plt.show()  # Commented out for automation
except Exception as e:
    print(f"\nError creating cluster plot: {e}")
    print("This might be due to insufficient data or correlation calculation issues.")
    raise


