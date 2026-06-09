#!/usr/bin/env python3
"""
Unit of Account: BTC/USD Chart

Creates a dual chart visualization showing:
- Left: Price of 1 USD in terms of Bitcoin (in satoshis)
- Right: Price of 1 BTC in terms of US Dollar
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import requests

# Load data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'
data = pd.read_csv(dataset_path)

# Convert dates and prices
data['Date'] = pd.to_datetime(data['date'], format='%m/%d/%y')
data['Close'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Close'])
data = data[data['Close'] > 0].copy()
data = data.sort_values(by='Date')

# Calculate price of 1 USD in terms of Bitcoin (in satoshis)
# 1 BTC = 100,000,000 sats
# If 1 BTC = $X, then 1 USD = 1/X BTC = 100,000,000/X sats
data['USD_in_Sats'] = (100_000_000 / data['Close']).clip(lower=0.01)  # Avoid division issues

# Get current values (most recent data point)
current_date = data['Date'].max()
current_price_btc_usd = data[data['Date'] == current_date]['Close'].iloc[0]
current_price_usd_btc_sats = data[data['Date'] == current_date]['USD_in_Sats'].iloc[0]

# Genesis block date
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

# Get block height from mempool.space API or fallback
current_block_height = get_block_height_from_mempool()
if current_block_height is None:
    current_block_height = calculate_block_height_fallback(current_date)

# Format current date (e.g., "JAN 2, 2026")
current_date_str = current_date.strftime('%b %d, %Y').upper()

# Create figure with dedicated header rows so metrics do not overlap price lines.
fig = plt.figure(figsize=(20, 10))
fig.patch.set_facecolor('black')
gs = fig.add_gridspec(2, 2, height_ratios=[0.22, 1], hspace=0.02, wspace=0.16)

header1 = fig.add_subplot(gs[0, 0])
header2 = fig.add_subplot(gs[0, 1])
for header_ax in (header1, header2):
    header_ax.set_facecolor('black')
    header_ax.axis('off')

# Left chart: Price of 1 USD in terms of Bitcoin
ax1 = fig.add_subplot(gs[1, 0])
ax1.set_facecolor('black')

# Plot the data
ax1.plot(data['Date'], data['USD_in_Sats'], color='#FF8C00', linewidth=2, label='USDBTC LOG LINEAR')

# Set log scale on y-axis
ax1.set_yscale('log')
sats_floor = 1
sats_ceiling = max(100_000_000, data['USD_in_Sats'].max() * 1.2)
ax1.set_ylim(sats_floor, sats_ceiling)
ax1.fill_between(data['Date'], sats_floor, data['USD_in_Sats'], alpha=0.3, color='#666666')

# Format y-axis with satoshi labels. Keep extra resolution below 10k sats,
# where current BTC/USD prices make the chart most useful day-to-day.
sats_ticks = [
    1,
    2,
    5,
    10,
    20,
    50,
    100,
    200,
    500,
    1_000,
    2_000,
    5_000,
    10_000,
    100_000,
    1_000_000,
    10_000_000,
    100_000_000,
]
sats_labels = [
    '1 sat',
    '2 sats',
    '5 sats',
    '10 sats',
    '20 sats',
    '50 sats',
    '100 sats',
    '200 sats',
    '500 sats',
    '1k sats',
    '2k sats',
    '5k sats',
    '10k sats',
    '100k sats',
    '1M sats',
    '10M sats',
    '1 BTC',
]
ax1.set_yticks(sats_ticks)
ax1.set_yticklabels(sats_labels, color='#FF8C00', fontsize=9)
ax1.yaxis.set_label_position('right')
ax1.yaxis.tick_right()

# Format x-axis with years
ax1.xaxis.set_major_locator(mdates.YearLocator(2))  # Every 2 years
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.set_xlim(data['Date'].min(), data['Date'].max())
ax1.tick_params(axis='x', colors='white', labelsize=10)
ax1.tick_params(axis='y', colors='#FF8C00')

# Remove spines
for spine in ax1.spines.values():
    spine.set_visible(False)

# Grid
ax1.grid(True, which="both", linestyle='--', alpha=0.1, color='white')

# Header: title, current value, and context
current_sats_display = f"{int(current_price_usd_btc_sats):,} sats"
header1.text(0.5, 0.92, 'Price of 1 USD in terms of bitcoin',
             ha='center', va='top', transform=header1.transAxes,
             fontsize=16, fontweight='bold', color='white')
header1.text(0.5, 0.58, current_sats_display,
             ha='center', va='top', transform=header1.transAxes,
             fontsize=36, fontweight='bold', color='#FF8C00')
header1.text(0.5, 0.18, f'1 BTC = 100,000,000 sats   |   BLOCK HEIGHT: {current_block_height:,}',
             ha='center', va='top', transform=header1.transAxes,
             fontsize=10, color='white')

# Right chart: Price of 1 BTC in terms of US Dollar
ax2 = fig.add_subplot(gs[1, 1])
ax2.set_facecolor('black')

# Plot the data
ax2.plot(data['Date'], data['Close'], color='#00FF00', linewidth=2, label='BTCUSD LOG LINEAR')

# Set log scale on y-axis
ax2.set_yscale('log')
usd_floor = 0.01
usd_ceiling = max(100_000, data['Close'].max() * 1.2)
ax2.set_ylim(usd_floor, usd_ceiling)
ax2.fill_between(data['Date'], usd_floor, data['Close'], alpha=0.3, color='#666666')

# Format y-axis with USD labels
usd_ticks = [1, 10, 100, 1_000, 10_000, 100_000]
usd_labels = ['$1', '$10', '$100', '$1k', '$10k', '$100k']
ax2.set_yticks(usd_ticks)
ax2.set_yticklabels(usd_labels, color='#00FF00', fontsize=10)
ax2.yaxis.set_label_position('left')
ax2.yaxis.tick_left()

# Format x-axis with years
ax2.xaxis.set_major_locator(mdates.YearLocator(2))  # Every 2 years
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax2.set_xlim(data['Date'].min(), data['Date'].max())
ax2.tick_params(axis='x', colors='white', labelsize=10)
ax2.tick_params(axis='y', colors='#00FF00')

# Remove spines
for spine in ax2.spines.values():
    spine.set_visible(False)

# Grid
ax2.grid(True, which="both", linestyle='--', alpha=0.1, color='white')

# Header: title, current value, and date
current_price_display = f"${current_price_btc_usd:,.2f}"
header2.text(0.5, 0.92, 'Price of 1 BTC in terms of US Dollar',
             ha='center', va='top', transform=header2.transAxes,
             fontsize=16, fontweight='bold', color='white')
header2.text(0.5, 0.58, current_price_display,
             ha='center', va='top', transform=header2.transAxes,
             fontsize=36, fontweight='bold', color='#00FF00')
header2.text(0.5, 0.18, current_date_str,
             ha='center', va='top', transform=header2.transAxes,
             fontsize=10, color='white')

output_path = script_dir / 'uoa_btc_usd.png'
plt.savefig(output_path, dpi=300, facecolor='black', bbox_inches='tight')
print(f"Chart saved as '{output_path}'")
# plt.show()  # Display the chart in Python (commented out for automation)
