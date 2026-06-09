#!/usr/bin/env python3
"""
Jellybean Chart - Annual Sector Returns Visualization

Creates a colorful table showing annual returns by sector, similar to traditional
jellybean charts used in financial planning. Displays:
- Annual returns for each sector by year
- BEST and WORST performers for each year
- Annualized returns over the period
- Standard deviation (volatility) for each sector
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import argparse
import logging
import time
from typing import Dict, List, Tuple
import os
import sys

# Add parent directory to path to import stock_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from stock_utils import (
    STOCK_CHART_BG,
    STOCK_CHART_MUTED,
    STOCK_CHART_SPINE,
    STOCK_CHART_TEXT,
    get_sector_tickers_from_sp500,
)

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description='Jellybean Chart - Annual Sector Returns Visualization',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python jellybean_chart.py                          # Use default years (2005-2024)
  python jellybean_chart.py --start 2010 --end 2024  # Custom year range
  python jellybean_chart.py --period 10y             # Last 10 years
    """
)
parser.add_argument(
    '--start',
    type=int,
    default=None,
    help='Start year (default: 2005 or 10 years ago if using --period)'
)
parser.add_argument(
    '--end',
    type=int,
    default=None,
    help='End year (default: current year)'
)
parser.add_argument(
    '--period',
    type=str,
    default=None,
    help='Time period (e.g., 10y, 15y) - overrides start/end'
)
parser.add_argument(
    '--use-stocks',
    action='store_true',
    help='Use actual sector stocks from S&P 500 instead of ETFs (slower but more accurate)'
)
args = parser.parse_args()

USE_STOCKS = args.use_stocks

