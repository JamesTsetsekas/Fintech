#!/usr/bin/env python3
"""
Epoch-Over-Epoch (EOE) Growth Chart

Creates a visualization showing Bitcoin's price history across epochs (halving cycles)
with color-coded EOE Growth percentages.

The chart shows:
- Stacked area chart of epochs (E1-E5)
- X-axis: Epoch Block Count (0-210,000)
- Y-axis: Price on logarithmic scale
- Color gradient based on EOE Growth percentage
- Legend showing growth percentages
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime
from pathlib import Path
import warnings
import requests

# Suppress urllib3 OpenSSL warning (harmless compatibility warning)
warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')

# Genesis block date
GENESIS_DATE = datetime(2009, 1, 3)

# Epoch definitions (210,000 blocks per epoch)
EPOCHS = {
    1: {'block_start': 0, 'block_end': 210000},
    2: {'block_start': 210000, 'block_end': 420000},
    3: {'block_start': 420000, 'block_end': 630000},
    4: {'block_start': 630000, 'block_end': 840000},
    5: {'block_start': 840000, 'block_end': 1050000},
}

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
    blocks_per_day = 144
    return int(days_since_genesis * blocks_per_day)

# Load data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'

try:
    data = pd.read_csv(dataset_path)
    print(f"Loaded {len(data)} rows from {dataset_path}")
except Exception as e:
    print(f"Error loading data: {e}")
    raise

# Convert dates and prices
data['Date'] = pd.to_datetime(data['date'])
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data['Epoch'] = pd.to_numeric(data['epoch'], errors='coerce')
data['Epoch_Height'] = pd.to_numeric(data['epoch_height'], errors='coerce')
data['Block_Height'] = pd.to_numeric(data['block_height'], errors='coerce')

# Filter out zero prices (early days when Bitcoin wasn't valued)
data = data[data['Price'] > 0].copy()

# Sort by date
data = data.sort_values('Date').reset_index(drop=True)

print(f"Data range: {data['Date'].min()} to {data['Date'].max()}")
print(f"Epochs in data: {sorted(data['Epoch'].unique())}")

# Get current data
current_date = data['Date'].max()
current_row = data[data['Date'] == current_date].iloc[0]
current_price = current_row['Price']
current_epoch = int(current_row['Epoch'])
current_epoch_height = int(current_row['Epoch_Height'])
current_block_height = int(current_row['Block_Height'])

# Get block height (use API if available)
block_height = get_block_height_from_mempool()
if block_height is None:
    block_height = calculate_block_height_fallback(current_date)

# Calculate epoch start prices and EOE Growth
epoch_start_prices = {}
for epoch in sorted(data['Epoch'].unique()):
    epoch_data = data[data['Epoch'] == epoch].copy()
    if len(epoch_data) > 0:
        epoch_data = epoch_data.sort_values('Date')
        epoch_start_prices[epoch] = epoch_data.iloc[0]['Price']
        print(f"Epoch {int(epoch)} start price: ${epoch_start_prices[epoch]:,.2f}")

# Calculate EOE Growth for each data point
# EOE Growth = (current_price / previous_epoch_start_price - 1) * 100
def calculate_eoe_growth(row):
    epoch = row['Epoch']
    price = row['Price']
    
    # For epoch 1, compare to a baseline (use first non-zero price)
    if epoch == 1:
        # Use a very small baseline for epoch 1 to show massive growth
        baseline = data[data['Epoch'] == 1].iloc[0]['Price']
        if baseline > 0 and price > 0:
            growth = ((price / baseline) - 1) * 100
            return growth
        return 0
    
    # For other epochs, compare to previous epoch's start price
    prev_epoch = epoch - 1
    if prev_epoch in epoch_start_prices:
        prev_start_price = epoch_start_prices[prev_epoch]
        if prev_start_price > 0 and price > 0:
            growth = ((price / prev_start_price) - 1) * 100
            return growth
    
    return 0

data['EOE_Growth'] = data.apply(calculate_eoe_growth, axis=1)

# Cap extreme growth values for visualization
# Replace infinity and very large values with a max cap
max_growth_display = 100000000  # 100M%
data['EOE_Growth_Display'] = data['EOE_Growth'].clip(upper=max_growth_display)

# Create figure with dark background
fig, ax = plt.subplots(figsize=(20, 12))
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# Set logarithmic scale for Y-axis
ax.set_yscale('log')

# Create color map for EOE Growth
# From the image: Dark Purple (≥100M%) -> Purple (10M%) -> Blue (1M%) -> 
# Light Blue/Cyan (100K%) -> Yellow (10K%) -> Orange (1K%) -> Red (100%) -> Dark Red (≤10%)
growth_colors = [
    '#1a0033',  # Dark Purple (≥100,000,000%)
    '#4a0080',  # Purple (10,000,000%)
    '#0066ff',  # Blue (1,000,000%)
    '#00ccff',  # Light Blue/Cyan (100,000%)
    '#ffff00',  # Yellow (10,000%)
    '#ff8800',  # Orange (1,000%)
    '#ff0000',  # Red (100%)
    '#8b0000',  # Dark Red (≤10%)
]

# Define growth thresholds for color mapping (log scale)
growth_thresholds = [10, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000]

# Create colormap using log scale normalization
from matplotlib.colors import BoundaryNorm
norm = BoundaryNorm(growth_thresholds + [float('inf')], len(growth_colors))
cmap = LinearSegmentedColormap.from_list('eoe_growth', growth_colors, N=256)

# Prepare data for stacking
# We'll create filled areas for each epoch, stacked on top of each other
max_epoch = int(data['Epoch'].max())

# Create a grid for epoch_height (0-210000) to ensure consistent x-values
epoch_height_grid = np.arange(0, 210001, 50)  # 50 block steps for better detail

# Collect epoch data
epoch_plots = []

for epoch in sorted(data['Epoch'].unique()):
    epoch = int(epoch)
    epoch_data = data[data['Epoch'] == epoch].copy()
    epoch_data = epoch_data.sort_values('Epoch_Height')
    
    if len(epoch_data) == 0:
        continue
    
    # Interpolate to grid
    epoch_heights = epoch_data['Epoch_Height'].values
    prices = epoch_data['Price'].values
    eoe_growths = epoch_data['EOE_Growth_Display'].values
    
    # Filter grid to epoch range
    epoch_max_height = min(epoch_data['Epoch_Height'].max(), 210000)
    epoch_grid = epoch_height_grid[epoch_height_grid <= epoch_max_height]
    
    # Interpolate prices and growth values
    grid_prices = np.interp(epoch_grid, epoch_heights, prices, left=prices[0] if len(prices) > 0 else 0, right=prices[-1] if len(prices) > 0 else 0)
    grid_growths = np.interp(epoch_grid, epoch_heights, eoe_growths, left=eoe_growths[0] if len(eoe_growths) > 0 else 0, right=eoe_growths[-1] if len(eoe_growths) > 0 else 0)
    
    # Calculate bottom prices (price at same epoch_height in previous epoch)
    bottom_prices = np.zeros_like(epoch_grid)
    
    if epoch == 1:
        # For epoch 1, bottom is at a minimum price floor
        min_price = max(data['Price'].min() * 0.01, 0.0001)
        bottom_prices = np.full_like(epoch_grid, min_price)
    else:
        # For other epochs, find the price at same epoch_height in previous epoch
        prev_epoch = epoch - 1
        prev_epoch_data = data[data['Epoch'] == prev_epoch].copy()
        prev_epoch_data = prev_epoch_data.sort_values('Epoch_Height')
        
        if len(prev_epoch_data) > 0:
            prev_heights = prev_epoch_data['Epoch_Height'].values
            prev_prices = prev_epoch_data['Price'].values
            
            # Get the last price of previous epoch (the price at epoch boundary)
            prev_epoch_end_price = prev_prices[-1] if len(prev_prices) > 0 else epoch_start_prices.get(prev_epoch, 0)
            
            # For stacking, bottom should be the maximum price reached in previous epochs at this x-position
            # Since epochs are sequential, we use the end price of previous epoch as baseline
            # But actually, we want to show each epoch starting from where previous ended
            for i, x in enumerate(epoch_grid):
                # Find the price in previous epoch at the same epoch_height
                if x < len(prev_heights):
                    if x <= prev_heights[-1]:
                        # Interpolate from previous epoch data
                        prev_price = np.interp(x, prev_heights, prev_prices, left=prev_prices[0] if len(prev_prices) > 0 else 0, right=prev_epoch_end_price)
                        bottom_prices[i] = prev_price
                    else:
                        bottom_prices[i] = prev_epoch_end_price
                else:
                    bottom_prices[i] = prev_epoch_end_price
        else:
            # No previous epoch data, use epoch start price
            bottom_prices = np.full_like(epoch_grid, epoch_start_prices.get(epoch, 0))
    
    epoch_plots.append({
        'epoch': epoch,
        'x': epoch_grid,
        'y': grid_prices,
        'bottom': bottom_prices,
        'growth': grid_growths
    })

# Plot each epoch as a filled area with gradient colors
for epoch_plot in epoch_plots:
    x = epoch_plot['x']
    y = epoch_plot['y']
    bottom = epoch_plot['bottom']
    growth = epoch_plot['growth']
    epoch = epoch_plot['epoch']
    
    # Ensure bottom is never above y (for log scale safety)
    bottom = np.maximum(bottom, y * 0.5)  # Bottom should be at least 50% of y
    
    # Create segments with gradient colors
    # Use steps for performance and smooth color transitions
    step = max(1, len(x) // 1500)
    
    for i in range(0, len(x) - 1, step):
        end_idx = min(i + step, len(x) - 1)
        
        x_seg = x[i:end_idx+1]
        y_seg = y[i:end_idx+1]
        bottom_seg = bottom[i:end_idx+1]
        growth_seg = growth[i:end_idx+1]
        
        # Use average growth for color
        avg_growth = np.mean(growth_seg)
        
        # Normalize growth for colormap (use log scale)
        if avg_growth <= 10:
            norm_val = 0.0
        elif avg_growth >= 100000000:
            norm_val = 1.0
        else:
            # Log scale normalization
            log_growth = np.log10(max(avg_growth, 10))
            log_min = np.log10(10)
            log_max = np.log10(100000000)
            norm_val = (log_growth - log_min) / (log_max - log_min)
        
        color = cmap(norm_val)
        
        # Fill area
        ax.fill_between(x_seg, bottom_seg, y_seg, color=color, alpha=0.85, linewidth=0, zorder=epoch)
    
    # Draw white line on top boundary of epoch
    ax.plot(x, y, color='white', linewidth=1.5, zorder=max_epoch + 10, alpha=0.95)

# Draw white lines for epoch boundaries (vertical lines at epoch transitions)
for epoch in sorted(data['Epoch'].unique())[:-1]:
    epoch = int(epoch)
    epoch_data = data[data['Epoch'] == epoch].copy()
    if len(epoch_data) > 0:
        epoch_data = epoch_data.sort_values('Epoch_Height')
        max_height = min(epoch_data['Epoch_Height'].max(), 210000)
        # Draw vertical line at epoch boundary
        ax.axvline(x=max_height, color='white', linewidth=2, linestyle='-', alpha=0.9, zorder=max_epoch + 15)

# Format X-axis (Epoch Block Count)
ax.set_xlabel('Epoch Block Count', color='white', fontsize=14, fontweight='bold')
ax.set_xlim(0, 210000)
ax.set_xticks([0, 30000, 60000, 90000, 120000, 150000, 180000, 210000])
ax.set_xticklabels(['0', '30k', '60k', '90k', '120k', '150k', '180k', '210k'], color='white', fontsize=10)

# Format Y-axis (Price - logarithmic scale)
ax.set_ylabel('Price (BTCUSD)', color='white', fontsize=14, fontweight='bold')

# Set Y-axis ticks based on image
price_ticks = [
    0.0001,  # "Not Valued (E1)"
    0.001,   # 0.1¢
    0.01,    # 1¢
    0.1,     # 10¢
    1,       # $1
    10,      # $10 (E2)
    100,     # $100
    1000,    # $1k (E3)
    10000,   # $10k (E4)
    100000,  # $100k (E5)
    1000000, # $1M
    10000000 # $10M
]

def format_price_tick(x, pos):
    if x < 0.001:
        return 'Not Valued\n(E1)'
    elif x < 1:
        return f'{x*100:.1f}¢'
    elif x < 1000:
        return f'${x:.0f}'
    elif x < 1000000:
        return f'${x/1000:.0f}k'
    else:
        return f'${x/1000000:.0f}M'

ax.set_yticks(price_ticks)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price_tick))
ax.set_ylim(0.00005, 20000000)

# Remove spines
for spine in ax.spines.values():
    spine.set_visible(False)

# Grid
ax.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.5)
ax.tick_params(colors='white', labelsize=10)

# Add color legend on the right side
cax = fig.add_axes([0.92, 0.15, 0.02, 0.7])  # [left, bottom, width, height]
cax.set_facecolor('black')

# Create legend labels
legend_labels = [
    '≥100,000,000%',
    '10,000,000%',
    '1,000,000%',
    '100,000%',
    '10,000%',
    '1,000%',
    '100%',
    '≤10%'
]

# Create custom colorbar
sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=1))
sm.set_array([])

# Add vertical colorbar with custom labels
cbar = plt.colorbar(sm, cax=cax, orientation='vertical')
cbar.set_label('EOE Growth', color='white', fontsize=12, fontweight='bold', labelpad=15)

# Set custom tick positions and labels
tick_positions = np.linspace(0, 1, len(legend_labels))
cbar.set_ticks(tick_positions)
cbar.set_ticklabels(legend_labels)
cbar.ax.tick_params(colors='white', labelsize=9, length=5)

# Calculate current epoch metrics
current_epoch_data = data[data['Epoch'] == current_epoch].copy()
current_epoch_start_price = epoch_start_prices[current_epoch]

# Calculate EOE Growth for current epoch
if current_epoch > 1:
    prev_epoch = current_epoch - 1
    prev_epoch_start_price = epoch_start_prices[prev_epoch]
    eoe_growth = ((current_price / prev_epoch_start_price) - 1) * 100
else:
    baseline = data[data['Epoch'] == 1].iloc[0]['Price']
    eoe_growth = ((current_price / baseline) - 1) * 100 if baseline > 0 else 0

# Calculate epoch 4 end price (for header - shown as "Epoch 4 Price")
epoch_4_data = data[data['Epoch'] == 4].copy()
if len(epoch_4_data) > 0:
    epoch_4_data = epoch_4_data.sort_values('Date')
    epoch_4_end_price = epoch_4_data.iloc[-1]['Price']
else:
    epoch_4_end_price = epoch_start_prices.get(4, 0)

# --- HEADER SECTION ---
header_y = 0.96
header_height = 0.04

# Title
fig.text(0.02, header_y, 'Epoch-Over-Epoch (EOE) Growth',
         fontsize=24, fontweight='bold', color='white',
         verticalalignment='top', horizontalalignment='left')

# Date and Block Height (right side)
date_str = current_date.strftime('%b %d, %Y')
fig.text(0.98, header_y, date_str,
         fontsize=11, color='white',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.98, header_y - 0.02, f'Block Height: {current_block_height:,}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='right')

# Metrics
metrics_y = header_y - 0.04
fig.text(0.02, metrics_y, f'Epoch: {current_epoch}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='left')

# Calculate epoch block count (current epoch's height)
epoch_block_count = current_epoch_height
fig.text(0.12, metrics_y, f'Epoch Block Count: {epoch_block_count:,}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='left')

# Show epoch prices based on current epoch
if current_epoch == 5:
    # For epoch 5, show epoch 4 end price and epoch 5 current price
    fig.text(0.32, metrics_y, f'Epoch 4 Price: ${epoch_4_end_price:,.2f}',
             fontsize=10, color='white',
             verticalalignment='top', horizontalalignment='left')
    
    fig.text(0.52, metrics_y, f'Epoch 5 Price: ${current_price:,.2f}',
             fontsize=10, color='white',
             verticalalignment='top', horizontalalignment='left')
    
    fig.text(0.72, metrics_y, f'EOE Growth: {eoe_growth:.1f}%',
             fontsize=10, color='white', fontweight='bold',
             verticalalignment='top', horizontalalignment='left')
else:
    # For other epochs, show current epoch price
    fig.text(0.32, metrics_y, f'Epoch {current_epoch} Price: ${current_price:,.2f}',
             fontsize=10, color='white',
             verticalalignment='top', horizontalalignment='left')
    
    if current_epoch > 1:
        fig.text(0.52, metrics_y, f'EOE Growth: {eoe_growth:.1f}%',
                 fontsize=10, color='white', fontweight='bold',
                 verticalalignment='top', horizontalalignment='left')

# --- FOOTER SECTION ---
# Footer branding removed

# Adjust layout manually (tight_layout doesn't work well with manually positioned colorbar)
plt.subplots_adjust(left=0.08, right=0.89, top=0.96, bottom=0.03)

# Save the chart
output_path = script_dir / 'eoe_growth.png'
try:
    plt.savefig(output_path, dpi=150, facecolor='black', bbox_inches='tight', pad_inches=0.2)
    print(f"\nChart saved as '{output_path}'")
    print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
    print(f"Current Price: ${current_price:,.2f}")
    print(f"Current Epoch: {current_epoch}")
    print(f"Current Epoch Height: {current_epoch_height:,}")
    print(f"Block Height: {current_block_height:,}")
    print(f"EOE Growth: {eoe_growth:.1f}%")
except Exception as e:
    print(f"Error saving chart: {e}")
    import traceback
    traceback.print_exc()
    raise

plt.close(fig)
print("EOE Growth chart generated successfully!")

