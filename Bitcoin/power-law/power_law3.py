import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bitcoin_chart_utils import bitcoin_data_dir, load_daily_price, power_law_band_prices  # noqa: E402

# Load your data
script_dir = Path(__file__).parent
data = load_daily_price(bitcoin_data_dir(__file__))
halving_dates = [datetime(2012, 11, 28), datetime(2016, 7, 9), datetime(2020, 5, 11), datetime(2024, 4, 19), datetime(2028, 4, 19),
                 datetime(2032, 4, 19), datetime(2036, 4, 19), datetime(2040, 4, 19)]

# Filter out zero prices and invalid data (needed for log calculations)
data = data[(data['Price'] > 0) & (data['Price'].notna())]
data = data.sort_values(by='Date').reset_index(drop=True)




# --- 1. Calculate the Power Law Regression (Log-Log) ---
# Standard Bitcoin Power Law uses days since Genesis Block (January 3, 2009)
genesis_date = datetime(2009, 1, 3)
days_since_genesis = (data['Date'] - genesis_date).dt.days.values
data = data[days_since_genesis > 0].reset_index(drop=True)
days_since_genesis = (data['Date'] - genesis_date).dt.days.values

# Extend time range for regression prediction
future_dates = pd.to_datetime([f'{year}-01-01' for year in range(data['Date'].max().year + 1, 2041)])
# Convert future_dates to a Pandas Series
future_dates_series = pd.Series(future_dates)
extended_dates = pd.concat([data['Date'], future_dates_series], ignore_index=True)
extended_days_since_genesis = (extended_dates - genesis_date).dt.days.values




# --- 3. Plotting ---
plt.figure(figsize=(14, 8))
plt.style.use('dark_background')


# Plot Bitcoin Price, Linear Reg, Upper and Lower Band, and Halving Markers
# Use days_since_genesis for x-axis (log scale)
plt.plot(days_since_genesis, data['Price'], color='orange', label='Price History')
# Generate smooth lines for regression and bands to appear straight on log-log plot
min_days = extended_days_since_genesis.min()
max_days = extended_days_since_genesis.max()
smooth_days = np.logspace(np.log10(min_days), np.log10(max_days), 1000)
smooth_linear_fit, smooth_lower_band, smooth_upper_band = power_law_band_prices(smooth_days)
plt.plot(smooth_days, smooth_linear_fit, color='red', linestyle='-', label='Power Law Fair Value (Projected)')
plt.plot(smooth_days, smooth_upper_band, color='purple', linestyle='--', alpha=0.7, label='Resistance (Projected)')
plt.plot(smooth_days, smooth_lower_band, color='green', linestyle='--', alpha=0.7, label='Support (Projected)')
# Convert halving dates to days since genesis for vertical lines
for date in halving_dates:
    halving_days = (date - genesis_date).days
    plt.axvline(halving_days, color='red', linestyle='--', alpha=0.5, label='Halving' if date == halving_dates[0] else "")


plt.yscale('log')
plt.xscale('log')                                                   # Set x-axis to logarithmic scale
# Set y-axis limits (use 0.1 as minimum to show values starting near zero)
plt.ylim(0.1, 10000000)
# Set specific price axis ticks (include 0.1 to represent near-zero)
price_ticks = [0.1, 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
ax = plt.gca()
ax.set_yticks(price_ticks)
# Format y-axis labels with commas
def format_price(x, p):
    if x <= 0.15:  # Show 0 for values near 0.1
        return '0'
    elif x >= 1:
        return f'{int(round(x)):,}'
    else:
        return f'{x:.2f}'
ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price))

# Calculate x-axis limits first (before setting ticks)
min_days_val = days_since_genesis.min()
max_days_val_extended = extended_days_since_genesis.max()

# Format x-axis with year ticks (extended to 2040)
min_year = data['Date'].min().year
max_year = 2040
year_ticks = []
year_labels = []
# Add the actual first data point as first tick to avoid dead space
first_data_days = min_days_val
if first_data_days > 0:
    year_ticks.append(first_data_days)
    year_labels.append(str(min_year))
# Add other year ticks
for year in range(min_year, max_year + 1, 4):  # Show every 4 years for extended range
    year_date = datetime(year, 1, 1)
    year_days = (year_date - genesis_date).days
    if year_days > first_data_days and year_days not in year_ticks:  # Avoid duplicates
        year_ticks.append(year_days)
        year_labels.append(str(year))
ax.set_xticks(year_ticks)
ax.set_xticklabels(year_labels, rotation=45, ha='right', color='gray')
# Set x-axis limits to show full data range (no dead space) - set after log scale
ax.set_xlim(min_days_val * 0.98, max_days_val_extended * 1.02)
plt.xlabel('Year', color='gray')
plt.ylabel('BTC Price ($)', color='gray')
plt.title('Bitcoin Price with Power Law Bands (Projected to 2040, Log-Log)', color='gray')
plt.tick_params(axis='x', color='gray')
plt.tick_params(axis='y', color='gray')
plt.yticks(color='gray')
plt.legend()
plt.grid(True, which="both", linestyle='--', alpha=0.1)
plt.tight_layout()
output_path = script_dir / 'power_law3.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black', pad_inches=0.1)
print(f"Chart saved as '{output_path}'")
# plt.show()  # Commented out for automation
