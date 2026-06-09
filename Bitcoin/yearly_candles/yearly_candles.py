#!/usr/bin/env python3
"""
Bitcoin Yearly Candlestick Chart

Creates a yearly candlestick chart showing Bitcoin's price history from daily data.
The chart aggregates daily price data into yearly OHLC (Open, High, Low, Close) candles.
Uses a logarithmic scale for the Y-axis to better visualize the price growth over time.
"""

import pandas as pd
import matplotlib
# Use Agg backend for saving
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import requests

def get_block_height_from_mempool():
    """Fetch current block height from mempool.space API"""
    try:
        url = 'https://mempool.space/api/blocks/tip/height'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return int(response.text.strip())
        else:
            raise Exception(f"API returned status code {response.status_code}")
    except Exception as e:
        print(f"Warning: Could not fetch block height from mempool.space API: {e}")
        print("Falling back to calculated block height...")
        return None

def calculate_block_height_fallback(date):
    """Calculate approximate block height from date (fallback method)"""
    genesis_date = datetime(2009, 1, 3)
    days_since_genesis = (date - genesis_date).days
    # Approximately 144 blocks per day (1 block every 10 minutes)
    blocks_per_day = 144
    return int(days_since_genesis * blocks_per_day)

# Load data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'
try:
    data = pd.read_csv(dataset_path)
    print(f"Loaded {len(data)} rows from {dataset_path}")
except Exception as e:
    print(f"Error loading data: {e}")
    raise

# Convert dates and prices
data['Date'] = pd.to_datetime(data['date'])
data['Close'] = pd.to_numeric(data['price'], errors='coerce')
data['High'] = pd.to_numeric(data['daily_high'], errors='coerce')
data = data.dropna(subset=['Date', 'Close', 'High'])
data = data.sort_values('Date').reset_index(drop=True)

# Get block height column if available
if 'block_height' in data.columns:
    data['BlockHeight'] = pd.to_numeric(data['block_height'], errors='coerce')
else:
    data['BlockHeight'] = None

# Create year for grouping
data['Year'] = data['Date'].dt.year

# Aggregate daily data into yearly OHLC
yearly_data = []

for year in sorted(data['Year'].unique()):
    year_data = data[data['Year'] == year].copy()
    
    if len(year_data) == 0:
        continue
    
    # Open = first price of the year
    open_price = year_data.iloc[0]['Close']
    
    # High = maximum daily_high of the year
    high_price = year_data['High'].max()
    
    # Low = minimum close price of the year (approximation)
    # Note: We don't have daily low in the dataset, so we use minimum close price
    # This is a reasonable approximation for yearly candles
    low_price = year_data['Close'].min()
    
    # As an additional check, if any high is lower than low, adjust
    # (This shouldn't happen, but handle edge cases)
    if high_price < low_price:
        low_price = year_data['High'].min()
    
    # Close = last price of the year
    close_price = year_data.iloc[-1]['Close']
    
    # Date = first day of the year (for plotting)
    year_date = year_data.iloc[0]['Date'].replace(month=1, day=1)
    
    # Block height = last block height of the year
    if year_data['BlockHeight'].notna().any():
        block_height = year_data['BlockHeight'].dropna().iloc[-1]
    else:
        block_height = None
    
    yearly_data.append({
        'Date': year_date,
        'Open': open_price,
        'High': high_price,
        'Low': low_price,
        'Close': close_price,
        'BlockHeight': block_height
    })

yearly_df = pd.DataFrame(yearly_data)
yearly_df = yearly_df.sort_values('Date').reset_index(drop=True)

print(f"Created {len(yearly_df)} yearly candles")
print(f"Date range: {yearly_df['Date'].min()} to {yearly_df['Date'].max()}")

# Get current year data (most recent)
current_year = yearly_df.iloc[-1]
current_open = current_year['Open']
current_high = current_year['High']
current_low = current_year['Low']
current_close = current_year['Close']
current_date = current_year['Date']
current_change = current_close - current_open
current_change_pct = (current_change / current_open) * 100 if current_open > 0 else 0

# Get block height
block_height = current_year['BlockHeight']
if pd.isna(block_height):
    block_height = get_block_height_from_mempool()
    if block_height is None:
        block_height = calculate_block_height_fallback(yearly_df['Date'].max())
        block_height = int(block_height)

# Calculate candle width based on the date range
# Make candles take up roughly 70% of the average spacing between years
total_years = len(yearly_df)
if total_years > 1:
    total_days = (yearly_df['Date'].max() - yearly_df['Date'].min()).days
    avg_days_per_year = total_days / (total_years - 1) if total_years > 1 else 365
    # Use about 70% of the average spacing for candle width
    # Convert days to matplotlib date units (1 day = 1.0 in matplotlib)
    candle_width_num = avg_days_per_year * 0.7
