#!/usr/bin/env python3
"""
Bitcoin Epoch Candles Chart

Creates a visualization showing Bitcoin's price history divided into halving epochs
with multipliers for each epoch period.

The chart shows:
- Bitcoin price on logarithmic scale
- Five epochs (halving cycles) marked with green shaded bands
- Multiplier for each epoch (price increase during that period)
- Halving dates marked with orange dots
"""

import pandas as pd
import matplotlib
# Use Agg backend for saving
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Bitcoin genesis block date
GENESIS_DATE = datetime(2009, 1, 3)

# Bitcoin halving dates (defining epochs)
HALVING_DATES = [
    datetime(2009, 1, 3),   # Genesis block (start of Epoch 1)
    datetime(2012, 11, 28), # First halving (end of Epoch 1, start of Epoch 2)
    datetime(2016, 7, 9),   # Second halving (end of Epoch 2, start of Epoch 3)
    datetime(2020, 5, 11),  # Third halving (end of Epoch 3, start of Epoch 4)
    datetime(2024, 4, 20),  # Fourth halving (end of Epoch 4, start of Epoch 5)
    datetime(2028, 4, 10),  # Fifth halving (end of Epoch 5, projected)
]

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
    days_since_genesis = (date - GENESIS_DATE).days
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
# daily_price.csv doesn't have Open or Low, so we'll use price for both
# Open = previous day's close, Low = current day's price (min approximation)
data = data.sort_values('Date').reset_index(drop=True)
data['Open'] = data['Close'].shift(1).fillna(data['Close'])
data['Low'] = data['Close']  # Use price as approximation for Low
data = data.dropna(subset=['Date', 'Open', 'High', 'Low', 'Close'])
data = data.sort_values(by='Date').reset_index(drop=True)
print(f"Data range: {data['Date'].min()} to {data['Date'].max()}")

# Get current date and price data
current_date = data['Date'].max()
current_row = data[data['Date'] == current_date].iloc[0]
current_open = current_row['Open']
current_high = current_row['High']
current_low = current_row['Low']
current_close = current_row['Close']
current_change = current_close - current_open
current_change_pct = (current_change / current_open) * 100

# Get previous day for comparison
prev_date = data[data['Date'] < current_date]['Date'].max()
if pd.notna(prev_date):
    prev_row = data[data['Date'] == prev_date].iloc[0]
    prev_close = prev_row['Close']
else:
    prev_close = current_open

# Get block height
block_height = get_block_height_from_mempool()
if block_height is None:
    block_height = calculate_block_height_fallback(current_date)

# Calculate multipliers for each epoch and get OHLC data
epoch_multipliers = []
epoch_data = []

for i in range(len(HALVING_DATES) - 1):
    epoch_start = HALVING_DATES[i]
    epoch_end = HALVING_DATES[i + 1]
    
    # Get price at start of epoch (Open)
    epoch_start_data = data[data['Date'] >= epoch_start]
    if len(epoch_start_data) > 0:
        epoch_open = epoch_start_data.iloc[0]['Open']
        epoch_start_price = epoch_start_data.iloc[0]['Close']
    else:
        # For very early dates, use first available price
        epoch_open = data.iloc[0]['Open'] if len(data) > 0 else 1.0
        epoch_start_price = data.iloc[0]['Close'] if len(data) > 0 else 1.0
    
    # Get price at end of epoch (Close)
    if epoch_end > current_date:
        epoch_close = current_close
        epoch_end_price = current_close
    else:
        epoch_end_data = data[data['Date'] <= epoch_end]
        if len(epoch_end_data) > 0:
            epoch_close = epoch_end_data.iloc[-1]['Close']
            epoch_end_price = epoch_close
        else:
            epoch_close = epoch_start_price
            epoch_end_price = epoch_start_price
    
    # Get High and Low for the entire epoch period
    epoch_period_data = data[(data['Date'] >= epoch_start) & (data['Date'] <= min(epoch_end, current_date))]
    if len(epoch_period_data) > 0:
        epoch_high = epoch_period_data['High'].max()
        epoch_low = epoch_period_data['Low'].min()
    else:
        epoch_high = max(epoch_open, epoch_close)
        epoch_low = min(epoch_open, epoch_close)
    
    # Calculate multiplier
    if epoch_start_price > 0:
        multiplier = epoch_end_price / epoch_start_price
        if multiplier == float('inf') or multiplier > 1000:
            multiplier_str = "X inf"
        else:
            multiplier_str = f"x{multiplier:.1f}"
    else:
        multiplier = float('inf')
        multiplier_str = "X inf"
    
    epoch_multipliers.append(multiplier_str)
    epoch_data.append({
        'start': epoch_start,
        'end': epoch_end,
        'open': epoch_open,
        'high': epoch_high,
        'low': epoch_low,
        'close': epoch_close,
        'start_price': epoch_start_price,
        'end_price': epoch_end_price,
        'multiplier': multiplier,
        'multiplier_str': multiplier_str
    })

