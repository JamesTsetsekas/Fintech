import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bitcoin_chart_utils import bitcoin_data_dir, load_daily_price, power_law_price  # noqa: E402

# Load data
script_dir = Path(__file__).parent
data = load_daily_price(bitcoin_data_dir(__file__))

# Filter out NaN, zero, and negative prices (needed for log calculations)
data = data.dropna(subset=['Date', 'Price'])
data = data[data['Price'] > 0].copy()  # Filter out zero/negative prices
data = data.sort_values(by='Date')

# Genesis block date (January 3, 2009)
genesis_date = datetime(2009, 1, 3)

# Calculate days since genesis for all dates
data['Days_Since_Genesis'] = (data['Date'] - genesis_date).dt.days

# Filter out invalid days (must be positive)
data = data[data['Days_Since_Genesis'] > 0].copy()

# Check if we have enough data points
if len(data) < 10:
    raise ValueError(f"Not enough valid data points after filtering. Found {len(data)} points.")

# Calculate power law fit for all data points
data['Power_Law_Fit'] = power_law_price(data['Days_Since_Genesis'])

# Ensure power law fit values are positive (safety check)
data = data[data['Power_Law_Fit'] > 0].copy()

# --- Calculate the Oscillator ---
# Oscillator = normalized log deviation between actual price and power law fit
# Formula: oscillator = (log(price) - log(power_law_fit)) / normalization_factor
# Normalize to -1 to 1 range using percentile-based approach for better stability

log_price = np.log(data['Price'])
log_fit = np.log(data['Power_Law_Fit'])
deviation = log_price - log_fit

# Normalize to -1 to 1 range using percentile-based method
# This is more robust than using max absolute deviation
p95 = np.percentile(deviation, 95)
p5 = np.percentile(deviation, 5)
max_range = max(abs(p95), abs(p5))

if max_range > 0:
    # Normalize so that 95th and 5th percentiles map to approximately -1 and 1
    data['Oscillator'] = deviation / max_range
    # Clip to ensure values stay within -1 to 1 range
    data['Oscillator'] = np.clip(data['Oscillator'], -1, 1)
else:
    data['Oscillator'] = 0

# --- Calculate Median (moving median of oscillator) ---
# Use a rolling window to calculate median
# Typical window size: 365 days (1 year) or 30 days (1 month)
# Based on the chart, it looks like a longer-term median, let's use 365 days
# Set Date as index for time-based rolling
data_indexed = data.set_index('Date')
window_days = '365D'  # 365 days
data_indexed['Median'] = data_indexed['Oscillator'].rolling(window=window_days, min_periods=1, center=True).median()
data = data_indexed.reset_index()

# Create figure with dark background
fig, ax1 = plt.subplots(figsize=(20, 10))
plt.style.use('dark_background')
fig.patch.set_facecolor('black')
ax1.set_facecolor('black')

# Left Y-axis for Oscillator and Median
ax1.set_ylabel('USD oscillator', color='lightgray', fontsize=12)
ax1.set_ylim(-1.00, 1.00)
ax1.set_yticks(np.arange(-1.00, 1.01, 0.20))
ax1.tick_params(axis='y', labelcolor='lightgray', labelsize=10)
ax1.tick_params(axis='x', labelcolor='lightgray', labelsize=10)
ax1.grid(True, which="major", linestyle='-', alpha=0.1, color='gray')
ax1.grid(True, which="minor", linestyle='--', alpha=0.05, color='gray')

# Plot Oscillator (purple line)
ax1.plot(data['Date'], data['Oscillator'], color='purple', linewidth=1.5, label='Oscillator', zorder=10)

# Plot Median (orange line)
ax1.plot(data['Date'], data['Median'], color='orange', linewidth=1.5, label='Median', zorder=9)

# Right Y-axis for USD Price (logarithmic scale)
ax2 = ax1.twinx()
ax2.set_ylabel('USD price', color='lightgray', fontsize=12)
ax2.set_yscale('log')
ax2.set_ylim(1, 200000)
ax2.tick_params(axis='y', labelcolor='lightgray', labelsize=10)

# Format right Y-axis with log scale ticks
price_ticks = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]
ax2.set_yticks(price_ticks)

def format_price_log(x, p):
    if x >= 1000:
        return f'{int(x/1000)}k'
    elif x >= 1:
        return f'{int(x)}'
    else:
        return f'{x:.2f}'

ax2.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_log))

# Plot USD Price (green line)
ax2.plot(data['Date'], data['Price'], color='green', linewidth=1.5, label='USD price', zorder=8)

# Plot Power Law Fit (light blue/cyan line)
ax2.plot(data['Date'], data['Power_Law_Fit'], color='cyan', linewidth=1.5, label='Power Law Fit', zorder=7, alpha=0.8)

# Set X-axis limits and format
x_min = max(data['Date'].min(), datetime(2011, 1, 1))
x_max = min(data['Date'].max(), datetime(2026, 12, 31))
ax1.set_xlim(x_min, x_max)

# Format X-axis (show years)
ax1.xaxis.set_major_locator(mdates.YearLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.xaxis.set_minor_locator(mdates.YearLocator())
ax1.set_xlabel('Year', color='lightgray', fontsize=12)

# Add title (optional, can be removed to match original)
# ax1.set_title('Power Law Oscillator', color='lightgray', fontsize=16, fontweight='bold', pad=20)

# Add legend in bottom-right
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
all_lines = lines1 + lines2
all_labels = labels1 + labels2
legend = ax1.legend(all_lines, all_labels, loc='lower right', 
                   framealpha=0.9, facecolor='white', edgecolor='black', fontsize=10)
for text in legend.get_texts():
    text.set_color('black')

# Adjust layout
plt.subplots_adjust(left=0.08, right=0.92, top=0.95, bottom=0.08)

# Save the chart
output_path = script_dir / 'power_law_oscillator.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black', 
            pad_inches=0.1, edgecolor='none')
print(f"Power Law Oscillator chart saved to: {output_path}")

# Close the figure to free memory
plt.close(fig)

# plt.show()  # Commented out for automation