else:
    # Default to ~250 days width
    candle_width_num = 250.0

# Create figure with dark background
fig, ax = plt.subplots(figsize=(20, 12))
fig.patch.set_facecolor('#1a1a1a')  # Dark grey background
ax.set_facecolor('#1a1a1a')

# Plot yearly candlesticks
for idx, row in yearly_df.iterrows():
    year_date = row['Date']
    open_price = row['Open']
    high_price = row['High']
    low_price = row['Low']
    close_price = row['Close']
    
    # Determine candle color (green if close >= open, red if close < open)
    is_green = close_price >= open_price
    candle_color = '#00FF00' if is_green else '#FF0000'  # Green or red
    
    # Convert date to numeric for matplotlib
    date_num = mdates.date2num(year_date)
    
    # Draw wick (high-low line)
    ax.plot([date_num, date_num], [low_price, high_price], 
            color=candle_color, linewidth=1.5, zorder=2)
    
    # Draw candle body (open-close rectangle)
    body_top = max(open_price, close_price)
    body_bottom = min(open_price, close_price)
    body_height = body_top - body_bottom
    
    # Minimum height for flat candles
    if body_height == 0:
        body_height = body_top * 0.01
    
    # Create rectangle for candle body
    candle_body = Rectangle(
        (date_num - candle_width_num/2, body_bottom),
        candle_width_num,
        body_height,
        facecolor=candle_color,
        edgecolor=candle_color,
        linewidth=1,
        zorder=3
    )
    ax.add_patch(candle_body)

# Format Y-axis (price scale) - LOGARITHMIC SCALE
y_min = 1
y_max = max(yearly_df['High'].max(), 100000)  # Up to $100k
ax.set_ylim(y_min, y_max)
ax.set_yscale('log')

# Set Y-axis ticks for logarithmic scale
# Create ticks at powers of 10: $1, $10, $100, $1k, $10k, $100k
y_ticks = [1, 10, 100, 1000, 10000, 100000]
y_ticks = [t for t in y_ticks if y_min <= t <= y_max]
ax.set_yticks(y_ticks)

# Format Y-axis labels
def format_price_y(x, p):
    if x >= 1000:
        return f'${x/1000:.0f}k'
    elif x >= 1:
        return f'${x:.0f}'
    else:
        return f'${x:.2f}'

ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_y))

# Format X-axis (years)
ax.set_xlim(yearly_df['Date'].min(), yearly_df['Date'].max())
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.xaxis.set_minor_locator(mdates.YearLocator())

# Set colors
ax.tick_params(colors='lightgray', labelsize=10)
ax.set_ylabel('Price (USD)', color='lightgray', fontsize=12)

# Add grid
ax.grid(True, which="major", linestyle='-', alpha=0.1, color='gray', linewidth=0.5)
ax.grid(True, which="minor", linestyle='--', alpha=0.05, color='gray', linewidth=0.3)

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('lightgray')
ax.spines['bottom'].set_color('lightgray')

# --- HEADER SECTION ---
header_y = 0.96

# Bitcoin logo/title (left side)
fig.text(0.02, header_y, 'bitcoin',
         fontsize=24, fontweight='bold', color='#ff8c00',
         verticalalignment='top', horizontalalignment='left')

# Price data (1Y indicates yearly timeframe)
price_text = f"1Y · O{current_open:.2f} H{current_high:.0f} L{current_low:.2f} C{current_close:.2f} {current_change:+.2f} ({current_change_pct:+.2f}%)"
fig.text(0.15, header_y, price_text,
         fontsize=11, color='lightgray', family='monospace',
         verticalalignment='top', horizontalalignment='left')

# Date and Block Height (right side)
# Use the most recent date from the data, not the year start date
latest_date = data['Date'].max()
date_str = latest_date.strftime('%b %d, %Y %H:%M (UTC)')
fig.text(0.98, header_y, date_str,
         fontsize=10, color='lightgray',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.98, header_y - 0.025, f'Block Height: {int(block_height):,}',
         fontsize=10, color='lightgray',
         verticalalignment='top', horizontalalignment='right')

# Adjust layout
plt.tight_layout(rect=[0, 0, 1, 0.96])

# Save the chart
output_path = script_dir / 'yearly_candles.png'
try:
    plt.savefig(output_path, dpi=150, facecolor='#1a1a1a', bbox_inches=None)
    print(f"Chart saved as '{output_path}'")
    print(f"Current Date: {latest_date.strftime('%Y-%m-%d')}")
    print(f"Current Year Close Price: ${current_close:,.2f}")
    print(f"Block Height: {int(block_height):,}")
except Exception as e:
    print(f"Error saving chart: {e}")
    import traceback
    traceback.print_exc()
    raise

plt.close(fig)

