#!/usr/bin/env python3
"""
200 Day Moving Average & 200 Week Moving Average Chart

Creates a visualization showing Bitcoin's price with 200-day and 200-week
moving averages across three different time windows and scales.

The chart shows:
- Full History (Log Scale): Complete price history with both moving averages
- 200 Day Window (Linear Scale): Recent 200 days for short-term analysis
- 200 Week Window (Linear Scale): Recent 200 weeks for medium-term analysis
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime
from pathlib import Path

# Load data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'
data = pd.read_csv(dataset_path)

# Convert 'date' to datetime and 'price' to numeric
data['Date'] = pd.to_datetime(data['date'], format='%m/%d/%y')
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Price'])
data = data.sort_values(by='Date').reset_index(drop=True)

# Filter out zero prices (early data)
data = data[data['Price'] > 0].copy()

# Set Date as index for time-based rolling
data_indexed = data.set_index('Date')

# Calculate 200 Day Moving Average (200 DMA)
# 200 trading days ≈ 200 calendar days (using calendar days)
data_indexed['DMA_200'] = data_indexed['Price'].rolling(window=200, min_periods=1).mean()

# Calculate 200 Week Moving Average (200 WMA)
# 200 weeks = 1400 days (200 * 7)
data_indexed['WMA_200'] = data_indexed['Price'].rolling(window=1400, min_periods=1).mean()

# Reset index to get Date back as column
data = data_indexed.reset_index()

# Get current values (most recent non-null data)
current_row = data[data['Price'].notna()].iloc[-1]
current_date = current_row['Date']
current_price = float(current_row['Price'])
current_dma = float(current_row['DMA_200']) if pd.notna(current_row['DMA_200']) else None
current_wma = float(current_row['WMA_200']) if pd.notna(current_row['WMA_200']) else None

# Prepare data windows
# Full history - all data
full_data = data[data['Price'] > 0].copy()

# 200 Day Window - last 200 days
data_end = data['Date'].max()
data_start_200d = max(data['Date'].min(), data_end - pd.Timedelta(days=200))
data_200d = data[data['Date'] >= data_start_200d].copy()

# 200 Week Window - last 1400 days (200 weeks)
data_start_200w = max(data['Date'].min(), data_end - pd.Timedelta(days=1400))
data_200w = data[data['Date'] >= data_start_200w].copy()

# Create figure with dark background
fig = plt.figure(figsize=(20, 14))
plt.style.use('dark_background')
fig.patch.set_facecolor('black')

# Create grid for subplots: header row, then 2 columns (left: full history, right: split 200d/200w), footer
# Grid: 5 rows (header, 3 chart rows, footer), 2 columns
gs = fig.add_gridspec(5, 2, 
                      height_ratios=[0.8, 1, 1, 1, 0.6], 
                      width_ratios=[1, 1],
                      hspace=0.25, wspace=0.2)

# --- HEADER SECTION --- (spans both columns)
ax_header = fig.add_subplot(gs[0, :])
ax_header.set_facecolor('black')
ax_header.axis('off')

# Add header information
header_y = 0.5
# Format date as "Jan 7, 2026" (without zero padding)
date_str = f"{current_date.strftime('%b')} {current_date.day}, {current_date.year}"

# Left side: Date and Price
ax_header.text(0.02, header_y, f'Date: {date_str}', 
               ha='left', va='center', transform=ax_header.transAxes,
               fontsize=14, color='white', fontweight='bold')

ax_header.text(0.02, header_y - 0.35, f'Price: ${current_price:,.2f}', 
               ha='left', va='center', transform=ax_header.transAxes,
               fontsize=14, color='white', fontweight='bold')

# Middle: 200 DMA and 200 WMA
if current_dma is not None:
    ax_header.text(0.35, header_y, f'200 DMA: ${current_dma:,.2f}', 
                   ha='left', va='center', transform=ax_header.transAxes,
                   fontsize=14, color='#00ffff', fontweight='bold')  # Cyan

if current_wma is not None:
    ax_header.text(0.35, header_y - 0.35, f'200 WMA: ${current_wma:,.2f}', 
                   ha='left', va='center', transform=ax_header.transAxes,
                   fontsize=14, color='#ff8c00', fontweight='bold')  # Orange

# Title
ax_header.text(0.5, 0.85, '200 Day Moving Average & 200 Week Moving Average', 
               ha='center', va='center', transform=ax_header.transAxes,
               fontsize=20, fontweight='bold', color='white')

# Font-safe Bitcoin label.
ax_header.text(0.98, header_y, 'BTC',
               ha='right', va='center', transform=ax_header.transAxes,
               fontsize=24, color='#ff8c00', fontweight='bold')

# --- CHART 1: Full History (Log Scale) --- (left side, spans rows 1-3)
ax1 = fig.add_subplot(gs[1:4, 0])
ax1.set_facecolor('black')

# Plot price (white line)
ax1.plot(full_data['Date'], full_data['Price'], 
         color='white', linewidth=1.5, label='Price', zorder=3)

# Plot 200 DMA (cyan line)
ax1.plot(full_data['Date'], full_data['DMA_200'], 
         color='#00ffff', linewidth=1.5, label='200 DMA', zorder=2, alpha=0.9)

# Plot 200 WMA (orange line)
ax1.plot(full_data['Date'], full_data['WMA_200'], 
         color='#ff8c00', linewidth=1.5, label='200 WMA', zorder=2, alpha=0.9)

# Set log scale
ax1.set_yscale('log')

# Format Y-axis (log scale)
ax1.set_ylabel('Price (USD)', color='white', fontsize=11)
ax1.tick_params(axis='y', labelcolor='white', labelsize=9)
ax1.tick_params(axis='x', labelcolor='white', labelsize=9)

# Set Y-axis ticks for log scale
price_min = full_data['Price'].min()
price_max = full_data['Price'].max()
# Create log ticks from 0.1¢ to $100k
log_ticks = [0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000]
log_labels = ['0.1¢', '1¢', '10¢', '$1', '$10', '$100', '$1k', '$10k', '$100k']
# Filter ticks that are within data range
valid_ticks = [t for t in log_ticks if price_min <= t <= price_max]
valid_labels = [log_labels[i] for i, t in enumerate(log_ticks) if price_min <= t <= price_max]
ax1.set_yticks(valid_ticks)
ax1.set_yticklabels(valid_labels)

# Grid
ax1.grid(True, which="major", linestyle='-', alpha=0.2, color='white', linewidth=0.8)
ax1.grid(True, which="minor", linestyle='--', alpha=0.1, color='white', linewidth=0.5)

# Format X-axis
ax1.set_xlim(full_data['Date'].min(), full_data['Date'].max())
ax1.xaxis.set_major_locator(mdates.YearLocator(2))  # Every 2 years
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.xaxis.set_minor_locator(mdates.YearLocator())

# Title
ax1.text(0.5, 0.98, 'Full History (Log Scale)', 
         ha='center', va='top', transform=ax1.transAxes,
         fontsize=12, fontweight='bold', color='white')

# Remove spines
for spine in ax1.spines.values():
    spine.set_visible(False)

# --- CHART 2: 200 Day Window (Linear Scale) --- (right side, top)
ax2 = fig.add_subplot(gs[1:2, 1])
ax2.set_facecolor('black')

# Plot price (white line)
ax2.plot(data_200d['Date'], data_200d['Price'], 
         color='white', linewidth=2, label='Price', zorder=3)

# Plot 200 DMA (cyan line)
ax2.plot(data_200d['Date'], data_200d['DMA_200'], 
         color='#00ffff', linewidth=2, label='200 DMA', zorder=2, alpha=0.9)

# Plot 200 WMA (orange line)
ax2.plot(data_200d['Date'], data_200d['WMA_200'], 
         color='#ff8c00', linewidth=2, label='200 WMA', zorder=2, alpha=0.9)

# Format Y-axis (linear scale)
ax2.set_ylabel('Price (USD)', color='white', fontsize=11)
ax2.tick_params(axis='y', labelcolor='white', labelsize=9)
ax2.tick_params(axis='x', labelcolor='white', labelsize=9)

# Set Y-axis limits and ticks
price_min_200d = data_200d[['Price', 'DMA_200', 'WMA_200']].min().min()
price_max_200d = data_200d[['Price', 'DMA_200', 'WMA_200']].max().max()
y_range_200d = price_max_200d - price_min_200d
y_padding = y_range_200d * 0.1
ax2.set_ylim(price_min_200d - y_padding, price_max_200d + y_padding)

# Set Y-axis ticks ($10k intervals)
y_min_rounded = int(np.floor((price_min_200d - y_padding) / 10000) * 10000)
y_max_rounded = int(np.ceil((price_max_200d + y_padding) / 10000) * 10000)
y_ticks_200d = np.arange(y_min_rounded, y_max_rounded + 10000, 10000)
ax2.set_yticks(y_ticks_200d)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# Grid
ax2.grid(True, which="major", linestyle='-', alpha=0.2, color='white', linewidth=0.8)
ax2.grid(True, which="minor", linestyle='--', alpha=0.1, color='white', linewidth=0.5)

# Format X-axis
ax2.set_xlim(data_200d['Date'].min(), data_200d['Date'].max())
ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))  # Every month
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax2.xaxis.set_minor_locator(mdates.DayLocator(interval=7))  # Every week (7 days)
ax2.tick_params(axis='x', rotation=45)

# Title
ax2.text(0.5, 0.98, '200 Day Window (Linear Scale)', 
         ha='center', va='top', transform=ax2.transAxes,
         fontsize=12, fontweight='bold', color='white')

# Remove spines
for spine in ax2.spines.values():
    spine.set_visible(False)

# --- CHART 3: 200 Week Window (Linear Scale) --- (right side, bottom)
ax3 = fig.add_subplot(gs[2:4, 1])
ax3.set_facecolor('black')

# Plot price (white line)
ax3.plot(data_200w['Date'], data_200w['Price'], 
         color='white', linewidth=2, label='Price', zorder=3)

# Plot 200 DMA (cyan line)
ax3.plot(data_200w['Date'], data_200w['DMA_200'], 
         color='#00ffff', linewidth=2, label='200 DMA', zorder=2, alpha=0.9)

# Plot 200 WMA (orange line)
ax3.plot(data_200w['Date'], data_200w['WMA_200'], 
         color='#ff8c00', linewidth=2, label='200 WMA', zorder=2, alpha=0.9)

# Format Y-axis (linear scale)
ax3.set_ylabel('Price (USD)', color='white', fontsize=11)
ax3.tick_params(axis='y', labelcolor='white', labelsize=9)
ax3.tick_params(axis='x', labelcolor='white', labelsize=9)

# Set Y-axis limits and ticks
price_min_200w = data_200w[['Price', 'DMA_200', 'WMA_200']].min().min()
price_max_200w = data_200w[['Price', 'DMA_200', 'WMA_200']].max().max()
y_range_200w = price_max_200w - price_min_200w
y_padding_200w = y_range_200w * 0.1
ax3.set_ylim(price_min_200w - y_padding_200w, price_max_200w + y_padding_200w)

# Set Y-axis ticks ($20k intervals)
y_min_rounded_200w = int(np.floor((price_min_200w - y_padding_200w) / 20000) * 20000)
y_max_rounded_200w = int(np.ceil((price_max_200w + y_padding_200w) / 20000) * 20000)
y_ticks_200w = np.arange(y_min_rounded_200w, y_max_rounded_200w + 20000, 20000)
ax3.set_yticks(y_ticks_200w)
ax3.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# Grid
ax3.grid(True, which="major", linestyle='-', alpha=0.2, color='white', linewidth=0.8)
ax3.grid(True, which="minor", linestyle='--', alpha=0.1, color='white', linewidth=0.5)

# Format X-axis
ax3.set_xlim(data_200w['Date'].min(), data_200w['Date'].max())
ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))  # Every 6 months
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax3.xaxis.set_minor_locator(mdates.MonthLocator(interval=3))
ax3.tick_params(axis='x', rotation=45)

# Title
ax3.text(0.5, 0.98, '200 Week Window (Linear Scale)', 
         ha='center', va='top', transform=ax3.transAxes,
         fontsize=12, fontweight='bold', color='white')

# Remove spines
for spine in ax3.spines.values():
    spine.set_visible(False)

# --- FOOTER SECTION --- (spans both columns)
ax_footer = fig.add_subplot(gs[4, :])
ax_footer.set_facecolor('black')
ax_footer.axis('off')

# Footer area left empty

# Save the chart
output_path = script_dir / '200_dma_200_wma.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black', 
            pad_inches=0.1, edgecolor='none')
print(f"200 DMA & 200 WMA chart saved to: {output_path}")
print(f"Current Date: {date_str}")
print(f"Current Price: ${current_price:,.2f}")
if current_dma is not None:
    print(f"200 DMA: ${current_dma:,.2f}")
if current_wma is not None:
    print(f"200 WMA: ${current_wma:,.2f}")

# plt.show()  # Display the chart (commented out for automation)