# Create figure with black background
fig, ax = plt.subplots(figsize=(20, 12))
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# Set logarithmic scale for Y-axis
ax.set_yscale('log')

# Add green shaded bands and candlesticks for each epoch
for i, epoch in enumerate(epoch_data):
    start_date = epoch['start']
    end_date = min(epoch['end'], current_date) if epoch['end'] > current_date else epoch['end']
    
    # Get Y-axis limits for shading
    y_min = data['Close'].min() * 0.1
    y_max = data['Close'].max() * 10
    
    # Add shaded rectangle for epoch
    ax.axvspan(start_date, end_date, alpha=0.15, color='green', zorder=1)
    
    # Calculate candle position (middle of epoch for labels)
    mid_date = start_date + (end_date - start_date) / 2
    
    # Get OHLC values
    candle_open = epoch['open']
    candle_high = epoch['high']
    candle_low = epoch['low']
    candle_close = epoch['close']
    
    # Determine candle color (green if close > open, red if close < open)
    is_green = candle_close >= candle_open
    candle_color = '#00FF00' if is_green else '#FF0000'  # Green or red
    
    # Draw wicks (High and Low lines) - span full width with vertical lines at edges
    # Left edge wick
    ax.plot([start_date, start_date], [candle_low, candle_high], 
            color=candle_color, linewidth=2, zorder=3, alpha=0.4)
    # Right edge wick
    ax.plot([end_date, end_date], [candle_low, candle_high], 
            color=candle_color, linewidth=2, zorder=3, alpha=0.4)
    # Top wick line connecting edges
    ax.plot([start_date, end_date], [candle_high, candle_high], 
            color=candle_color, linewidth=1.5, zorder=3, alpha=0.3)
    # Bottom wick line connecting edges
    ax.plot([start_date, end_date], [candle_low, candle_low], 
            color=candle_color, linewidth=1.5, zorder=3, alpha=0.3)
    
    # Draw candle body (Open to Close rectangle) - spans full epoch width
    body_top = max(candle_open, candle_close)
    body_bottom = min(candle_open, candle_close)
    body_height = body_top - body_bottom
    if body_height == 0:
        body_height = body_top * 0.01  # Minimum height for flat candles
    
    # Create rectangle spanning full epoch period
    candle_x_left = mdates.date2num(start_date)
    candle_x_right = mdates.date2num(end_date)
    candle_width_num = candle_x_right - candle_x_left
    
    candle_body = Rectangle(
        (candle_x_left, body_bottom),
        candle_width_num,
        body_height,
        facecolor=candle_color,
        edgecolor=candle_color,
        linewidth=1.5,
        alpha=0.35,  # More transparent to see price chart behind
        zorder=3
    )
    ax.add_patch(candle_body)
    
    # Add multiplier label above the candle
    label_y = max(candle_high, y_max * 0.3)
    ax.text(mid_date, label_y, epoch['multiplier_str'],
            fontsize=16, fontweight='bold', color=candle_color,
            ha='center', va='bottom',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='black', 
                     edgecolor=candle_color, linewidth=2, alpha=0.8),
            zorder=10)

