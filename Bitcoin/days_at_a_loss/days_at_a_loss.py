#!/usr/bin/env python3
"""
Number of Days Spent at a Loss Chart

Creates a visualization showing the number of days that purchases made at each
price point have spent at a loss

The chart shows:
- Line graph with gradient colors (green to yellow to red) indicating days at a loss
- Heatmap/bar chart below showing the same data
- Header information with current stats
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import requests

# Genesis block date
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
data['Close'] = pd.to_numeric(data['price'], errors='coerce')
data['High'] = pd.to_numeric(data['daily_high'], errors='coerce')
data = data.dropna(subset=['Date', 'Close'])
data = data.sort_values(by='Date').reset_index(drop=True)

# Calculate days at a loss for each date
# For each date, if someone bought at that day's price, count how many days
# since then the price has been below that purchase price
# Use vectorized operations for efficiency
print("Calculating days at a loss...")
prices = data['Close'].values
n = len(prices)
days_at_loss = np.zeros(n, dtype=int)

# Vectorized calculation: for each price, count future prices below it
for i in range(n - 1):
    if i % 500 == 0:
        print(f"  Processing {i}/{n}...")
    purchase_price = prices[i]
    future_prices = prices[i+1:]
    days_at_loss[i] = (future_prices < purchase_price).sum()

print("Calculation complete.")
data['Days_At_Loss'] = days_at_loss

# Get current values
current_date = data['Date'].max()
current_row = data[data['Date'] == current_date].iloc[0]
current_price = current_row['Close']
current_high = current_row['High'] if pd.notna(current_row['High']) else current_price
current_days_at_loss = current_row['Days_At_Loss']

# Calculate network age (days since Bitcoin genesis: Jan 3, 2009)
network_age = (current_date - GENESIS_DATE).days

# Get block height from mempool.space API or fallback
block_height = get_block_height_from_mempool()
if block_height is None:
    block_height = calculate_block_height_fallback(current_date)

# Find the most recent ATH and calculate days at loss for purchases at that ATH
ath_price = data['Close'].max()
ath_row = data[data['Close'] == ath_price].iloc[-1]  # Get the most recent ATH
ath_date = ath_row['Date']
ath_days_at_loss = ath_row['Days_At_Loss']

# Create figure with dark background
fig = plt.figure(figsize=(18, 11))
fig.patch.set_facecolor('black')

# Create two subplots: line chart on top, heatmap on bottom
gs = fig.add_gridspec(2, 1, height_ratios=[2, 1], hspace=0.05)
ax1 = fig.add_subplot(gs[0])  # Line chart
ax2 = fig.add_subplot(gs[1])  # Heatmap
ax1.set_facecolor('black')
ax2.set_facecolor('black')

# Create color gradient (green -> yellow -> red)
colors = ['#00FF00', '#FFFF00', '#FF0000']
n_bins = 100
cmap = LinearSegmentedColormap.from_list('loss_gradient', colors, N=n_bins)

# Normalize days at loss for coloring
max_days = data['Days_At_Loss'].max()
norm = plt.Normalize(vmin=0, vmax=max_days)

# Plot line chart with gradient colors
dates_array = data['Date'].values
days_array = data['Days_At_Loss'].values

# Plot line segments with gradient colors
# Use a reasonable step size to balance detail and performance
step = max(1, len(data) // 1500)  # Limit segments for performance
for i in range(0, len(data) - step, step):
    end_idx = min(i + step, len(data) - 1)
    x_segment = dates_array[i:end_idx+1]
    y_segment = days_array[i:end_idx+1]
    color = cmap(norm(days_array[i]))
    ax1.plot(x_segment, y_segment, color=color, linewidth=2.5, alpha=0.9, zorder=2)

# Format top chart (line graph)
ax1.set_ylabel('days', color='white', fontsize=12, fontweight='bold')
ax1.tick_params(axis='y', colors='white', labelsize=10)
ax1.tick_params(axis='x', colors='white', labelsize=10)
ax1.set_ylim(bottom=0)
ax1.set_xlim(data['Date'].min(), data['Date'].max())

# Set y-axis ticks
max_days_rounded = int(np.ceil(max_days / 300) * 300)
if max_days_rounded > 1200:
    y_ticks = [0, 300, 600, 900, 1200]
elif max_days_rounded > 900:
    y_ticks = [0, 300, 600, 900]
elif max_days_rounded > 600:
    y_ticks = [0, 300, 600]
else:
    y_ticks = [0, 100, 200, 300]
ax1.set_yticks(y_ticks)
ax1.set_yticklabels([f'{int(t):,} days' if t > 0 else '0 days' for t in y_ticks])

# Remove spines
for spine in ax1.spines.values():
    spine.set_visible(False)

# Grid
ax1.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.8)

# Plot heatmap/bar chart
# Use fill_between for better performance
dates_array = data['Date'].values
days_array = data['Days_At_Loss'].values

# Calculate bar width in days
# Convert numpy timedelta64 to days
date_diff = dates_array[-1] - dates_array[0]
total_days = date_diff.astype('timedelta64[D]').astype(int)
bar_width_days = total_days / len(data) * 0.95

# Sample data points for heatmap to improve performance
sample_step = max(1, len(data) // 800)  # Limit to ~800 bars for performance
sampled_dates = dates_array[::sample_step]
sampled_days = days_array[::sample_step]
sampled_colors = [cmap(norm(d)) for d in sampled_days]

# Plot bars
for date, color in zip(sampled_dates, sampled_colors):
    ax2.bar(date, max_days, width=bar_width_days, color=color, alpha=0.85, align='center', edgecolor='none')

# Format bottom chart (heatmap)
ax2.set_ylim(0, max_days)
ax2.set_xlim(data['Date'].min(), data['Date'].max())
ax2.set_xticks([])  # Remove x-axis labels from bottom chart
ax2.set_yticks([])  # Remove y-axis labels from bottom chart

# Remove spines
for spine in ax2.spines.values():
    spine.set_visible(False)

# Format x-axis on top chart
ax1.xaxis.set_major_locator(mdates.YearLocator(2))
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.xaxis.set_minor_locator(mdates.YearLocator())

# Add title/header area
header_y = 0.97
header_bg_y = 0.88
header_height = 0.09

# Header background
header_bg = Rectangle((0, header_bg_y), 1, header_height, 
                     transform=fig.transFigure, 
                     facecolor='black', alpha=0.8, 
                     edgecolor='#333333', linewidth=1, zorder=2)
fig.patches.append(header_bg)


# Date and Block Height
date_str = current_date.strftime('%b %d, %Y')
ax1.text(0.02, 0.90, f'Date: {date_str}', 
        ha='left', va='top', transform=ax1.transAxes,
        fontsize=10, color='white')
ax1.text(0.02, 0.86, f'Block Height: {block_height:,}', 
        ha='left', va='top', transform=ax1.transAxes,
        fontsize=10, color='white')

# Price (Daily High)
ax1.text(0.25, 0.90, f'Price (Daily High): ${current_high:,.2f}', 
        ha='left', va='top', transform=ax1.transAxes,
        fontsize=10, color='white', fontweight='bold')

# Network Age
ax1.text(0.25, 0.86, f'Network Age: {network_age:,} Days', 
        ha='left', va='top', transform=ax1.transAxes,
        fontsize=10, color='white')

# ATH purchase info (top right)
if ath_days_at_loss > 0:
    ath_date_str = ath_date.strftime('%b %d, %Y')
    ax1.text(0.98, 0.95, f'Purchases made at the ATH on {ath_date_str} at ${ath_price:,.0f}\nhave spent {int(ath_days_at_loss)} day(s) at a loss', 
            ha='right', va='top', transform=ax1.transAxes,
            fontsize=9, color='white',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='black', alpha=0.8, 
                     edgecolor='white', linewidth=1))

# Title
ax1.text(0.5, 0.98, 'NUMBER OF DAYS SPENT AT A LOSS', 
        ha='center', va='top', transform=ax1.transAxes,
        fontsize=20, fontweight='bold', color='white')


plt.tight_layout()
output_path = script_dir / 'days_at_a_loss.png'
plt.savefig(output_path, dpi=300, facecolor='black', bbox_inches='tight')
print(f"Chart saved as '{output_path}'")
print(f"Current Date: {date_str}")
print(f"Current Price: ${current_price:,.2f}")
print(f"Current Days at Loss: {int(current_days_at_loss)}")
print(f"ATH Price: ${ath_price:,.2f}")
print(f"ATH Days at Loss: {int(ath_days_at_loss)}")

# plt.show()  # Display the chart (commented out for automation)

