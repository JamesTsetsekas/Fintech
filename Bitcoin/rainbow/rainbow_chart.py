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

# Halving dates
halving_dates = [
    datetime(2012, 11, 28),
    datetime(2016, 7, 9),
    datetime(2020, 5, 11),
    datetime(2024, 4, 19),
    datetime(2028, 4, 19),
    datetime(2032, 4, 19),
    datetime(2036, 4, 19),
    datetime(2040, 4, 19)
]

# Genesis block date (January 3, 2009)
genesis_date = datetime(2009, 1, 3)

# Calculate days since genesis for all dates
data['Days_Since_Genesis'] = (data['Date'] - genesis_date).dt.days

# HPR (Halving Price Regression) formula: log10(price) = 2.6521*LN(x) - 18.163
# where x is days since genesis
# Rearranging: price = 10^(2.6521*LN(x) - 18.163)
def hpr_price(days):
    """Calculate HPR price for given days since genesis"""
    days_array = np.array(days)
    result = np.full_like(days_array, np.nan, dtype=float)
    mask = days_array > 0
    result[mask] = 10 ** (2.6521 * np.log(days_array[mask]) - 18.163)
    if isinstance(days, pd.Series):
        return pd.Series(result, index=days.index)
    return result

# Generate HPR line for all dates
data['HPR'] = hpr_price(data['Days_Since_Genesis'])

# Create rainbow bands
# Blue band = on trend (HPR line itself)
# Each band above = another year ahead (365 days)
# We'll create bands by shifting the HPR line forward in time

def create_band(days_offset):
    """Create a band by offsetting days (positive = future, negative = past)"""
    shifted_days = data['Days_Since_Genesis'] + days_offset
    return hpr_price(shifted_days)

# Define bands (in days offset from HPR trend)
# Blue band: on trend (0 offset = HPR line)
# Green: 1 year ahead (365 days)
# Yellow: 2 years ahead (730 days)
# Orange: 3 years ahead (1095 days)
# Red: 4 years ahead (1460 days)
# Low (dark blue): -1 year behind (-365 days)

bands = {
    'Low': -365,      # Dark blue - 1 year behind trend
    'Blue': 0,        # Blue - on trend (HPR line)
    'Green': 365,     # Green - 1 year ahead
    'Yellow': 730,    # Yellow - 2 years ahead
    'Orange': 1095,   # Orange - 3 years ahead
    'Red': 1460       # Red - 4 years ahead
}

# Calculate band values
for band_name, offset in bands.items():
    data[f'{band_name}_Band'] = create_band(offset)

# Create figure with dark background - wider to use full width
plt.figure(figsize=(20, 10))
plt.style.use('dark_background')

# Plot rainbow bands (from bottom to top)
band_colors = {
    'Low': '#1a1a5e',      # Dark blue
    'Blue': '#0066cc',     # Blue
    'Green': '#00cc00',    # Green
    'Yellow': '#ffcc00',   # Yellow
    'Orange': '#ff6600',   # Orange
    'Red': '#cc0000'       # Red
}

# Plot bands as filled areas (rainbow effect)
band_order = ['Low', 'Blue', 'Green', 'Yellow', 'Orange', 'Red']
for i, band_name in enumerate(band_order):
    if i == 0:
        # First band: fill from bottom to Low band
        plt.fill_between(data['Date'], 0.1, data[f'{band_name}_Band'], 
                         color=band_colors[band_name], alpha=0.4, label=band_name)
    else:
        # Subsequent bands: fill between previous and current
        prev_band = band_order[i-1]
        plt.fill_between(data['Date'], 
                         data[f'{prev_band}_Band'], 
                         data[f'{band_name}_Band'],
                         color=band_colors[band_name], alpha=0.4, label=band_name)
    
    # Also plot the band line for clarity
    plt.plot(data['Date'], data[f'{band_name}_Band'], 
             color=band_colors[band_name], linewidth=1.5, alpha=0.9)

# Plot HPR line (purple)
plt.plot(data['Date'], data['HPR'], color='purple', linestyle='-', linewidth=1.5, 
         alpha=0.7, label='HPR', zorder=10)

# Plot Bitcoin price (white)
plt.plot(data['Date'], data['Price'], color='white', linewidth=2, label='Price', zorder=15)

# Plot halving events (vertical dashed green lines)
for date in halving_dates:
    if date <= data['Date'].max():
        plt.axvline(date, color='green', linestyle='--', alpha=0.5, linewidth=1, zorder=5)

# Set logarithmic Y-axis
plt.yscale('log')
plt.ylim(0.1, 10000000)

# Add halving labels after setting ylim
for date in halving_dates:
    if date <= data['Date'].max() and date >= data['Date'].min():
        y_pos = 0.15  # Position label just above bottom
        plt.text(date, y_pos, 'Halving', rotation=90, 
                ha='right', va='bottom', color='lightblue', fontsize=8, alpha=0.7)

# Format Y-axis
price_ticks = [1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
ax = plt.gca()
ax.set_yticks(price_ticks)

def format_price(x, p):
    if x < 1:
        return f'{x:.2f}'
    elif x >= 1:
        return f'{int(round(x)):,}'
    return str(x)

ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price))
ax.tick_params(axis='y', color='lightgray', labelsize=10)

# Set x-axis limits based on actual data range with small buffer for projection
# Extend slightly into future for projection, but not too far
data_end = data['Date'].max()
data_start = data['Date'].min()
# Extend 1-2 years into future for projection, but cap at reasonable limit
future_buffer = pd.Timedelta(days=730)  # 2 years
x_max = min(data_end + future_buffer, datetime(2028, 12, 31))  # Cap at 2028
x_min = max(data_start - pd.Timedelta(days=180), datetime(2010, 1, 1))  # Start from 2010 or data start
plt.xlim(x_min, x_max)

# Format X-axis (show years) - adjust based on date range
date_range = (x_max - x_min).days
if date_range > 3650:  # More than 10 years
    ax.xaxis.set_major_locator(mdates.YearLocator(base=2))  # Every 2 years
else:
    ax.xaxis.set_major_locator(mdates.YearLocator())  # Every year
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.xaxis.set_minor_locator(mdates.YearLocator())
ax.tick_params(axis='x', color='lightgray', labelsize=10, rotation=45)
ax.set_xlabel('Year', color='lightgray', fontsize=12)
ax.set_ylabel('USD', color='lightgray', fontsize=12, rotation=0, labelpad=20)

# Set title
ax.set_title('Bitcoin Rainbow Chart', color='lightgray', fontsize=16, fontweight='bold', pad=20)

# Add grid
plt.grid(True, which="major", linestyle='-', alpha=0.1, color='gray')
plt.grid(True, which="minor", linestyle='--', alpha=0.05, color='gray')

# Add legend
legend = plt.legend(loc='upper left', framealpha=0.3, fontsize=9)
for text in legend.get_texts():
    text.set_color('lightgray')

# Adjust subplot parameters to maximize chart area and reduce dead space
plt.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.1)

# Save the chart with optimized settings
output_path = script_dir / 'rainbow_chart.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black', 
            pad_inches=0.1, edgecolor='none')
print(f"Rainbow chart saved to: {output_path}")

# plt.show()  # Commented out for automation

