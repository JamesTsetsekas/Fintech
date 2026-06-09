import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
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
data = data.sort_values(by='Date')

# Set Date as index for time-based rolling
data_indexed = data.set_index('Date')

# Calculate Simple Moving Averages
# SMA 111-day (short-term)
data_indexed['SMA111d'] = data_indexed['Price'].rolling(window=111, min_periods=1).mean()

# SMA 350-day (long-term) multiplied by 2
data_indexed['SMA350d'] = data_indexed['Price'].rolling(window=350, min_periods=1).mean()
data_indexed['SMA350d_X2'] = data_indexed['SMA350d'] * 2

# Reset index to get Date back as column
data = data_indexed.reset_index()

plt.style.use('dark_background')
# Create figure with dark background
fig, ax = plt.subplots(figsize=(20, 10))
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# Set Y-axis to logarithmic scale for price
ax.set_yscale('log')
ax.set_ylabel('Price (USD)', color='lightgray', fontsize=12)
plotted_y_max = data[['Price', 'SMA111d', 'SMA350d_X2']].max().max()
y_upper = max(100000, plotted_y_max * 1.2)
ax.set_ylim(100.00, y_upper)

# Format Y-axis with log scale ticks
price_tick_candidates = [100, 200, 500, 1000, 2000, 5000, 10000, 20000,
                         50000, 100000, 200000, 500000, 1000000]
price_ticks = [tick for tick in price_tick_candidates if tick <= y_upper]
ax.set_yticks(price_ticks)

def format_price_log(x, p):
    """Format price labels for log scale"""
    if x >= 10000:
        return f'{x/1000:.0f}k'
    elif x >= 1000:
        return f'{x/1000:.1f}k'
    elif x >= 100:
        return f'{x:.0f}'
    else:
        return f'{x:.2f}'

ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_log))
ax.tick_params(axis='y', labelcolor='lightgray', labelsize=10)
ax.tick_params(axis='x', labelcolor='lightgray', labelsize=10)
ax.grid(True, which="major", linestyle='-', alpha=0.1, color='gray')
ax.grid(True, which="minor", linestyle='--', alpha=0.05, color='gray')

# Plot Price (gold line) - using a gold/yellow color
ax.plot(data['Date'], data['Price'], color='#FFD700', linewidth=1.5, label='Price (USD)', zorder=10)

# Plot SMA111d (cyan line)
ax.plot(data['Date'], data['SMA111d'], color='cyan', linewidth=1.5, label='SMA111d', zorder=9)

# Plot SMA350d X 2 (magenta line)
ax.plot(data['Date'], data['SMA350d_X2'], color='magenta', linewidth=1.5, label='SMA350d X 2', zorder=8)

# Set X-axis limits and format
x_min = max(data['Date'].min(), datetime(2012, 1, 1))
x_max = min(data['Date'].max(), datetime(2026, 12, 31))
ax.set_xlim(x_min, x_max)

# Format X-axis (show years)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.xaxis.set_minor_locator(mdates.MonthLocator((1, 7)))  # Minor ticks every 6 months
ax.set_xlabel('Day', color='lightgray', fontsize=12)

# Keep the legend inside the plot area to avoid savefig clipping.
legend = ax.legend(loc='lower right', bbox_to_anchor=(0.985, 0.035),
                  framealpha=0.9, facecolor='white', edgecolor='black', fontsize=10)
for text in legend.get_texts():
    text.set_color('black')

# Adjust layout
plt.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.08)

# Save the chart
output_path = script_dir / 'pi_cycle_top.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black', 
            pad_inches=0.1, edgecolor='none')
print(f"Pi Cycle Top Indicator chart saved to: {output_path}")

# Open the chart
# plt.show()  # Commented out for automation
