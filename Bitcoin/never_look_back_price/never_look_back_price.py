#!/usr/bin/env python3
"""
Never Look Back Price Chart

Creates a visualization showing Bitcoin's price history and the "Never Look Back Price",
which is the highest price Bitcoin has reached and never subsequently fallen below.
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import requests

# Genesis block date (January 3, 2009)
genesis_date = datetime(2009, 1, 3)

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
    days_since_genesis = (date - genesis_date).days
    # Approximately 144 blocks per day (1 block every 10 minutes)
    blocks_per_day = 144
    return int(days_since_genesis * blocks_per_day)

# Load data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'
data = pd.read_csv(dataset_path)

# Convert dates and prices
data['Date'] = pd.to_datetime(data['date'])
data['Close'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Close'])

# Sort chronologically (oldest to newest)
data = data.sort_values(by='Date').reset_index(drop=True)

# Calculate "Never Look Back Price" - the highest price that, once reached, 
# Bitcoin never falls below again (looking forward from each point)
# This creates a step function that only increases
# 
# Algorithm: For each point in time i, the NLB is the highest price reached up to time i
# such that from the time that price was reached until the end of the dataset, 
# the price never falls below that level.
#
# Optimized: Pre-compute minimum prices ahead for efficiency

prices = data['Close'].values
n = len(prices)

# Pre-compute minimum price from each index to the end (for efficiency)
min_ahead = np.zeros(n)
min_ahead[n-1] = prices[n-1]
for i in range(n-2, -1, -1):
    min_ahead[i] = min(min_ahead[i+1], prices[i])

# Now compute NLB for each point
nlb_prices = np.zeros(n)

for i in range(n):
    best_nlb = 0.0
    
    # Check all prices from start to current point
    for j in range(i + 1):
        candidate_price = prices[j]
        
        # Check if from point j forward, price never falls below candidate_price
        if j < n - 1:
            # Use pre-computed minimum ahead
            if min_ahead[j] >= candidate_price:
                best_nlb = max(best_nlb, candidate_price)
        else:
            # j is the last data point, so candidate is valid
            best_nlb = max(best_nlb, candidate_price)
    
    nlb_prices[i] = best_nlb

data['Never_Look_Back_Price'] = nlb_prices

# Get current values
current_date = data['Date'].max()
current_nlb_price = data[data['Date'] == current_date]['Never_Look_Back_Price'].iloc[0]
current_price = data[data['Date'] == current_date]['Close'].iloc[0]

# Get block height from mempool.space API or fallback
current_block_height = get_block_height_from_mempool()
if current_block_height is None:
    current_block_height = calculate_block_height_fallback(current_date)

# Create figure with dark grey background
fig = plt.figure(figsize=(20, 12))
fig.patch.set_facecolor('#2a2a2a')  # Dark grey background

# Main chart area
ax = fig.add_subplot(111)
ax.set_facecolor('#2a2a2a')

# Plot Bitcoin price (grey line)
ax.plot(data['Date'], data['Close'], color='#888888', linewidth=2, zorder=2, label='Bitcoin Price')

# Plot Never Look Back Price (orange step function)
# Use step='post' to create a step function that steps up after each new high
ax.plot(data['Date'], data['Never_Look_Back_Price'], color='#FF8C00', linewidth=2.5, zorder=3, 
        label='Never Look Back Price', drawstyle='steps-post')

# Format Y-axis
ax.set_ylabel('Price (USD)', color='white', fontsize=12, fontweight='bold')
ax.tick_params(axis='y', colors='white', labelsize=10)
ax.set_ylim(0, 120000)  # Based on image showing up to $120k
y_ticks = np.arange(0, 120001, 20000)
ax.set_yticks(y_ticks)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x/1000:.0f}k' if x >= 1000 else f'${x:.0f}'))

# Format X-axis
ax.set_xlabel('Year', color='white', fontsize=11)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.xaxis.set_minor_locator(mdates.YearLocator())
ax.set_xlim(data['Date'].min(), data['Date'].max())
ax.tick_params(axis='x', colors='white', labelsize=10)
plt.setp(ax.xaxis.get_majorticklabels(), rotation=-5)  # Rotate labels slightly counter-clockwise

# Grid
ax.grid(True, which="major", linestyle='-', alpha=0.2, color='#666666', linewidth=0.8)
ax.grid(True, which="minor", linestyle=':', alpha=0.1, color='#666666', linewidth=0.5)

# Remove spines
for spine in ax.spines.values():
    spine.set_visible(False)

# Title
title_y = 0.98
ax.text(0.5, title_y, 'Never Look Back Price', 
        ha='center', va='top', transform=ax.transAxes,
        fontsize=24, fontweight='bold', color='white')

# Current Never Look Back Price value (below title)
ax.text(0.5, title_y - 0.06, f'${current_nlb_price:,.2f}', 
        ha='center', va='top', transform=ax.transAxes,
        fontsize=18, fontweight='bold', color='#FF8C00')

# Bitcoin logo/text (top left)
ax.text(0.02, title_y, 'bitcoin', 
        ha='left', va='top', transform=ax.transAxes,
        fontsize=14, fontweight='bold', color='#FF8C00')

# Date and Block Height (top right)
# Format date similar to image (daily data, so use 00:00 as default time)
current_date_str = current_date.strftime('%b %d, %Y 00:00 (UTC)')
ax.text(0.98, title_y, current_date_str, 
        ha='right', va='top', transform=ax.transAxes,
        fontsize=10, color='#888888')
ax.text(0.98, title_y - 0.03, f'Block Height: {current_block_height:,}', 
        ha='right', va='top', transform=ax.transAxes,
        fontsize=10, color='#888888')

# Adjust layout to make room for title
plt.subplots_adjust(left=0.08, right=0.95, top=0.90, bottom=0.08)

# Save the chart
output_path = script_dir / 'never_look_back_price.png'
plt.savefig(output_path, dpi=300, facecolor='#2a2a2a', bbox_inches='tight')
print(f"Chart saved as '{output_path}'")
print(f"Current Never Look Back Price: ${current_nlb_price:,.2f}")
print(f"Current Price: ${current_price:,.2f}")
print(f"Date: {current_date_str}")
print(f"Block Height: {current_block_height:,}")

# plt.show()  # Display the chart (commented out for automation)

