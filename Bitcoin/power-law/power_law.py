import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
import math
from datetime import datetime
from pathlib import Path

# Load your data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'
data = pd.read_csv(dataset_path)
halving_dates = [datetime(2012, 11, 28), datetime(2016, 7, 9), datetime(2020, 5, 11), datetime(2024, 4, 19), datetime(2028, 4, 19)]

# Convert 'date' to datetime and 'price' to numeric
data['Date'] = pd.to_datetime(data['date'])
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
# Filter out zero prices and invalid data (needed for log calculations)
data = data[(data['Price'] > 0) & (data['Price'].notna())]
data = data.sort_values(by='Date').reset_index(drop=True)



# --- 1. Calculate the Power Law Fit ---
# Standard Bitcoin Power Law uses days since Genesis Block (January 3, 2009)
genesis_date = datetime(2009, 1, 3)
days_since_genesis = (data['Date'] - genesis_date).dt.days.values

def power_law(t, a, b):
    return a * (t ** b)

try:
    from scipy.optimize import curve_fit
    # Use standard initial parameters: A ≈ 10^-17, n ≈ 5.8
    popt, pcov = curve_fit(power_law, days_since_genesis, data['Price'], p0=[1e-17, 5.8])
    # Generate smooth line for power law fit to appear straight on log-log plot
    min_days = days_since_genesis.min()
    max_days = days_since_genesis.max()
    smooth_days = np.logspace(np.log10(min_days), np.log10(max_days), 1000)
    power_law_fit_smooth = power_law(smooth_days, *popt)
    # Also keep original for data points alignment
    power_law_fit = power_law(days_since_genesis, *popt)
except ImportError:
    print("Error: scipy not installed.")
    power_law_fit = np.full_like(data['Price'], np.nan)
    smooth_days = days_since_genesis
    power_law_fit_smooth = np.full_like(data['Price'], np.nan)
except RuntimeError:
    print("Error: Optimal parameters not found.")
    power_law_fit = np.full_like(data['Price'], np.nan)
    smooth_days = days_since_genesis
    power_law_fit_smooth = np.full_like(data['Price'], np.nan)



# --- 2. Plotting ---
plt.figure(figsize=(14, 8))
plt.style.use('dark_background')


# Plot Bitcoin Price, Plot Power Law Fit, Plot Halving Markers
# Use days_since_genesis for x-axis (log scale)
plt.plot(days_since_genesis, data['Price'], color='lime', label='Bitcoin Price')
# Plot smooth power law fit line to appear straight on log-log
if not np.isnan(power_law_fit_smooth).all():
    plt.plot(smooth_days, power_law_fit_smooth, color='magenta', linestyle='-', label='Power Law Fit')
# Convert halving dates to days since genesis for vertical lines
for date in halving_dates:
    halving_days = (date - genesis_date).days
    plt.axvline(halving_days, color='red', linestyle='--', alpha=0.7, label='Halving' if date == halving_dates[0] else "")


plt.yscale('log')                                                   # Set y-axis to logarithmic scale
plt.xscale('log')                                                   # Set x-axis to logarithmic scale
# Set y-axis limits (use 0.1 as minimum to show values starting near zero)
plt.ylim(0.1, 10000000)
# Set specific price axis ticks (include 0.1 to represent near-zero)
price_ticks = [0.1, 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
ax = plt.gca()                                                      # Get the current axes
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
ax.tick_params(axis='y', color='gray')                            # Set the y-axis tick labels color to gray

# Calculate x-axis limits first (before setting ticks)
min_days_val = days_since_genesis.min()
max_days_val = days_since_genesis.max()

# Format x-axis with year ticks
min_year = data['Date'].min().year
max_year = data['Date'].max().year
year_ticks = []
year_labels = []
# Add the actual first data point as first tick to avoid dead space
first_data_days = min_days_val
if first_data_days > 0:
    year_ticks.append(first_data_days)
    year_labels.append(str(min_year))
# Add other year ticks
for year in range(min_year, max_year + 1, 2):  # Show every 2 years
    year_date = datetime(year, 1, 1)
    year_days = (year_date - genesis_date).days
    if year_days > first_data_days and year_days not in year_ticks:  # Avoid duplicates
        year_ticks.append(year_days)
        year_labels.append(str(year))
ax.set_xticks(year_ticks)
ax.set_xticklabels(year_labels, rotation=45, ha='right', color='gray')
# Set x-axis limits to show full data range (no dead space) - set after log scale
ax.set_xlim(min_days_val * 0.98, max_days_val * 1.02)
ax.set_xlabel('Year', color='gray')                               
ax.set_ylabel('BTC Price ($)', color='gray')
ax.set_title('Bitcoin Power Law Chart (Log-Log)', color='gray')
plt.yticks(color='gray')
plt.legend()
plt.grid(True, which="both", linestyle='--', alpha=0.1)
plt.tight_layout()
output_path = script_dir / 'power_law.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black', pad_inches=0.1)
print(f"Chart saved as '{output_path}'")
# plt.show()  # Commented out for automation