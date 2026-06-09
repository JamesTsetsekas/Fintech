#!/usr/bin/env python3
"""
Bitcoin Monthly Candlestick Chart

Creates a monthly candlestick chart showing Bitcoin's price history from daily data.
The chart aggregates daily price data into monthly OHLC (Open, High, Low, Close) candles.
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

# Create year-month for grouping
data['YearMonth'] = data['Date'].dt.to_period('M')

# Aggregate daily data into monthly OHLC
monthly_data = []

for year_month in data['YearMonth'].unique():
    month_data = data[data['YearMonth'] == year_month].copy()
    
    if len(month_data) == 0:
        continue
    
    # Open = first price of the month
    open_price = month_data.iloc[0]['Close']
    
    # High = maximum daily_high of the month
    high_price = month_data['High'].max()
    
    # Low = minimum close price of the month (approximation)
    # Note: We don't have daily low in the dataset, so we use minimum close price
    # This is a reasonable approximation for monthly candles
    low_price = month_data['Close'].min()
    
    # As an additional check, if any high is lower than low, adjust
    # (This shouldn't happen, but handle edge cases)
    if high_price < low_price:
        low_price = month_data['High'].min()
    
    # Close = last price of the month
    close_price = month_data.iloc[-1]['Close']
    
    # Date = first day of the month (for plotting)
    month_date = month_data.iloc[0]['Date'].replace(day=1)
    
    # Block height = last block height of the month
    if month_data['BlockHeight'].notna().any():
        block_height = month_data['BlockHeight'].dropna().iloc[-1]
    else:
        block_height = None
    
    monthly_data.append({
        'Date': month_date,
        'Open': open_price,
        'High': high_price,
        'Low': low_price,
        'Close': close_price,
        'BlockHeight': block_height
    })

monthly_df = pd.DataFrame(monthly_data)
monthly_df = monthly_df.sort_values('Date').reset_index(drop=True)

print(f"Created {len(monthly_df)} monthly candles")
print(f"Date range: {monthly_df['Date'].min()} to {monthly_df['Date'].max()}")

# Get current month data (most recent)
current_month = monthly_df.iloc[-1]
current_open = current_month['Open']
current_high = current_month['High']
current_low = current_month['Low']
current_close = current_month['Close']
current_date = current_month['Date']
current_change = current_close - current_open
current_change_pct = (current_change / current_open) * 100 if current_open > 0 else 0

# Get block height
block_height = current_month['BlockHeight']
if pd.isna(block_height):
    block_height = get_block_height_from_mempool()
    if block_height is None:
        block_height = calculate_block_height_fallback(monthly_df['Date'].max())
        block_height = int(block_height)

# Calculate candle width based on the date range (once, outside the loop)
# Make candles take up roughly 70% of the average spacing between months
total_months = len(monthly_df)
if total_months > 1:
    total_days = (monthly_df['Date'].max() - monthly_df['Date'].min()).days
    avg_days_per_month = total_days / (total_months - 1) if total_months > 1 else 30
    # Use about 70% of the average spacing for candle width
    # Convert days to matplotlib date units (1 day = 1.0 in matplotlib)
    candle_width_num = avg_days_per_month * 0.7
else:
    # Default to ~20 days width
    candle_width_num = 20.0

# Create figure with dark background
fig, ax = plt.subplots(figsize=(20, 12))
fig.patch.set_facecolor('#1a1a1a')  # Dark grey background
ax.set_facecolor('#1a1a1a')

# Plot monthly candlesticks
for idx, row in monthly_df.iterrows():
    month_date = row['Date']
    open_price = row['Open']
    high_price = row['High']
    low_price = row['Low']
    close_price = row['Close']
    
    # Determine candle color (green if close >= open, red if close < open)
    is_green = close_price >= open_price
    candle_color = '#00FF00' if is_green else '#FF0000'  # Green or red
    
    # Convert date to numeric for matplotlib
    date_num = mdates.date2num(month_date)
    
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

# Format Y-axis (price scale)
y_min = 0
y_max = max(monthly_df['High'].max(), 120000)  # Up to $120k as shown in example
ax.set_ylim(y_min, y_max)

# Set Y-axis ticks
y_ticks = np.arange(0, y_max + 20000, 20000)
ax.set_yticks(y_ticks)

# Format Y-axis labels
def format_price_y(x, p):
    if x >= 1000:
        return f'${x/1000:.0f}k'
    else:
        return f'${x:.0f}'

ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_y))

# Format X-axis (years)
ax.set_xlim(monthly_df['Date'].min(), monthly_df['Date'].max())
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

# Price data (1M indicates monthly timeframe)
price_text = f"1M · O{current_open:.2f} H{current_high:.0f} L{current_low:.2f} C{current_close:.2f} {current_change:+.2f} ({current_change_pct:+.2f}%)"
fig.text(0.15, header_y, price_text,
         fontsize=11, color='lightgray', family='monospace',
         verticalalignment='top', horizontalalignment='left')

# Date and Block Height (right side)
# Use the most recent date from the data, not the month start date
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
output_path = script_dir / 'monthly_candles.png'
try:
    plt.savefig(output_path, dpi=150, facecolor='#1a1a1a', bbox_inches=None)
    print(f"Chart saved as '{output_path}'")
    print(f"Current Date: {latest_date.strftime('%Y-%m-%d')}")
    print(f"Current Month Close Price: ${current_close:,.2f}")
    print(f"Block Height: {int(block_height):,}")
except Exception as e:
    print(f"Error saving chart: {e}")
    import traceback
    traceback.print_exc()
    raise

plt.close(fig)

