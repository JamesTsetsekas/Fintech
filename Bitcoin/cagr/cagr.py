#!/usr/bin/env python3
"""
Compound Annual Growth Rate (CAGR) Chart

Creates a visualization showing Bitcoin's CAGR over different time periods

The chart shows:
- Left: Bitcoin Price History with CAGR lines overlaid
- Right: CAGR Over Network Age showing how different CAGRs evolve over time
"""

import pandas as pd
import matplotlib
# Use Agg backend for saving, will switch to interactive for display if available
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime
from pathlib import Path
import os
import sys
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
data['Date'] = pd.to_datetime(data['date'])
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Price'])

# Sort chronologically (oldest to newest)
data = data.sort_values(by='Date').reset_index(drop=True)

# Validate data
if len(data) == 0:
    raise ValueError("No valid data found in daily_price.csv")

# Get current values
current_date = data['Date'].max()
current_price_data = data[data['Date'] == current_date]
if len(current_price_data) == 0:
    raise ValueError("No current price data found")
current_price = current_price_data['Price'].iloc[0]

if current_price <= 0:
    raise ValueError(f"Invalid current price: {current_price}")
current_year = current_date.year
network_age_years = (current_date - GENESIS_DATE).days / 365.25

# Calculate CAGR for different periods
def calculate_cagr(start_price, end_price, years):
    """Calculate Compound Annual Growth Rate"""
    if start_price <= 0 or years <= 0:
        return np.nan
    return ((end_price / start_price) ** (1 / years) - 1) * 100

# Calculate CAGRs for current date (4, 6, 8, 10, 12 years)
cagr_periods = [4, 6, 8, 10, 12]
current_cagrs = {}

for period in cagr_periods:
    # Find price N years ago
    period_date = current_date - pd.Timedelta(days=period * 365.25)
    period_data = data[data['Date'] <= period_date]
    
    if len(period_data) > 0:
        period_price = period_data.iloc[-1]['Price']
        cagr = calculate_cagr(period_price, current_price, period)
        current_cagrs[period] = cagr
    else:
        current_cagrs[period] = np.nan

# Calculate historical CAGRs for the right chart
# For each date, calculate CAGRs for different periods
historical_cagrs = {period: [] for period in cagr_periods}
historical_network_ages = []
historical_dates = []

for idx, row in data.iterrows():
    date = row['Date']
    price = row['Price']
    network_age = (date - GENESIS_DATE).days / 365.25
    
    # Only calculate if network age is at least 5 years (as shown in the image)
    if network_age < 5:
        continue
    
    historical_network_ages.append(network_age)
    historical_dates.append(date)
    
    for period in cagr_periods:
        # Find price N years ago
        period_date = date - pd.Timedelta(days=period * 365.25)
        period_data = data[data['Date'] <= period_date]
        
        if len(period_data) > 0:
            period_price = period_data.iloc[-1]['Price']
            cagr = calculate_cagr(period_price, price, period)
            historical_cagrs[period].append(cagr)
        else:
            historical_cagrs[period].append(np.nan)

# Create figure with black background
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 12))
fig.patch.set_facecolor('black')

# Left chart: Price with CAGR lines
# Right chart: CAGR over network age
ax1.set_facecolor('black')
ax2.set_facecolor('black')

# --- LEFT CHART: Bitcoin Price History with CAGR Lines ---
ax1.set_yscale('log')
ax1.plot(data['Date'], data['Price'], color='white', linewidth=2, zorder=10, label='Bitcoin Price')

# Add CAGR lines (straight lines from past points to current)
colors_cagr = {
    4: '#FF4444',   # Red
    6: '#4444FF',   # Blue
    8: '#FFFF44',   # Yellow
    10: '#44FF44',  # Green
    12: '#FF44FF'   # Pink/Purple
}

for period in cagr_periods:
    if period in current_cagrs and not np.isnan(current_cagrs[period]):
        # Find price N years ago
        period_date = current_date - pd.Timedelta(days=period * 365.25)
        period_data = data[data['Date'] <= period_date]
        
        if len(period_data) > 0:
            period_price = period_data.iloc[-1]['Price']
            period_date_actual = period_data.iloc[-1]['Date']
            
            # Draw straight line from past point to current
            ax1.plot([period_date_actual, current_date], 
                    [period_price, current_price],
                    color=colors_cagr[period], linewidth=2, alpha=0.7, zorder=5)

# Format left chart
ax1.set_xlabel('Year', color='white', fontsize=12)
ax1.set_ylabel('Price (USD)', color='white', fontsize=12)
ax1.tick_params(axis='both', colors='white', labelsize=10)
ax1.grid(True, which="major", linestyle='--', alpha=0.2, color='white', linewidth=0.5)
ax1.grid(True, which="minor", linestyle=':', alpha=0.1, color='white', linewidth=0.3)

# Format Y-axis with log scale
ax1.set_ylim(data['Price'].min() * 0.5, data['Price'].max() * 2)
price_ticks = [1000, 10000, 100000]
ax1.set_yticks(price_ticks)
ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x/1000:.0f}k' if x >= 1000 else f'${x:.0f}'))

# Format X-axis
ax1.xaxis.set_major_locator(mdates.YearLocator(2))
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.set_xlim(data['Date'].min(), data['Date'].max())

# Remove spines
for spine in ax1.spines.values():
    spine.set_visible(False)