# Sector ETFs mapping
SECTOR_ETFS = {
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

# Representative stocks for each sector (fallback)
SECTOR_STOCKS = {
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

# Color mapping for each sector (distinct colors)
SECTOR_COLORS = {
    'Technology': '#FF6B6B',              # Red
    'Healthcare': '#4ECDC4',              # Teal
    'Financials': '#45B7D1',              # Blue
    'Consumer Discretionary': '#FFA07A',  # Light Salmon
    'Communication Services': '#98D8C8',  # Mint
    'Industrials': '#F7DC6F',             # Yellow
    'Consumer Staples': '#BB8FCE',        # Purple
    'Energy': '#F8B739',                  # Orange
    'Utilities': '#5DADE2',               # Light Blue
    'Real Estate': '#EC7063',             # Coral
    'Materials': '#A569BD',               # Medium Purple
}

CELL_SECTOR_LABELS = {
    'Communication Services': 'Comm.\nServices',
    'Consumer Discretionary': 'Consumer\nDisc.',
    'Consumer Staples': 'Consumer\nStaples',
    'Real Estate': 'Real\nEstate',
}

def format_cell_sector(sector: str) -> str:
    """Shorten long sector names inside square BEST/WORST cells."""
    return CELL_SECTOR_LABELS.get(sector, sector)

def get_sector_data(sector: str, start_date: str, end_date: str, sector_tickers_map: Dict[str, List[str]] = None) -> pd.Series:
    """Get historical price data for a sector (ETF, representative stocks, or live S&P 500 data)."""

    # If using live sector data from S&P 500
    if USE_STOCKS and sector_tickers_map and sector in sector_tickers_map:
        tickers = sector_tickers_map[sector][:5]  # Use top 5 stocks
        stock_prices = []

        for ticker in tickers:
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
            return pd.DataFrame(stock_prices).mean()

    # Try ETF (default method)
    etf = SECTOR_ETFS.get(sector)
    if etf:
        try:
            ticker_obj = yf.Ticker(etf)
            hist = ticker_obj.history(start=start_date, end=end_date)

            if not hist.empty and len(hist) > 0:
                if "Adj Close" in hist.columns:
                    return hist["Adj Close"]
                elif "Close" in hist.columns:
                    return hist["Close"]
        except:
            pass

    # Try representative stocks as fallback
    stock_prices = []
    for stock in SECTOR_STOCKS.get(sector, [])[:2]:
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
        return pd.DataFrame(stock_prices).mean()

    return pd.Series(dtype=float)

def calculate_annual_returns(data: pd.Series, year: int) -> float:
    """Calculate annual return for a given year."""
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"
    
    year_data = data[(data.index >= year_start) & (data.index <= year_end)]
    
    if len(year_data) < 2:
        return np.nan
    
    start_price = year_data.iloc[0]
    end_price = year_data.iloc[-1]
    
    if pd.isna(start_price) or pd.isna(end_price) or start_price == 0:
        return np.nan
    
    return ((end_price / start_price) - 1) * 100

def calculate_annualized_return(data: pd.Series, start_date: str, end_date: str) -> float:
    """Calculate annualized return over the entire period."""
    period_data = data[(data.index >= start_date) & (data.index <= end_date)]
    
    if len(period_data) < 2:
        return np.nan
    
    start_price = period_data.iloc[0]
    end_price = period_data.iloc[-1]
    
    if pd.isna(start_price) or pd.isna(end_price) or start_price == 0:
        return np.nan
    
    days = (period_data.index[-1] - period_data.index[0]).days
    years = days / 365.25 if days > 0 else 1
    
    return ((end_price / start_price) ** (1/years) - 1) * 100

def calculate_standard_deviation(data: pd.Series) -> float:
    """Calculate annualized standard deviation (volatility)."""
    returns = data.pct_change().dropna()
    if len(returns) < 2:
        return np.nan
    return returns.std() * np.sqrt(252) * 100

# Determine year range
current_year = datetime.now().year
if args.period:
    if args.period.endswith('y'):
        years = int(args.period[:-1])
        start_year = current_year - years
    else:
        start_year = 2005
else:
    start_year = args.start if args.start else 2005

end_year = args.end if args.end else current_year

print("Jellybean Chart - Annual Sector Returns")
print("="*60)
print(f"Analyzing years: {start_year}-{end_year}\n")

# Download sector data
print("Downloading sector data...")
if USE_STOCKS:
    print("[INFO] Using live sector classifications from S&P 500 companies (this may take longer)...")

sector_data = {}
sector_tickers_map = None

# Fetch live sector mapping if requested
if USE_STOCKS:
    try:
        print("[INFO] Fetching live sector classifications...")
        sector_tickers_map = get_sector_tickers_from_sp500()
        print(f"[INFO] Retrieved {len(sector_tickers_map)} sectors with live data")
    except Exception as e:
        print(f"[ERROR] Failed to fetch dynamic sector data: {e}")
        print("[INFO] Falling back to ETF-based analysis...")
        USE_STOCKS = False

# Download data for each sector
for sector in SECTOR_ETFS.keys():
    print(f"Downloading {sector}...", end=" ", flush=True)
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"

    data = get_sector_data(sector, start_date, end_date, sector_tickers_map)

    if not data.empty and len(data) > 0:
        sector_data[sector] = data
        if USE_STOCKS and sector_tickers_map and sector in sector_tickers_map:
            print(f"[OK] (using {min(5, len(sector_tickers_map[sector]))} stocks)")
        else:
            print("[OK]")
    else:
        print("[FAILED]")

    time.sleep(0.3)  # Rate limiting

if not sector_data:
    raise ValueError("Failed to download any sector data.")

# Calculate annual returns for each sector and year
years = list(range(start_year, end_year + 1))
annual_returns = {}

for sector in sector_data.keys():
    annual_returns[sector] = {}
    for year in years:
        ret = calculate_annual_returns(sector_data[sector], year)
        annual_returns[sector][year] = ret

# Create DataFrame for annual returns
returns_df = pd.DataFrame(annual_returns, index=years)
returns_df = returns_df.T  # Sectors as rows, years as columns

# Calculate annualized returns and standard deviations
annualized_returns = {}
std_deviations = {}

for sector in sector_data.keys():
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"
    ann_ret = calculate_annualized_return(sector_data[sector], start_date, end_date)
    std_dev = calculate_standard_deviation(sector_data[sector])
    
    annualized_returns[sector] = ann_ret
    std_deviations[sector] = std_dev

# Find BEST and WORST for each year
best_performers = {}
worst_performers = {}

for year in years:
    year_returns = returns_df[year].dropna()
    if len(year_returns) > 0:
        best_performers[year] = year_returns.idxmax()
        worst_performers[year] = year_returns.idxmin()

# Create the visualization
# Calculate optimal figure size based on number of years and sectors
n_sectors = len(returns_df.index)
n_years = len(years)
n_total_rows = n_sectors + 3  # +1 for header, +2 for BEST/WORST

# Make cells square - adjust based on content
cell_size = 1.2  # Square cells
cell_padding = 0.1  # Padding between cells
label_col_width = 1.8  # Width for BEST/WORST labels
ann_return_col_width = 1.8  # Width for annualized return column

# Calculate figure size to accommodate square cells
fig_width = label_col_width + (n_years * (cell_size + cell_padding)) + ann_return_col_width + 2
fig_height = (n_total_rows * (cell_size + cell_padding)) + 3

fig = plt.figure(figsize=(fig_width, fig_height))
ax = fig.add_subplot(111)
ax.axis('off')

# Starting position
x_start = 0.5
y_start = (n_sectors + 2) * (cell_size + cell_padding)  # +2 for header and BEST row

# Create color map for returns (light to dark based on value)
def get_cell_color(sector: str, value: float) -> str:
    """Get color for a cell based on sector and return value."""
    base_color = SECTOR_COLORS.get(sector, '#CCCCCC')
    
    if pd.isna(value):
        return '#1f2937'  # Muted cell for missing data
    
    # Make color intensity based on absolute return
    # Higher returns = more intense color
    intensity = min(abs(value) / 60.0, 1.0)  # Scale to 0-1, adjusted for better range
    
    # For positive returns, use the sector color (brighter)
    # For negative returns, use a muted red/orange
    if value < 0:
        # Use a red gradient for negative returns
        red_intensity = min(abs(value) / 40.0, 1.0)
        return mcolors.rgb2hex([0.9 - red_intensity * 0.4, 0.7 - red_intensity * 0.3, 0.7 - red_intensity * 0.3])
    else:
        # Use sector color with better intensity scaling
        rgb = mcolors.hex2color(base_color)
        # Make positive returns brighter and more vibrant
        return mcolors.rgb2hex([min(1.0, c * (0.7 + intensity * 0.3)) for c in rgb])

# Draw header row (Years + Annualized Return)
header_y = y_start + cell_size
header_bg = Rectangle((x_start - 0.05, header_y - cell_size/2), 
                     label_col_width + (n_years * (cell_size + cell_padding)) + ann_return_col_width + 0.1, 
                     cell_size,
                     facecolor='#2C3E50', edgecolor='none', alpha=0.9)
ax.add_patch(header_bg)

x_pos = x_start + label_col_width + cell_padding
for year in years:
    ax.text(x_pos + cell_size / 2, header_y, str(year),
            ha='center', va='center', fontsize=10, fontweight='bold', color='white')
    x_pos += cell_size + cell_padding

# Annualized Return header
ax.text(x_pos + ann_return_col_width / 2, header_y, 'ANNUALIZED\nRETURN',
        ha='center', va='center', fontsize=10, fontweight='bold', color='white')

# Draw BEST row at the top (right after header)
best_y = y_start
best_label_bg = Rectangle((x_start, best_y - cell_size/2), label_col_width, cell_size,
                         facecolor='#27AE60', edgecolor='white', linewidth=1.5, alpha=0.9)
ax.add_patch(best_label_bg)
ax.text(x_start + label_col_width / 2, best_y, 'BEST',
        ha='center', va='center', fontsize=10, fontweight='bold', color='white')

x_pos = x_start + label_col_width + cell_padding
for year in years:
    if year in best_performers:
        sector = best_performers[year]
        value = returns_df.loc[sector, year]
        color = SECTOR_COLORS.get(sector, '#CCCCCC')
        
        rect = Rectangle((x_pos, best_y - cell_size/2), cell_size, cell_size,
                        facecolor=color, edgecolor='black', linewidth=1.5, alpha=0.95)
        ax.add_patch(rect)
        
        if not pd.isna(value):
            rgb = mcolors.hex2color(color)
            brightness = sum(rgb) / 3
            text_color = 'white' if brightness < 0.5 else 'black'
            
            ax.text(x_pos + cell_size / 2, best_y,
                   f'{format_cell_sector(sector)}\n{value:.2f}%', ha='center', va='center',
                   fontsize=7, fontweight='bold', color=text_color)
    x_pos += cell_size + cell_padding

# Add annualized return for BEST row (calculate best annualized)
best_ann_ret = max([(s, annualized_returns.get(s, np.nan)) for s in returns_df.index], 
                  key=lambda x: x[1] if not pd.isna(x[1]) else -999)
if not pd.isna(best_ann_ret[1]):
    ann_color = SECTOR_COLORS.get(best_ann_ret[0], '#CCCCCC')
    ann_rect = Rectangle((x_pos, best_y - cell_size/2), 
                       ann_return_col_width, cell_size,
                       facecolor=ann_color, edgecolor='black', linewidth=1.5, alpha=0.95)
    ax.add_patch(ann_rect)
    ann_rgb = mcolors.hex2color(ann_color)
    ann_brightness = sum(ann_rgb) / 3
    ann_text_color = 'white' if ann_brightness < 0.5 else 'black'
    ax.text(x_pos + ann_return_col_width / 2, best_y,
           f'{best_ann_ret[1]:.2f}%', ha='center', va='center',
           fontsize=8, fontweight='bold', color=ann_text_color)

# Draw sector rows (without sector name column)
y_pos = best_y - (cell_size + cell_padding)
for idx, sector in enumerate(returns_df.index):
    # Annual returns for each year - square cells
    x_pos = x_start + label_col_width + cell_padding
    for year in years:
        value = returns_df.loc[sector, year]
        color = get_cell_color(sector, value)
        
        # Square cell
        rect = Rectangle((x_pos, y_pos - cell_size/2), cell_size, cell_size,
                        facecolor=color, edgecolor='black', linewidth=0.5, alpha=0.95)
        ax.add_patch(rect)
        
        if not pd.isna(value):
            # Determine text color based on cell background
            cell_rgb = mcolors.hex2color(color)
            cell_brightness = sum(cell_rgb) / 3
            cell_text_color = 'white' if cell_brightness < 0.6 else 'black'
            
            ax.text(x_pos + cell_size / 2, y_pos,
                   f'{value:.2f}%', ha='center', va='center',
                   fontsize=7, fontweight='bold', color=cell_text_color)
        x_pos += cell_size + cell_padding
    
    # Annualized return - square cell
    ann_ret = annualized_returns.get(sector, np.nan)
    color = '#1f2937' if pd.isna(ann_ret) else get_cell_color(sector, ann_ret)
    ann_rect = Rectangle((x_pos, y_pos - cell_size/2), ann_return_col_width, cell_size,
                    facecolor=color, edgecolor='black', linewidth=0.5, alpha=0.95)
    ax.add_patch(ann_rect)
    
    if not pd.isna(ann_ret):
        ann_rgb = mcolors.hex2color(color)
        ann_brightness = sum(ann_rgb) / 3
        ann_text_color = 'white' if ann_brightness < 0.6 else 'black'
        
        ax.text(x_pos + ann_return_col_width / 2, y_pos,
               f'{ann_ret:.2f}%', ha='center', va='center',
               fontsize=8, fontweight='bold', color=ann_text_color)
    
    y_pos -= (cell_size + cell_padding)

# Draw WORST row at the bottom
worst_y = y_pos
worst_label_bg = Rectangle((x_start, worst_y - cell_size/2), label_col_width, cell_size,
                          facecolor='#E74C3C', edgecolor='white', linewidth=1.5, alpha=0.9)
ax.add_patch(worst_label_bg)
ax.text(x_start + label_col_width / 2, worst_y, 'WORST',
        ha='center', va='center', fontsize=10, fontweight='bold', color='white')

x_pos = x_start + label_col_width + cell_padding
for year in years:
    if year in worst_performers:
        sector = worst_performers[year]
        value = returns_df.loc[sector, year]
        color = SECTOR_COLORS.get(sector, '#CCCCCC')
        
        rect = Rectangle((x_pos, worst_y - cell_size/2), cell_size, cell_size,
                        facecolor=color, edgecolor='black', linewidth=1.5, alpha=0.95)
        ax.add_patch(rect)
        
        if not pd.isna(value):
            rgb = mcolors.hex2color(color)
            brightness = sum(rgb) / 3
            text_color = 'white' if brightness < 0.5 else 'black'
            
            ax.text(x_pos + cell_size / 2, worst_y,
                   f'{format_cell_sector(sector)}\n{value:.2f}%', ha='center', va='center',
                   fontsize=7, fontweight='bold', color=text_color)
    x_pos += cell_size + cell_padding

# Add annualized return for WORST row
worst_ann_ret = min([(s, annualized_returns.get(s, np.nan)) for s in returns_df.index], 
                   key=lambda x: x[1] if not pd.isna(x[1]) else 999)
if not pd.isna(worst_ann_ret[1]):
    ann_color = SECTOR_COLORS.get(worst_ann_ret[0], '#CCCCCC')
    ann_rect = Rectangle((x_pos, worst_y - cell_size/2), 
                       ann_return_col_width, cell_size,
                       facecolor=ann_color, edgecolor='black', linewidth=1.5, alpha=0.95)
    ax.add_patch(ann_rect)
    ann_rgb = mcolors.hex2color(ann_color)
    ann_brightness = sum(ann_rgb) / 3
    ann_text_color = 'white' if ann_brightness < 0.5 else 'black'
    ax.text(x_pos + ann_return_col_width / 2, worst_y,
           f'{worst_ann_ret[1]:.2f}%', ha='center', va='center',
           fontsize=8, fontweight='bold', color=ann_text_color)

# Set axis limits
total_width = label_col_width + (n_years * (cell_size + cell_padding)) + ann_return_col_width + 1
ax.set_xlim(0, total_width)
ax.set_ylim(worst_y - (cell_size + cell_padding) - 1, header_y + cell_size/2 + 1)

# Add title with better styling
fig.suptitle(f'Sector Performance Jellybean Chart\n{start_year}-{end_year} Annual Returns',
             fontsize=18, fontweight='bold', y=0.995, color=STOCK_CHART_TEXT)

# Add compact footer blocks for the sector legend and standard deviation table.
footer_header_y = worst_y - (cell_size + cell_padding) - 1.2
footer_row_gap = 0.52
footer_header_height = 0.55
footer_text_top = footer_header_y - 0.58

sectors_present = [sector for sector in SECTOR_COLORS if sector in returns_df.index]
legend_x = x_start
legend_width = 6.3
legend_col_width = 3.05
legend_rows = (len(sectors_present) + 1) // 2

legend_header = Rectangle((legend_x, footer_header_y), legend_width, footer_header_height,
                          facecolor='#34495E', edgecolor=STOCK_CHART_SPINE,
                          linewidth=1, alpha=0.95)
ax.add_patch(legend_header)
ax.text(legend_x + legend_width / 2, footer_header_y + footer_header_height / 2,
        'MARKET SEGMENT', ha='center', va='center', fontsize=10,
        fontweight='bold', color=STOCK_CHART_TEXT)

for i, sector in enumerate(sectors_present):
    col = i // legend_rows
    row = i % legend_rows
    item_x = legend_x + 0.35 + col * legend_col_width
    item_y = footer_text_top - row * footer_row_gap
    square = Rectangle((item_x, item_y - 0.1), 0.18, 0.18,
                       facecolor=SECTOR_COLORS[sector], edgecolor='white',
                       linewidth=0.4)
    ax.add_patch(square)
    ax.text(item_x + 0.32, item_y, sector, ha='left', va='center',
            fontsize=8, color=STOCK_CHART_TEXT, fontweight='bold')

std_table_x = legend_x + legend_width + 0.8
std_width = 5.0
std_header = Rectangle((std_table_x, footer_header_y), std_width, footer_header_height,
                       facecolor='#34495E', edgecolor=STOCK_CHART_SPINE,
                       linewidth=1, alpha=0.95)
ax.add_patch(std_header)
ax.text(std_table_x + std_width / 2, footer_header_y + footer_header_height / 2,
        'STANDARD DEVIATION', ha='center', va='center', fontsize=10,
        fontweight='bold', color=STOCK_CHART_TEXT)

std_rows = 0
for std_rows, sector in enumerate(sorted(std_deviations.keys(), key=lambda x: std_deviations.get(x, 0)), start=1):
    std_dev = std_deviations.get(sector, np.nan)
    if pd.isna(std_dev):
        continue
    item_y = footer_text_top - (std_rows - 1) * footer_row_gap
    color = SECTOR_COLORS.get(sector, '#CCCCCC')
    square = Rectangle((std_table_x + 0.35, item_y - 0.1), 0.18, 0.18,
                       facecolor=color, edgecolor='white', linewidth=0.4)
    ax.add_patch(square)
    ax.text(std_table_x + 0.65, item_y, sector, ha='left', va='center',
            fontsize=8, color=STOCK_CHART_TEXT, fontweight='bold')
    ax.text(std_table_x + std_width - 0.35, item_y, f'{std_dev:.2f}',
            ha='right', va='center', fontsize=8, color=STOCK_CHART_MUTED,
            fontweight='bold')

footer_bottom = min(
    footer_text_top - max(legend_rows - 1, 0) * footer_row_gap,
    footer_text_top - max(std_rows - 1, 0) * footer_row_gap,
) - 0.7
ax.set_ylim(footer_bottom, header_y + cell_size/2 + 0.9)

# Set background color
fig.patch.set_facecolor(STOCK_CHART_BG)
ax.set_facecolor(STOCK_CHART_BG)

plt.tight_layout(rect=[0, 0, 1, 0.97])
plt.savefig('jellybean_chart.png', dpi=300, bbox_inches='tight',
            facecolor=fig.get_facecolor(), edgecolor='none')
print("\n[OK] Chart saved as 'jellybean_chart.png'")
plt.close()

# Print summary statistics
print("\n" + "="*60)
print("Summary Statistics")
print("="*60)
print(f"\nAnnualized Returns ({start_year}-{end_year}):")
sorted_sectors = sorted(annualized_returns.items(), key=lambda x: x[1] if not pd.isna(x[1]) else -999, reverse=True)
for sector, ann_ret in sorted_sectors:
    if not pd.isna(ann_ret):
        print(f"  {sector:30s}: {ann_ret:7.2f}%")

print(f"\nStandard Deviation (Volatility):")
sorted_std = sorted(std_deviations.items(), key=lambda x: x[1] if not pd.isna(x[1]) else 999)
for sector, std_dev in sorted_std:
    if not pd.isna(std_dev):
        print(f"  {sector:30s}: {std_dev:7.2f}%")
