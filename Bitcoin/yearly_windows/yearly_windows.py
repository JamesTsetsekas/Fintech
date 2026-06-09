#!/usr/bin/env python3
"""
Bitcoin Yearly Windows Chart

Creates a visualization showing Bitcoin price charts for different yearly windows (1Y, 2Y, 3Y, 4Y)

The chart shows:
- Four subplots (2x2 grid) showing 1Y, 2Y, 3Y, and 4Y price movements
- Each chart displays Open, High, Low, Close prices and percentage change
- Each chart has a vertical line marking the start of the period
- Each chart has a horizontal shaded rectangle (yearly window) showing the High-Low range
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Bitcoin genesis block date
GENESIS_DATE = datetime(2009, 1, 3)

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
data = pd.read_csv(dataset_path)

# Convert dates and prices
data['Date'] = pd.to_datetime(data['date'], format='%m/%d/%y')
data['Close'] = pd.to_numeric(data['price'], errors='coerce')
data['High'] = pd.to_numeric(data['daily_high'], errors='coerce')
# daily_price.csv doesn't have Open or Low, so we'll use price for both
# Open = previous day's close, Low = current day's price (min approximation)
data = data.sort_values('Date').reset_index(drop=True)
data['Open'] = data['Close'].shift(1).fillna(data['Close'])
data['Low'] = data['Close']  # Use price as approximation for Low
data = data.dropna(subset=['Date', 'Open', 'High', 'Low', 'Close'])
data = data.sort_values(by='Date').reset_index(drop=True)

# Get current date and price
current_date = data['Date'].max()
current_row = data[data['Date'] == current_date].iloc[0]
current_price = current_row['Close']

# Get block height from mempool.space API or fallback
block_height = get_block_height_from_mempool()
if block_height is None:
    block_height = calculate_block_height_fallback(current_date)

# Create figure with 2x2 subplots
fig = plt.figure(figsize=(20, 14))
fig.patch.set_facecolor('black')
gs = fig.add_gridspec(2, 2, hspace=0.25, wspace=0.25,
                      left=0.06, right=0.94, bottom=0.08, top=0.86)

axes = []
for i in range(4):
    ax = fig.add_subplot(gs[i // 2, i % 2])
    ax.set_facecolor('black')
    axes.append(ax)

# Define yearly windows to analyze
yearly_windows = [1, 2, 3, 4]

def get_yearly_data(data, years, end_date):
    """Get data for the specified number of years ending at end_date"""
    start_date = end_date - timedelta(days=years * 365.25)
    window_data = data[(data['Date'] >= start_date) & (data['Date'] <= end_date)].copy()
    return window_data

# Process each yearly window
for idx, years in enumerate(yearly_windows):
    ax = axes[idx]
    
    # Get data for this window
    window_data = get_yearly_data(data, years, current_date)
    
    if len(window_data) == 0:
        continue
    
    # Calculate statistics for this window
    window_open = window_data.iloc[0]['Open']
    window_high = window_data['High'].max()
    window_low = window_data['Low'].min()
    window_close = window_data.iloc[-1]['Close']
    window_change_pct = ((window_close - window_open) / window_open) * 100
    
    # Get the start date of the window
    window_start_date = window_data.iloc[0]['Date']
    
    # Plot price line
    ax.plot(window_data['Date'], window_data['Close'], 
            color='white', linewidth=2.5, zorder=3)
    
    # Add vertical line at the start of the period
    line_color = 'red' if window_change_pct < 0 else 'green'
    ax.axvline(x=window_start_date, color=line_color, 
               linestyle='-', linewidth=2, alpha=0.7, zorder=2)
    
    # Add horizontal shaded rectangle (yearly window) showing High-Low range
    # Use a semi-transparent rectangle
    rect_alpha = 0.2
    ax.axhspan(window_low, window_high, 
              xmin=0, xmax=1,
              color=line_color, alpha=rect_alpha, zorder=1)
    
    # Format the chart
    x_min = window_data['Date'].min()
    x_max = window_data['Date'].max()
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(window_low * 0.95, window_high * 1.15)
    
    # Remove spines
    for spine in ax.spines.values():
        spine.set_visible(False)
    
    # Set colors
    ax.tick_params(colors='white', labelsize=9)
    ax.set_facecolor('black')
    
    # Format x-axis
    if years == 1:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    elif years == 2:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    
    # Format y-axis (price)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Add grid
    ax.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.5)
    
    # Add label (1Y, 2Y, 3Y, 4Y)
    label_text = f"{years}Y"
    ax.text(0.02, 0.98, label_text, 
            transform=ax.transAxes,
            fontsize=16, fontweight='bold', color='white',
            verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7, 
                     edgecolor='white', linewidth=1))
    
    # Add data text (O, H, L, C and percentage change)
    data_text = f"O {window_open:.2f} H {window_high:.2f} L {window_low:.2f} C {window_close:.2f}"
    change_text = f"{window_change_pct:+.2f}%"
    
    # Position data text at bottom left
    ax.text(0.02, 0.02, data_text,
            transform=ax.transAxes,
            fontsize=9, color='white', family='monospace',
            verticalalignment='bottom', horizontalalignment='left')
    
    # Keep the window exact on the x-axis; place the return badge above the
    # data area instead of adding fake future-time padding.
    ax.text(0.985, 1.025, change_text,
            transform=ax.transAxes,
            fontsize=12, fontweight='bold', color='white',
            verticalalignment='bottom', horizontalalignment='right',
            clip_on=False,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7,
                     edgecolor=line_color, linewidth=1.5))

# Add header
header_y = 0.96
header_height = 0.06

# Bitcoin title/logo area (left side)
fig.text(0.06, header_y, 'bitcoin',
         fontsize=24, fontweight='bold', color='white',
         verticalalignment='top', horizontalalignment='left')

# Timeframe indicators (dots) next to bitcoin title
timeframe_x = 0.20
for idx, years in enumerate(yearly_windows):
    dot_x = timeframe_x + idx * 0.04
    window_data = get_yearly_data(data, years, current_date)
    if len(window_data) > 0:
        window_open = window_data.iloc[0]['Open']
        window_close = window_data.iloc[-1]['Close']
        window_change_pct = ((window_close - window_open) / window_open) * 100
        dot_color = 'red' if window_change_pct < 0 else 'green'
    else:
        dot_color = 'green'
    
    fig.text(dot_x, header_y - 0.015, '●',
             fontsize=14, color=dot_color,
             verticalalignment='top', horizontalalignment='center')
    
    fig.text(dot_x + 0.008, header_y - 0.01, f'{years}Y',
             fontsize=10, color='white',
             verticalalignment='top', horizontalalignment='left')

# Current market data (right side of header)
date_str = current_date.strftime('%Y-%m-%d %H:%M:%S')
fig.text(0.94, header_y, f'Date & Time (UTC): {date_str}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.94, header_y - 0.025, f'Block Height: {block_height:,}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.94, header_y - 0.050, f'Price (BTCUSD): ${current_price:,.2f}',
         fontsize=10, color='white', fontweight='bold',
         verticalalignment='top', horizontalalignment='right')


plt.savefig(script_dir / 'yearly_windows.png', dpi=300, facecolor='black', bbox_inches='tight')
print(f"Chart saved as '{script_dir / 'yearly_windows.png'}'")
print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
print(f"Current Price: ${current_price:,.2f}")
print(f"Block Height: {block_height:,}")

# plt.show()  # Commented out for automation
