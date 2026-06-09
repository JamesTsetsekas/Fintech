#!/usr/bin/env python3
"""
Days Since All-Time High (ATH) Chart - Enhanced Dashboard

Creates a visualization showing Bitcoin's price history and days since ATH

The dashboard shows:
- Left panel: BTCUSD Price Chart (LOG LINEAR) with halving events
- Right panel: Days Since ATH chart with cycle peaks
- Top metrics: ATH, Daily High, Drawdown, Days Since ATH
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import requests

# Halving dates
halving_dates = [
    datetime(2012, 11, 28),
    datetime(2016, 7, 9),
    datetime(2020, 5, 11),
    datetime(2024, 4, 19),
]

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
if 'daily_high' in data.columns:
    data['High'] = pd.to_numeric(data['daily_high'], errors='coerce')
else:
    data['High'] = data['Close']
data = data.dropna(subset=['Date', 'Close'])

# Sort chronologically (oldest to newest)
data = data.sort_values(by='Date').reset_index(drop=True)

# Calculate running maximum (ATH up to each point)
data['Running_Max'] = data['Close'].expanding().max()

# Identify ATH dates (when we reach a new all-time high)
prev_running_max = data['Running_Max'].shift(1).fillna(0)
tolerance = 0.01
data['Is_ATH'] = (data['Running_Max'] - prev_running_max) > tolerance

# Calculate days since ATH
days_since_ath = []
last_ath_date = None

for idx, row in data.iterrows():
    if row['Is_ATH']:
        days_since_ath.append(0)
        last_ath_date = row['Date']
    else:
        if last_ath_date is not None:
            days = (row['Date'] - last_ath_date).days
            days_since_ath.append(days)
        else:
            days_since_ath.append(0)

data['Days_Since_ATH'] = days_since_ath

# Get current values
current_date = data['Date'].max()
current_days_since_ath = data[data['Date'] == current_date]['Days_Since_ATH'].iloc[0]
current_price = data[data['Date'] == current_date]['Close'].iloc[0]
current_ath = data['Running_Max'].max()
drawdown_pct = ((current_price - current_ath) / current_ath) * 100

# Get daily high
current_day_data = data[data['Date'] == current_date]
daily_high = current_day_data['High'].iloc[0] if not pd.isna(current_day_data['High'].iloc[0]) else current_price

# Find all ATH dates for vertical lines
ath_dates = data[data['Is_ATH']]['Date'].values

# Find peak days since ATH values for labeling (all peaks, including smaller ones)
peak_days = []
peak_dates = []
current_cycle_max = 0
current_cycle_max_date = None
cycle_peaks = []  # Store all peaks by cycle

for idx, row in data.iterrows():
    if row['Is_ATH']:
        # End of cycle - save peak if it exists
        if current_cycle_max > 0:
            cycle_peaks.append((current_cycle_max, current_cycle_max_date))
        # Reset for new cycle
        current_cycle_max = 0
        current_cycle_max_date = None
    else:
        # Track max in current cycle
        if row['Days_Since_ATH'] > current_cycle_max:
            current_cycle_max = row['Days_Since_ATH']
            current_cycle_max_date = row['Date']

# Handle the current (incomplete) cycle
if current_cycle_max > 0:
    cycle_peaks.append((current_cycle_max, current_cycle_max_date))

# Separate major peaks (>100 days) from minor peaks
major_peaks = [(d, date) for d, date in cycle_peaks if d > 100]
minor_peaks = [(d, date) for d, date in cycle_peaks if 50 <= d <= 100]

# Create figure with two subplots
fig = plt.figure(figsize=(20, 12))
fig.patch.set_facecolor('black')

# Create gridspec for layout: top bar for metrics, then two charts side by side
gs = fig.add_gridspec(2, 2, height_ratios=[1, 10], width_ratios=[1, 1], 
                      hspace=0.15, wspace=0.1, 
                      left=0.05, right=0.95, top=0.96, bottom=0.04)

# Top metrics bar (spans both columns)
metrics_ax = fig.add_subplot(gs[0, :])
metrics_ax.set_facecolor('black')
metrics_ax.axis('off')

# Metrics text
metrics_y = 0.5
label_fontsize = 10
stats_fontsize = 14

# All Time High
metrics_ax.text(0.02, metrics_y, 'All Time High (BTCUSD)', 
        ha='left', va='center', transform=metrics_ax.transAxes,
        fontsize=label_fontsize, color='#888888')
metrics_ax.text(0.02, metrics_y - 0.35, f'${current_ath:,.2f}', 
        ha='left', va='center', transform=metrics_ax.transAxes,
        fontsize=stats_fontsize, color='white', fontweight='bold')

# Daily High
metrics_ax.text(0.25, metrics_y, 'Daily High (BTCUSD)', 
        ha='left', va='center', transform=metrics_ax.transAxes,
        fontsize=label_fontsize, color='#888888')
metrics_ax.text(0.25, metrics_y - 0.35, f'${daily_high:,.2f}', 
        ha='left', va='center', transform=metrics_ax.transAxes,
        fontsize=stats_fontsize, color='white', fontweight='bold')

# Drawdown
drawdown_color = '#FF4444' if drawdown_pct < -20 else '#FFAA44' if drawdown_pct < -10 else '#FFFFFF'
metrics_ax.text(0.50, metrics_y, 'Drawdown from ATH', 
        ha='left', va='center', transform=metrics_ax.transAxes,
        fontsize=label_fontsize, color='#888888')
metrics_ax.text(0.50, metrics_y - 0.35, f'{drawdown_pct:.2f}%', 
        ha='left', va='center', transform=metrics_ax.transAxes,
        fontsize=stats_fontsize, color=drawdown_color, fontweight='bold')

# Days Since ATH
metrics_ax.text(0.98, metrics_y, 'Days Since ATH', 
        ha='right', va='center', transform=metrics_ax.transAxes,
        fontsize=label_fontsize, color='#888888')
metrics_ax.text(0.98, metrics_y - 0.35, f'{int(current_days_since_ath)}', 
        ha='right', va='center', transform=metrics_ax.transAxes,
        fontsize=stats_fontsize, color='#FF8C00', fontweight='bold')

# Left panel: Price Chart (LOG LINEAR)
ax1 = fig.add_subplot(gs[1, 0])
ax1.set_facecolor('black')

# Plot price on log scale
ax1.semilogy(data['Date'], data['Close'], color='#FF8C00', linewidth=2.5, zorder=3, label='BTCUSD')
ax1.set_ylabel('Price (BTCUSD)', color='#FF8C00', fontsize=12, fontweight='bold')
ax1.tick_params(axis='y', colors='#FF8C00', labelsize=10)
ax1.set_xlabel('Date', color='white', fontsize=11)

# Format x-axis
ax1.xaxis.set_major_locator(mdates.YearLocator(2))
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.xaxis.set_minor_locator(mdates.YearLocator())
ax1.set_xlim(data['Date'].min(), data['Date'].max())
ax1.tick_params(axis='x', colors='white', labelsize=10)

# Add halving events (after setting xlim so ylim is set properly)
halving_labels = ['1st Halving', '2nd Halving', '3rd Halving', '4th Halving']
for i, halving_date in enumerate(halving_dates):
    if halving_date <= data['Date'].max():
        ax1.axvline(x=halving_date, color='white', linestyle='--', linewidth=1.5, alpha=0.5, zorder=1)
        # Add label
        y_pos = ax1.get_ylim()[1] * 0.15
        ax1.text(halving_date, y_pos, halving_labels[i], 
                rotation=90, ha='right', va='bottom',
                color='white', fontsize=9, alpha=0.7)

# Remove spines
for spine in ax1.spines.values():
    spine.set_visible(False)

# Grid
ax1.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.8)
ax1.grid(True, which="minor", linestyle=':', alpha=0.08, color='white', linewidth=0.5)

# Title
ax1.text(0.5, 0.98, 'BTCUSD LOG LINEAR', 
        ha='center', va='top', transform=ax1.transAxes,
        fontsize=14, fontweight='bold', color='white')

# Block height (from mempool.space API or fallback)
current_block_height = get_block_height_from_mempool()
if current_block_height is None:
    current_block_height = calculate_block_height_fallback(current_date)
ax1.text(0.02, 0.98, f'BLOCK HEIGHT: {current_block_height}', 
        ha='left', va='top', transform=ax1.transAxes,
        fontsize=10, color='white', fontweight='bold')
# Add green triangle marker at current position
ax1.plot(current_date, current_price, '^', color='#00FF00', markersize=8, zorder=5, 
         transform=ax1.transData, clip_on=False)

# Right panel: Days Since ATH
ax2 = fig.add_subplot(gs[1, 1])
ax2.set_facecolor('black')

# Fill area under the curve
ax2.fill_between(data['Date'], 0, data['Days_Since_ATH'], alpha=0.2, color='#FF8C00', zorder=2)

# Plot the days since ATH line
ax2.plot(data['Date'], data['Days_Since_ATH'], color='#FF8C00', linewidth=2.5, zorder=3)

# Add vertical dashed lines at ATH events
for ath_date in ath_dates:
    ax2.axvline(x=ath_date, color='white', linestyle='--', linewidth=1.5, alpha=0.4, zorder=1)

# Label major peaks
for peak_day, peak_date in major_peaks:
    ax2.plot(peak_date, peak_day, 'o', color='#FF8C00', markersize=8, zorder=6, 
            markeredgecolor='white', markeredgewidth=1)
    ax2.text(peak_date, peak_day, f' {int(peak_day)}', 
            color='#FF8C00', fontsize=11, fontweight='bold', 
            verticalalignment='bottom', horizontalalignment='left', zorder=7)

# Label minor peaks (smaller spikes)
for peak_day, peak_date in minor_peaks:
    if peak_date > data['Date'].max() - pd.Timedelta(days=500):  # Only show recent minor peaks
        ax2.plot(peak_date, peak_day, 'o', color='#FF8C00', markersize=5, zorder=5, 
                markeredgecolor='white', markeredgewidth=0.8, alpha=0.8)
        ax2.text(peak_date, peak_day, f' {int(peak_day)}', 
                color='#FF8C00', fontsize=9, fontweight='bold', 
                verticalalignment='bottom', horizontalalignment='left', zorder=6, alpha=0.8)

# Format x-axis
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax2.xaxis.set_minor_locator(mdates.YearLocator())
ax2.set_xlim(data['Date'].min(), data['Date'].max())
ax2.tick_params(axis='x', colors='white', labelsize=10)

# Format y-axis
ax2.set_ylabel('Days Since ATH', color='#FF8C00', fontsize=12, fontweight='bold')
ax2.tick_params(axis='y', colors='#FF8C00', labelsize=10)
ax2.set_ylim(bottom=0)

max_days = data['Days_Since_ATH'].max()
if max_days > 1000:
    major_interval = 200
elif max_days > 500:
    major_interval = 100
else:
    major_interval = 50
ax2.yaxis.set_major_locator(ticker.MultipleLocator(major_interval))

# Remove spines
for spine in ax2.spines.values():
    spine.set_visible(False)

# Grid
ax2.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.8)
ax2.grid(True, which="minor", linestyle=':', alpha=0.08, color='white', linewidth=0.5)

# Title
ax2.text(0.5, 0.98, 'DAYS SINCE ATH', 
        ha='center', va='top', transform=ax2.transAxes,
        fontsize=14, fontweight='bold', color='white')

# Add date label at bottom right
current_date_str = current_date.strftime('%b %d, %Y').upper()
ax2.text(0.98, 0.02, f'{current_date_str} ▲', 
        ha='right', va='bottom', transform=ax2.transAxes,
        fontsize=9, color='#888888')

# Add green triangle marker at current position
max_days_val = data['Days_Since_ATH'].max()
current_y_pos = current_days_since_ath if current_days_since_ath < max_days_val * 0.95 else max_days_val * 0.95
ax2.plot(current_date, current_days_since_ath, '^', color='#00FF00', markersize=6, zorder=5, 
         transform=ax2.transData, clip_on=False)

# Save
output_path = script_dir / 'days_since_ath.png'
plt.savefig(output_path, dpi=300, facecolor='black', bbox_inches='tight')
print(f"Chart saved as '{output_path}'")
print(f"Current ATH: ${current_ath:,.2f}")
print(f"Current Price: ${current_price:,.2f}")
print(f"Days Since ATH: {int(current_days_since_ath)}")
print(f"Drawdown: {drawdown_pct:.2f}%")
# plt.show()  # Display the chart (commented out for automation)
