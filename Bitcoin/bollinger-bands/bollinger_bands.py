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
data['Date'] = pd.to_datetime(data['date'])
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Price'])
data = data.sort_values(by='Date')

# Set Date as index for time-based rolling
data_indexed = data.set_index('Date')

# Calculate Bollinger Bands
# Parameters: period = 20, standard deviation multiplier = 2
period = 20
std_multiplier = 2

# Calculate SMA 20 (Middle Band)
data_indexed['SMA_20'] = data_indexed['Price'].rolling(window=period, min_periods=1).mean()

# Calculate Standard Deviation
data_indexed['Std'] = data_indexed['Price'].rolling(window=period, min_periods=1).std()

# Calculate Upper and Lower Bands
data_indexed['Upper_Band'] = data_indexed['SMA_20'] + (data_indexed['Std'] * std_multiplier)
data_indexed['Lower_Band'] = data_indexed['SMA_20'] - (data_indexed['Std'] * std_multiplier)

# Reset index to get Date back as column
data = data_indexed.reset_index()

# Filter data for main chart (last 2 years or available data)
# Based on the image, it shows approximately 2 years of data
data_end = data['Date'].max()
data_start_main = max(data['Date'].min(), data_end - pd.Timedelta(days=730))  # ~2 years
main_data = data[data['Date'] >= data_start_main].copy()

# Create figure with dark background
# Main chart on top, mini chart on bottom
fig = plt.figure(figsize=(20, 12))
plt.style.use('dark_background')
fig.patch.set_facecolor('#1a1a1a')  # Dark grey background

# Create main chart (top, larger)
ax_main = plt.subplot2grid((10, 1), (0, 0), rowspan=7)
ax_main.set_facecolor('#1a1a1a')

# Create mini chart (bottom, smaller)
ax_mini = plt.subplot2grid((10, 1), (7, 0), rowspan=3)
ax_mini.set_facecolor('#1a1a1a')

# --- MAIN CHART ---
# Plot grey shaded area (Bollinger Bands)
ax_main.fill_between(main_data['Date'], main_data['Lower_Band'], main_data['Upper_Band'],
                     color='grey', alpha=0.3, zorder=1)

# Plot Upper Band (grey line)
ax_main.plot(main_data['Date'], main_data['Upper_Band'], 
             color='grey', linewidth=1, alpha=0.7, label='Upper Band', zorder=2)

# Plot Lower Band (black line)
ax_main.plot(main_data['Date'], main_data['Lower_Band'], 
             color='black', linewidth=1.5, label='Lower Band', zorder=3)

# Plot Price (orange line)
ax_main.plot(main_data['Date'], main_data['Price'], 
             color='#ff8c00', linewidth=2, label='Price', zorder=5)

# Plot SMA 20 (green line)
ax_main.plot(main_data['Date'], main_data['SMA_20'], 
             color='green', linewidth=1.5, label='SMA 20', zorder=4)

# Format main chart Y-axis
ax_main.set_ylabel('Price (USD)', color='lightgray', fontsize=12)
ax_main.tick_params(axis='y', labelcolor='lightgray', labelsize=10)
ax_main.tick_params(axis='x', labelcolor='lightgray', labelsize=10)
ax_main.grid(True, which="major", linestyle='-', alpha=0.1, color='gray')
ax_main.grid(True, which="minor", linestyle='--', alpha=0.05, color='gray')

# Set Y-axis limits based on data range
y_min = main_data[['Price', 'Lower_Band']].min().min() * 0.95
y_max = main_data[['Price', 'Upper_Band']].max().max() * 1.05
ax_main.set_ylim(y_min, y_max)

# Format Y-axis with appropriate ticks
y_range = y_max - y_min
if y_range > 50000:
    # Large range: use 20k intervals
    y_ticks = np.arange(0, y_max + 20000, 20000)
elif y_range > 10000:
    # Medium range: use 5k intervals
    y_ticks = np.arange(0, y_max + 5000, 5000)
else:
    # Small range: use 1k intervals
    y_ticks = np.arange(0, y_max + 1000, 1000)
ax_main.set_yticks(y_ticks)

# Format Y-axis labels
def format_price_y(x, p):
    if x >= 1000:
        return f'{x/1000:.0f}k'
    else:
        return f'{x:.0f}'

ax_main.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_y))

# Format X-axis for main chart
ax_main.set_xlim(main_data['Date'].min(), main_data['Date'].max())
ax_main.xaxis.set_major_locator(mdates.MonthLocator(interval=2))  # Every 2 months
ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax_main.xaxis.set_minor_locator(mdates.MonthLocator())
ax_main.tick_params(axis='x', rotation=45)

# Remove x-axis labels from main chart (will show on mini chart)
ax_main.set_xticklabels([])

# Add legend to main chart (bottom right)
legend = ax_main.legend(loc='lower right', framealpha=0.9, facecolor='white', 
                       edgecolor='black', fontsize=10)
for text in legend.get_texts():
    text.set_color('black')

# --- MINI CHART ---
# Plot all historical data in mini chart
ax_mini.fill_between(data['Date'], data['Lower_Band'], data['Upper_Band'],
                     color='grey', alpha=0.3, zorder=1)

# Plot Price (orange line)
ax_mini.plot(data['Date'], data['Price'], 
             color='#ff8c00', linewidth=1, zorder=3)

# Plot SMA 20 (green line)
ax_mini.plot(data['Date'], data['SMA_20'], 
             color='green', linewidth=1, zorder=2)

# Format mini chart
ax_mini.set_facecolor('#1a1a1a')
ax_mini.tick_params(axis='y', labelcolor='lightgray', labelsize=8)
ax_mini.tick_params(axis='x', labelcolor='lightgray', labelsize=8)
ax_mini.grid(True, which="major", linestyle='-', alpha=0.1, color='gray', linewidth=0.5)

# Set Y-axis for mini chart (log scale for better visibility of full range)
ax_mini.set_yscale('log')
ax_mini.set_ylim(data['Price'].min() * 0.5, data['Price'].max() * 2)

# Format mini chart Y-axis
price_ticks_mini = [100, 1000, 10000, 100000]
ax_mini.set_yticks(price_ticks_mini)
ax_mini.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_y))

# Format X-axis for mini chart
ax_mini.set_xlim(data['Date'].min(), data['Date'].max())
ax_mini.xaxis.set_major_locator(mdates.YearLocator())
ax_mini.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax_mini.tick_params(axis='x', rotation=45)

# Add vertical lines to show the zoomed period in main chart
ax_mini.axvline(main_data['Date'].min(), color='white', linewidth=1.5, linestyle='-', alpha=0.8, zorder=10)
ax_mini.axvline(main_data['Date'].max(), color='white', linewidth=1.5, linestyle='-', alpha=0.8, zorder=10)

# Adjust layout
plt.subplots_adjust(left=0.08, right=0.92, top=0.95, bottom=0.12, hspace=0.3)

# Save the chart
output_path = script_dir / 'bollinger_bands.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#1a1a1a', 
            pad_inches=0.1, edgecolor='none')
print(f"Bollinger Bands chart saved to: {output_path}")

# plt.show()  # Display the chart (commented out for automation)

