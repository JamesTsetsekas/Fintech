import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
from datetime import datetime, timedelta
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

# Calculate 111-day SMA
data_indexed['SMA111'] = data_indexed['Price'].rolling(window=111, min_periods=1).mean()

# Calculate 350-day SMA and multiply by 2
data_indexed['SMA350'] = data_indexed['Price'].rolling(window=350, min_periods=1).mean()
data_indexed['SMA350_x2'] = data_indexed['SMA350'] * 2

# Reset index to get Date back as column
data = data_indexed.reset_index()

# Filter data from Jan 2020 onwards (as shown in the image)
data_start = datetime(2020, 1, 1)
data = data[data['Date'] >= data_start].copy()

# Get the last date in the data
last_date = data['Date'].max()
last_idx = len(data) - 1

# Calculate slopes over the past 10 days for projection
# Use the last 10 days of available data
lookback_days = 10
if len(data) >= lookback_days:
    # Get last 10 days of SMA values
    sma111_recent = data['SMA111'].iloc[-lookback_days:].values
    sma350_x2_recent = data['SMA350_x2'].iloc[-lookback_days:].values
    dates_recent = data['Date'].iloc[-lookback_days:]
    
    # Convert dates to numeric (days since first date) for linear regression
    # Use pandas Timedelta to handle the conversion properly
    first_date = dates_recent.iloc[0]
    days_since_start = np.array([(pd.Timestamp(d) - pd.Timestamp(first_date)).days for d in dates_recent])
    
    # Calculate linear regression slopes
    # SMA111 slope
    sma111_slope = np.polyfit(days_since_start, sma111_recent, 1)[0]
    sma111_intercept = np.polyfit(days_since_start, sma111_recent, 1)[1]
    
    # SMA350_x2 slope
    sma350_x2_slope = np.polyfit(days_since_start, sma350_x2_recent, 1)[0]
    sma350_x2_intercept = np.polyfit(days_since_start, sma350_x2_recent, 1)[1]
    
    # Get last values
    last_sma111 = data['SMA111'].iloc[-1]
    last_sma350_x2 = data['SMA350_x2'].iloc[-1]
    
    # Project forward up to 1 year (365 days) from last date
    projection_days = 365
    future_dates = [last_date + timedelta(days=i) for i in range(1, projection_days + 1)]
    
    # Calculate projected values
    # Convert last_date to pandas Timestamp for proper timedelta calculation
    last_date_ts = pd.Timestamp(last_date)
    days_from_last = np.array([(pd.Timestamp(d) - last_date_ts).days for d in future_dates])
    projected_sma111 = last_sma111 + sma111_slope * days_from_last
    projected_sma350_x2 = last_sma350_x2 + sma350_x2_slope * days_from_last
    
    # Check if lines will cross in the projection period
    # Find where SMA111 crosses above SMA350_x2
    cross_found = False
    cross_date = None
    
    for i in range(len(future_dates) - 1):
        # Check if SMA111 crosses above SMA350_x2
        if (projected_sma111[i] <= projected_sma350_x2[i] and 
            projected_sma111[i+1] > projected_sma350_x2[i+1]):
            cross_found = True
            cross_date = future_dates[i+1]
            break
        # Check if they're already crossed and will uncross
        elif (projected_sma111[i] > projected_sma350_x2[i] and 
              projected_sma111[i+1] <= projected_sma350_x2[i+1]):
            # They're already crossed, check if they'll uncross (SMA111 goes below)
            cross_found = True
            cross_date = future_dates[i+1]
            break
    
    # Create projection dataframe
    projection_df = pd.DataFrame({
        'Date': future_dates,
        'SMA111': projected_sma111,
        'SMA350_x2': projected_sma350_x2
    })
else:
    # Not enough data for projection
    projection_df = pd.DataFrame(columns=['Date', 'SMA111', 'SMA350_x2'])
    cross_found = False
    cross_date = None

plt.style.use('dark_background')
# Create figure with dark background
fig, ax = plt.subplots(figsize=(20, 10))
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# Set Y-axis to logarithmic scale
ax.set_yscale('log')
ax.set_ylabel('Price (USD)', color='lightgray', fontsize=12)
plotted_y_max = data[['Price', 'SMA111', 'SMA350_x2']].max().max()
if len(projection_df) > 0:
    plotted_y_max = max(plotted_y_max, projection_df[['SMA111', 'SMA350_x2']].max().max())
y_upper = max(200000, plotted_y_max * 1.2)
ax.set_ylim(5000, y_upper)