# --- RIGHT CHART: CAGR Over Network Age ---
ax2.set_yscale('log')
ax2.set_xlabel('Network Age (Years)', color='white', fontsize=12)
ax2.set_ylabel('CAGR', color='white', fontsize=12)
ax2.tick_params(axis='both', colors='white', labelsize=10)
ax2.grid(True, which="major", linestyle='--', alpha=0.2, color='white', linewidth=0.5)
ax2.grid(True, which="minor", linestyle=':', alpha=0.1, color='white', linewidth=0.3)

# Plot CAGR lines for each period
for period in cagr_periods:
    if len(historical_cagrs[period]) > 0:
        # Filter out NaN, zero, and negative values (log scale requires positive values)
        valid_indices = [i for i, val in enumerate(historical_cagrs[period]) 
                        if not np.isnan(val) and val > 0]
        valid_ages = [historical_network_ages[i] for i in valid_indices]
        valid_cagrs = [historical_cagrs[period][i] for i in valid_indices]
        
        if len(valid_cagrs) > 0:
            ax2.plot(valid_ages, valid_cagrs, 
                    color=colors_cagr[period], linewidth=2, 
                    label=f'{period}-Year CAGR', zorder=5)

# Format Y-axis with log scale for CAGR
# Ensure all CAGR values are positive for log scale
all_cagr_values = []
for period in cagr_periods:
    all_cagr_values.extend([v for v in historical_cagrs[period] if not np.isnan(v) and v > 0])

if len(all_cagr_values) > 0:
    min_cagr = max(5, min(all_cagr_values) * 0.8)  # At least 5%
    max_cagr = max(5000, max(all_cagr_values) * 1.2)  # At least 5000%
else:
    min_cagr = 5
    max_cagr = 5000

ax2.set_ylim(min_cagr, max_cagr)
cagr_ticks = [10, 20, 40, 100, 200, 400, 1000, 2000, 4000]
# Filter ticks to be within range
cagr_ticks = [t for t in cagr_ticks if min_cagr <= t <= max_cagr]
if len(cagr_ticks) > 0:
    ax2.set_yticks(cagr_ticks)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{x:.0f}%'))

# Format X-axis
ax2.set_xlim(5, 17)
ax2.xaxis.set_major_locator(ticker.MultipleLocator(2))
ax2.xaxis.set_minor_locator(ticker.MultipleLocator(1))

# Remove spines
for spine in ax2.spines.values():
    spine.set_visible(False)

# --- HEADER SECTION ---
header_y = 0.95
header_bg = Rectangle((0, header_y - 0.08), 1, 0.08, 
                     transform=fig.transFigure, 
                     facecolor='black', alpha=0.8, 
                     edgecolor='#333333', linewidth=1, zorder=2)
fig.patches.append(header_bg)


# Date and Block Height (from mempool.space API or fallback)
block_height = get_block_height_from_mempool()
if block_height is None:
    block_height = calculate_block_height_fallback(current_date)
fig.text(0.02, header_y - 0.05, f'Date: {current_date.strftime("%b %d, %Y")}', 
        ha='left', va='top', transform=fig.transFigure,
        fontsize=10, color='#888888')
fig.text(0.02, header_y - 0.07, f'Block Height: {block_height:,}', 
        ha='left', va='top', transform=fig.transFigure,
        fontsize=10, color='#888888')

# Main title
fig.text(0.5, header_y - 0.02, 'Compound Annual Growth Rate (CAGR)', 
        ha='center', va='top', transform=fig.transFigure,
        fontsize=20, fontweight='bold', color='white')

# Current price and CAGRs (right side of header)
stats_x = 0.98
stats_y = header_y - 0.02
fig.text(stats_x, stats_y, f'Price (BTCUSD) ${current_price:,.2f}', 
        ha='right', va='top', transform=fig.transFigure,
        fontsize=11, color='white', fontweight='bold')

y_offset = 0.025
for period in cagr_periods:
    if period in current_cagrs and not np.isnan(current_cagrs[period]):
        # Add colored box to the left of the text
        box_size = 0.012
        box_x = stats_x - 0.12  # Position box to the left of text
        box_y = stats_y - y_offset - 0.006  # Center vertically with text
        
        color_box = Rectangle(
            (box_x, box_y), box_size, box_size,
            transform=fig.transFigure,
            facecolor=colors_cagr[period],
            edgecolor='white',
            linewidth=0.5,
            zorder=10
        )
        fig.patches.append(color_box)
        
        # Add the CAGR text (unchanged)
        fig.text(stats_x, stats_y - y_offset, f'{period}-Year CAGR {current_cagrs[period]:.1f}%', 
                ha='right', va='top', transform=fig.transFigure,
                fontsize=10, color='white')
        y_offset += 0.025


# Adjust layout
try:
    plt.tight_layout(rect=[0, 0, 1, 0.92])
except Exception as e:
    print(f"Warning: Layout adjustment issue: {e}")

# Save the chart first (before any display attempts)
output_path = script_dir / 'cagr.png'
try:
    plt.savefig(output_path, dpi=300, facecolor='black', bbox_inches='tight')
    print(f"Chart saved as '{output_path}'")
    print(f"Current Price: ${current_price:,.2f}")
    for period in cagr_periods:
        if period in current_cagrs and not np.isnan(current_cagrs[period]):
            print(f"{period}-Year CAGR: {current_cagrs[period]:.1f}%")
except Exception as e:
    print(f"Error saving chart: {e}")
    raise

# Try to display the chart (may fail in headless environments)
try:
    # Check if we can display (not in headless environment)
    if hasattr(sys, 'ps1') or 'DISPLAY' in os.environ or sys.platform == 'darwin':
        plt.show()
    else:
        print("Note: Running in headless environment. Chart saved but not displayed.")
except Exception as e:
    print(f"Note: Could not display chart ({e}). Image saved successfully.")

