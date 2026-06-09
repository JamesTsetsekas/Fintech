#!/usr/bin/env python3
"""
Bitcoin Price Distribution Chart

Creates a visualization showing Bitcoin's historical price trend with halving events
and a distribution of daily closing prices across various price ranges.
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

# Genesis block date
GENESIS_DATE = datetime(2009, 1, 3)

# Halving dates
HALVINGS = [
    {'block': 210000, 'date': datetime(2012, 11, 28), 'label': '1st Halving'},
    {'block': 420000, 'date': datetime(2016, 7, 9), 'label': '2nd Halving'},
    {'block': 630000, 'date': datetime(2020, 5, 11), 'label': '3rd Halving'},
    {'block': 840000, 'date': datetime(2024, 4, 20), 'label': '4th Halving'},
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
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Price'])
data = data.sort_values('Date').reset_index(drop=True)

# Get block height column if available
if 'block_height' in data.columns:
    data['BlockHeight'] = pd.to_numeric(data['block_height'], errors='coerce')
else:
    data['BlockHeight'] = None

# Get latest data point
latest_data = data.iloc[-1]
current_price = latest_data['Price']
current_date = latest_data['Date']
current_block_height = latest_data['BlockHeight']

# Calculate network age
network_age_days = (current_date - GENESIS_DATE).days

# Get block height if not available
if pd.isna(current_block_height):
    current_block_height = get_block_height_from_mempool()
    if current_block_height is None:
        current_block_height = calculate_block_height_fallback(current_date)
        current_block_height = int(current_block_height)

# Define price ranges for distribution
price_ranges = [
    {'min': 10000000, 'max': 100000000, 'label': '$10M - $100M'},
    {'min': 1000000, 'max': 10000000, 'label': '$1M - $10M'},
    {'min': 100000, 'max': 1000000, 'label': '$100k - $1M'},
    {'min': 10000, 'max': 100000, 'label': '$10k - $100k'},
    {'min': 1000, 'max': 10000, 'label': '$1k - $10k'},
    {'min': 100, 'max': 1000, 'label': '$100 - $1k'},
    {'min': 10, 'max': 100, 'label': '$10 - $100'},
    {'min': 1, 'max': 10, 'label': '$1 - $10'},
    {'min': 0.10, 'max': 1, 'label': '10¢ - $1'},
    {'min': 0.01, 'max': 0.10, 'label': '1¢ - 10¢'},
    {'min': 0.001, 'max': 0.01, 'label': '0.1¢ - 1¢'},
    {'min': 0.0001, 'max': 0.001, 'label': '0.01¢ - 0.1¢'},
]

# Calculate distribution
distribution_counts = {}
for price_range in price_ranges:
    count = len(data[(data['Price'] >= price_range['min']) & (data['Price'] < price_range['max'])])
    distribution_counts[price_range['label']] = count

# Count "Not Valued" (price == 0)
not_valued_count = len(data[data['Price'] == 0])
distribution_counts['Not Valued'] = not_valued_count

# Create figure with dark background
fig = plt.figure(figsize=(20, 12))
fig.patch.set_facecolor('#000000')  # Black background

# Create axes using add_axes for precise positioning
# Main price chart (left, 70% width)
ax_main = fig.add_axes([0.05, 0.12, 0.65, 0.78])  # [left, bottom, width, height]
ax_main.set_facecolor('#000000')

# Distribution chart (right, 30% width)
ax_dist = fig.add_axes([0.72, 0.12, 0.26, 0.78])
ax_dist.set_facecolor('#000000')

# --- HEADER SECTION ---
header_y = 0.95

# Bitcoin logo/title (left side)
fig.text(0.05, header_y, 'bitcoin',
         fontsize=24, fontweight='bold', color='#ff8c00',
         verticalalignment='top', horizontalalignment='left')

# Date and Block Height (below logo)
date_str = current_date.strftime('%b %d, %Y')
fig.text(0.05, header_y - 0.04, date_str,
         fontsize=10, color='lightgray',
         verticalalignment='top', horizontalalignment='left')
fig.text(0.05, header_y - 0.065, f'Block Height: {int(current_block_height):,}',
         fontsize=10, color='lightgray',
         verticalalignment='top', horizontalalignment='left')

# Price (center)
price_text = f"Price (BTCUSD)"
fig.text(0.38, header_y, price_text,
         fontsize=14, color='lightgray', fontweight='bold',
         verticalalignment='top', horizontalalignment='center')
fig.text(0.38, header_y - 0.04, f"${current_price:,.2f}",
         fontsize=16, color='#ff8c00', fontweight='bold',
         verticalalignment='top', horizontalalignment='center')

# Network Age (right)
fig.text(0.95, header_y, f"Network Age",
         fontsize=12, color='lightgray', fontweight='bold',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.95, header_y - 0.04, f"{network_age_days:,} Days",
         fontsize=14, color='#ff8c00',
         verticalalignment='top', horizontalalignment='right')

# --- MAIN PRICE CHART ---
# Filter out zero prices for the main chart
price_data = data[data['Price'] > 0].copy()

# Plot price line
ax_main.plot(price_data['Date'], price_data['Price'], 
             color='#ff8c00', linewidth=1.5, zorder=2)

# Add halving lines
dates_min = price_data['Date'].min()
dates_max = price_data['Date'].max()
price_max = price_data['Price'].max()

for halving in HALVINGS:
    halving_date = pd.Timestamp(halving['date'])
    if dates_min <= halving_date <= dates_max:
        ax_main.axvline(x=halving['date'], color='#FFFFFF', linestyle='--', 
                        linewidth=1, alpha=0.6, zorder=1)
        # Add label
        y_pos = price_max * 0.95
        ax_main.text(halving['date'], y_pos, halving['label'], 
                     rotation=90, fontsize=9, color='#FFFFFF', alpha=0.8,
                     verticalalignment='top', horizontalalignment='right')

# Format Y-axis (price scale) - LOGARITHMIC SCALE
y_min = 0.01
y_max = max(price_data['Price'].max(), 100000) * 1.1
ax_main.set_ylim(y_min, y_max)
ax_main.set_yscale('log')

# Set Y-axis ticks for logarithmic scale
y_ticks = [0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000]
y_ticks = [t for t in y_ticks if y_min <= t <= y_max]
ax_main.set_yticks(y_ticks)

# Format Y-axis labels
def format_price_y(x, p):
    if x >= 1000000:
        return f'${x/1000000:.1f}M'
    elif x >= 1000:
        return f'${x/1000:.0f}k'
    elif x >= 1:
        return f'${x:.0f}'
    elif x >= 0.01:
        return f'${x:.2f}'
    else:
        return f'{x*100:.1f}¢'

ax_main.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_y))

# Format X-axis (dates)
ax_main.set_xlim(dates_min, dates_max)
ax_main.xaxis.set_major_locator(mdates.YearLocator())
ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax_main.xaxis.set_minor_locator(mdates.YearLocator())

# Set colors
ax_main.tick_params(colors='lightgray', labelsize=9)
ax_main.set_ylabel('Price (USD)', color='lightgray', fontsize=11)
ax_main.set_xlabel('Date', color='lightgray', fontsize=11)

# Add grid
ax_main.grid(True, which="major", linestyle='-', alpha=0.1, color='gray', linewidth=0.5)
ax_main.grid(True, which="minor", linestyle='--', alpha=0.05, color='gray', linewidth=0.3)

# Remove top and right spines
ax_main.spines['top'].set_visible(False)
ax_main.spines['right'].set_visible(False)
ax_main.spines['left'].set_color('lightgray')
ax_main.spines['bottom'].set_color('lightgray')

# --- DISTRIBUTION CHART ---
# Prepare data for horizontal bar chart
# Reverse order to show highest prices at top
range_labels = [pr['label'] for pr in reversed(price_ranges)] + ['Not Valued']
range_counts = [distribution_counts[label] for label in range_labels]

# Create horizontal bar chart
y_positions = np.arange(len(range_labels))
bars = ax_dist.barh(y_positions, range_counts, color='#ff8c00', height=0.6, zorder=2)

# Add value labels at the end of bars
for i, (bar, count) in enumerate(zip(bars, range_counts)):
    if count > 0:
        ax_dist.text(count, i, f' {count:,}', 
                     va='center', ha='left', color='#ff8c00', 
                     fontsize=9, fontweight='bold')

# Set y-axis labels
ax_dist.set_yticks(y_positions)
ax_dist.set_yticklabels(range_labels, fontsize=9, color='lightgray')

# Format x-axis
ax_dist.set_xlabel('Number of Daily Closes', color='lightgray', fontsize=10)
ax_dist.tick_params(colors='lightgray', labelsize=9)
ax_dist.set_facecolor('#000000')

# Add grid
ax_dist.grid(True, axis='x', linestyle='-', alpha=0.1, color='gray', linewidth=0.5, zorder=0)

# Remove spines
for spine in ax_dist.spines.values():
    spine.set_visible(False)

# Set title
ax_dist.set_title('Bitcoin Price Distribution\n(Daily closes in each price range)', 
                  color='lightgray', fontsize=11, fontweight='bold', pad=10)

# Adjust x-axis to fit labels
max_count = max(range_counts) if range_counts else 1
ax_dist.set_xlim(0, max_count * 1.15)

# Save the chart
output_path = script_dir / 'price_distribution.png'
try:
    plt.savefig(output_path, dpi=150, facecolor='#000000', bbox_inches=None)
    print(f"Chart saved as '{output_path}'")
    print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
    print(f"Current Price: ${current_price:,.2f}")
    print(f"Block Height: {int(current_block_height):,}")
    print(f"Network Age: {network_age_days:,} days")
    print("\nPrice Distribution:")
    for label in range_labels:
        count = distribution_counts[label]
        if count > 0:
            print(f"  {label}: {count:,} days")
except Exception as e:
    print(f"Error saving chart: {e}")
    import traceback
    traceback.print_exc()
    raise

plt.close(fig)