# Set Y-axis ticks
price_tick_candidates = [5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000]
price_ticks = [tick for tick in price_tick_candidates if tick <= y_upper]
ax.set_yticks(price_ticks)

def format_price_log(x, p):
    if x >= 1000:
        return f'{x/1000:.0f}k'
    else:
        return f'{x:.0f}'

ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_log))
ax.tick_params(axis='y', labelcolor='lightgray', labelsize=10)
ax.tick_params(axis='x', labelcolor='lightgray', labelsize=10)
ax.grid(True, which="major", linestyle='-', alpha=0.1, color='gray')
ax.grid(True, which="minor", linestyle='--', alpha=0.05, color='gray')

# Plot Price (gold line)
ax.plot(data['Date'], data['Price'], color='gold', linewidth=1.5, label='Price (USD)', zorder=10)

# Plot SMA111 (cyan line)
ax.plot(data['Date'], data['SMA111'], color='cyan', linewidth=1.5, label='SMA111d', zorder=9)

# Plot SMA350_x2 (magenta line)
ax.plot(data['Date'], data['SMA350_x2'], color='magenta', linewidth=1.5, label='SMA350d X 2', zorder=8)

# Plot projected lines (dashed)
if len(projection_df) > 0:
    ax.plot(projection_df['Date'], projection_df['SMA111'], 
            color='cyan', linewidth=1.5, linestyle='--', alpha=0.7, zorder=7)
    ax.plot(projection_df['Date'], projection_df['SMA350_x2'], 
            color='magenta', linewidth=1.5, linestyle='--', alpha=0.7, zorder=6)

# Set X-axis limits (from Jan 2020 to Jan 2026 or projection end)
x_min = data['Date'].min()
if len(projection_df) > 0:
    x_max = max(data['Date'].max(), projection_df['Date'].max())
else:
    x_max = data['Date'].max()
ax.set_xlim(x_min, x_max)

# Format X-axis
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))  # Every 6 months
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
ax.set_xlabel('Day', color='lightgray', fontsize=12)

# Keep the legend inside the plot area to avoid savefig clipping.
legend = ax.legend(loc='lower right', bbox_to_anchor=(0.985, 0.035),
                   framealpha=0.9, facecolor='white', edgecolor='black', fontsize=10)
for text in legend.get_texts():
    text.set_color('black')

# Add cross projection annotation
if cross_found and cross_date and len(projection_df) > 0:
    # Find the index of the cross date
    cross_mask = projection_df['Date'] == cross_date
    if cross_mask.any():
        cross_idx = projection_df[cross_mask].index[0]
        if cross_idx < len(projection_df):
            cross_sma111 = projection_df['SMA111'].iloc[cross_idx]
            cross_sma350_x2 = projection_df['SMA350_x2'].iloc[cross_idx]
            cross_y = (cross_sma111 + cross_sma350_x2) / 2
            
            # Format date
            cross_date_str = cross_date.strftime('%b %Y')
            
            annotation_text = f"Projected Cross: {cross_date_str}"
            ax.annotate(annotation_text, 
                       xy=(cross_date, cross_y),
                       xytext=(0.68, 0.20), textcoords='axes fraction',
                       bbox=dict(boxstyle='round', facecolor='yellow', edgecolor='black', alpha=0.9),
                       arrowprops=dict(arrowstyle='->', color='yellow', lw=2),
                       fontsize=10, color='black', zorder=21)
else:
    # No projected cross - keep annotation away from the chart's top-right edge.
    # Position it near the end of the projection lines
    if len(projection_df) > 0:
        annotation_x = projection_df['Date'].iloc[-1]
        annotation_y = (projection_df['SMA111'].iloc[-1] + projection_df['SMA350_x2'].iloc[-1]) / 2
    else:
        annotation_x = data['Date'].iloc[-1]
        annotation_y = (data['SMA111'].iloc[-1] + data['SMA350_x2'].iloc[-1]) / 2
    
    ax.annotate('No Projected Cross', 
               xy=(annotation_x, annotation_y),
               xytext=(0.68, 0.20), textcoords='axes fraction',
               bbox=dict(boxstyle='round', facecolor='green', edgecolor='black', alpha=0.9),
               arrowprops=dict(arrowstyle='->', color='green', lw=2),
               fontsize=10, color='black', zorder=21)

# Adjust layout
plt.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.08)

# Save the chart
output_path = script_dir / 'pi_cycle_top_estimate.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black', 
            pad_inches=0.1, edgecolor='none')
print(f"Pi Cycle Top Future Cross Estimate chart saved to: {output_path}")

# Open the chart
# plt.show()  # Commented out for automation