# Plot Bitcoin price line (orange) - higher zorder to be visible above transparent candles
ax.plot(data['Date'], data['Close'], color='#FF8800', linewidth=2.5, zorder=4, label='Bitcoin Price')

# Mark halving dates with orange dots
for halving_date in HALVING_DATES:
    if halving_date <= current_date:
        # Find closest price data point
        closest_data = data.iloc[(data['Date'] - halving_date).abs().argsort()[:1]]
        if len(closest_data) > 0:
            halving_price = closest_data.iloc[0]['Close']
            ax.plot(halving_date, halving_price, 'o', color='#FF8800', 
                   markersize=10, zorder=6)
            
            # Add date label
            date_str = halving_date.strftime('%b %d')
            ax.text(halving_date, halving_price * 0.3, date_str,
                   fontsize=10, color='#FF8800', ha='center', va='top',
                   rotation=0, zorder=7)

# Format Y-axis (logarithmic price scale)
price_ticks = [0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000]
ax.set_yticks(price_ticks)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: 
    f'${x*100:.0f}¢' if x < 1 else f'${x:,.0f}' if x < 1000 else f'${x/1000:.0f}k'))

# Format X-axis (years)
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.set_xlim(datetime(2010, 1, 1), datetime(2028, 12, 31))

# Set Y-axis limits
ax.set_ylim(0.0001, 200000)

# Remove spines
for spine in ax.spines.values():
    spine.set_visible(False)

# Set colors
ax.tick_params(colors='white', labelsize=10)
ax.set_xlabel('Year', color='white', fontsize=12)
ax.set_ylabel('Price (USD)', color='white', fontsize=12)

# Add grid
ax.grid(True, which="major", linestyle='--', alpha=0.2, color='white', linewidth=0.5)
ax.grid(True, which="minor", linestyle=':', alpha=0.1, color='white', linewidth=0.3)

# --- HEADER SECTION ---
header_y = 0.96
header_height = 0.06

# Bitcoin logo/title (left side)
fig.text(0.02, header_y, 'bitcoin',
         fontsize=24, fontweight='bold', color='white',
         verticalalignment='top', horizontalalignment='left')

# Price data (next to bitcoin title)
price_text = f"1E · O{current_open:.2f} H{current_high:.0f} L{current_low:.0f} C{current_close:.2f} {current_change:+.2f} ({current_change_pct:+.2f}%)"
fig.text(0.15, header_y, price_text,
         fontsize=11, color='white', family='monospace',
         verticalalignment='top', horizontalalignment='left')

# Date and Block Height (right side)
date_str = current_date.strftime('%b %d, %Y %H:%M (UTC)')
fig.text(0.98, header_y, date_str,
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.98, header_y - 0.025, f'Block Height: {block_height:,}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='right')

# --- FOOTER SECTION ---
# Footer removed - no branding

# Adjust layout
plt.tight_layout(rect=[0, 0, 1, 0.96])

# Save the chart
output_path = script_dir / 'epoch_candles.png'
try:
    # Use lower DPI and no tight bbox to avoid image size limits
    # Max dimensions: 65536 pixels (2^16) - using 150 DPI with 20x12 figsize gives 3000x1800 which is safe
    # tight_layout already handles spacing, so we don't need bbox_inches='tight'
    plt.savefig(output_path, dpi=150, facecolor='black', bbox_inches=None)
    print(f"Chart saved as '{output_path}'")
    print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
    print(f"Current Price: ${current_close:,.2f}")
    print(f"Block Height: {block_height:,}")
    print("\nEpoch Multipliers:")
    for i, epoch in enumerate(epoch_data, 1):
        print(f"  Epoch {i}: {epoch['multiplier_str']} ({epoch['start'].strftime('%Y-%m-%d')} to {epoch['end'].strftime('%Y-%m-%d')})")
except Exception as e:
    print(f"Error saving chart: {e}")
    import traceback
    traceback.print_exc()
    raise

plt.close(fig)  # Explicitly close the figure to free memory
# plt.show()  # Commented out for automation

