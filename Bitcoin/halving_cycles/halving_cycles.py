#!/usr/bin/env python3
"""
Bitcoin Halving Cycles Chart (Block Height Aligned)

Creates a visualization showing Bitcoin's price performance across different halving cycles,
normalized by block height alignment.

The chart shows:
- Multiple halving cycles (E2-E5) as colored lines
- Price multiples on logarithmic scale (1x to 100x)
- Halving progress (0% to 100%) aligned by block height
- Starting prices for each cycle on left Y-axis
- Secondary X-axis showing block heights
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from datetime import datetime
from pathlib import Path
import requests
import warnings

warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')

# Genesis block date
GENESIS_DATE = datetime(2009, 1, 3)

# Halving cycles (epochs) - 210,000 blocks per cycle
# E2 starts at block 210,000 (first halving)
# E3 starts at block 420,000 (second halving)
# E4 starts at block 630,000 (third halving)
# E5 starts at block 840,000 (fourth halving)
HALVING_CYCLES = {
    2: {'block_start': 210000, 'block_end': 420000},
    3: {'block_start': 420000, 'block_end': 630000},
    4: {'block_start': 630000, 'block_end': 840000},
    5: {'block_start': 840000, 'block_end': 1050000},
}

# Cycle colors (matching the example image)
CYCLE_COLORS = {
    2: '#90EE90',  # Light green
    3: '#FF69B4',  # Pink/magenta
    4: '#4169E1',  # Blue
    5: '#FF8C00',  # Orange
}

CYCLE_NAMES = {
    2: 'E2',
    3: 'E3',
    4: 'E4',
    5: 'E5',
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
data['Block_Height'] = pd.to_numeric(data['block_height'], errors='coerce')
data['Epoch'] = pd.to_numeric(data['epoch'], errors='coerce')

# Filter out zero prices (early days when Bitcoin wasn't valued)
data = data[data['Price'] > 0].copy()

# Sort by date
data = data.sort_values('Date').reset_index(drop=True)

print(f"Data range: {data['Date'].min()} to {data['Date'].max()}")

# Get current data
current_date = data['Date'].max()
current_row = data[data['Date'] == current_date].iloc[0]
current_price = current_row['Price']
current_block_height = int(current_row['Block_Height'])

# Get block height (use API if available)
block_height = get_block_height_from_mempool()
if block_height is None:
    block_height = calculate_block_height_fallback(current_date)
else:
    # Use API value if available
    current_block_height = block_height

print(f"Current block height: {current_block_height:,}")

# Calculate cycle start prices and prepare data for each cycle
cycle_data = {}
for cycle_num, cycle_info in HALVING_CYCLES.items():
    cycle_start_block = cycle_info['block_start']
    cycle_end_block = cycle_info['block_end']
    
    # Get data for this cycle
    cycle_rows = data[
        (data['Block_Height'] >= cycle_start_block) & 
        (data['Block_Height'] <= min(cycle_end_block, current_block_height))
    ].copy()
    
    if len(cycle_rows) == 0:
        continue
    
    # Sort by block height
    cycle_rows = cycle_rows.sort_values('Block_Height').reset_index(drop=True)
    
    # Get starting price (first price in cycle)
    cycle_start_price = cycle_rows.iloc[0]['Price']
    
    # Calculate halving progress and price multiples
    cycle_rows['Halving_Progress'] = ((cycle_rows['Block_Height'] - cycle_start_block) / 210000) * 100
    cycle_rows['Price_Multiple'] = cycle_rows['Price'] / cycle_start_price
    
    cycle_data[cycle_num] = {
        'start_block': cycle_start_block,
        'end_block': cycle_end_block,
        'start_price': cycle_start_price,
        'data': cycle_rows,
        'current_multiple': cycle_rows.iloc[-1]['Price_Multiple'] if len(cycle_rows) > 0 else 1.0
    }
    
    print(f"Cycle {cycle_num} (E{cycle_num}): Start block {cycle_start_block:,}, Start price ${cycle_start_price:,.2f}, Current multiple: {cycle_data[cycle_num]['current_multiple']:.2f}x")

# Create figure with dark background
fig, ax = plt.subplots(figsize=(20, 12))
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# Create secondary x-axis for block heights
ax2 = ax.twiny()

# Plot each cycle
for cycle_num in sorted(cycle_data.keys()):
    cycle_info = cycle_data[cycle_num]
    cycle_df = cycle_info['data']
    
    # Get halving progress and price multiples
    halving_progress = cycle_df['Halving_Progress'].values
    price_multiples = cycle_df['Price_Multiple'].values
    
    # Plot the line
    color = CYCLE_COLORS[cycle_num]
    label = f"{CYCLE_NAMES[cycle_num]} ({cycle_info['current_multiple']:.1f}x)"
    
    ax.plot(halving_progress, price_multiples, 
            color=color, linewidth=2.5, label=label, zorder=cycle_num + 10)

# Set logarithmic scale for Y-axis (price multiples)
ax.set_yscale('log')

# Format X-axis (Halving Progress - primary, bottom)
ax.set_xlabel('Halving Progress (Block Height Aligned)', color='white', fontsize=14, fontweight='bold')
ax.set_xlim(0, 100)
ax.set_xticks(range(0, 101, 10))
ax.set_xticklabels([f'{i}%' for i in range(0, 101, 10)], color='white', fontsize=10)

# Format secondary X-axis (Block Heights - top)
# Show block heights for current cycle (E5) and next cycle (E6)
current_cycle_start = HALVING_CYCLES[5]['block_start']
current_cycle_end = HALVING_CYCLES[5]['block_end']
next_cycle_start = HALVING_CYCLES[5]['block_end']

# Calculate block height positions for secondary axis
block_height_ticks = []
block_height_labels = []
for i in range(6):
    block_height = current_cycle_start + (i * 21000)  # Every 10% of cycle = 21,000 blocks
    if block_height <= next_cycle_start + 21000:  # Include a bit beyond next cycle
        block_height_ticks.append(((block_height - current_cycle_start) / 210000) * 100)
        if block_height < 1000000:
            block_height_labels.append(f'{int(block_height):,}')
        else:
            block_height_labels.append(f'{block_height/1000:.0f}k')
    
ax2.set_xlim(0, 100)
ax2.set_xticks(block_height_ticks)
ax2.set_xticklabels(block_height_labels, color='white', fontsize=9)
ax2.tick_params(colors='white', labelsize=9)
ax2.spines['top'].set_color('white')
ax2.spines['top'].set_visible(True)

# Format Y-axis (Price Multiples - right side, logarithmic)
ax.set_ylabel('Price Multiple', color='white', fontsize=14, fontweight='bold', labelpad=20)

# Set Y-axis ticks based on example: 1x, 2x, 5x, 10x, 20x, 50x, 100x
multiply_ticks = [1, 2, 5, 10, 20, 50, 100]
ax.set_yticks(multiply_ticks)
ax.set_yticklabels([f'{x}x' for x in multiply_ticks], color='white', fontsize=11)
ax.set_ylim(0.8, 120)

# Add left Y-axis for starting prices (reference markers)
# Draw horizontal dotted lines at 1x (where each cycle starts)
# Each cycle starts at 1x its starting price, so we draw at y=1
for cycle_num in sorted(cycle_data.keys()):
    color = CYCLE_COLORS[cycle_num]
    # Draw horizontal dotted line at 1x (all cycles start here)
    ax.axhline(y=1, color=color, linestyle='--', linewidth=1.5, alpha=0.6, zorder=1)

# Create left Y-axis for starting prices (reference only)
# Use a simpler approach: just add text labels at y=1 for each cycle
# Get starting prices for each cycle
starting_prices = [cycle_data[c]['start_price'] for c in sorted(cycle_data.keys())]

# Add starting price labels on the left side at y=1
# Each cycle's starting price corresponds to 1x multiple
y_label_position = 1.0
for i, cycle_num in enumerate(sorted(cycle_data.keys())):
    start_price = cycle_data[cycle_num]['start_price']
    color = CYCLE_COLORS[cycle_num]
    
    # Format label
    if start_price >= 1000:
        label = f"${start_price/1000:.1f}k"
    else:
        label = f"${start_price:.0f}"
    
    # Add label on the left side at y=1, slightly offset vertically to avoid overlap
    offset_multiple = 0.03 * (i - len(cycle_data) / 2 + 0.5)  # Small offset
    label_y = y_label_position * (1 + offset_multiple)
    
    # Use data coordinates for y, axes fraction for x (left side)
    # Use a custom transform: y in data coords, x in axes fraction
    from matplotlib.transforms import blended_transform_factory
    trans = blended_transform_factory(fig.transFigure, ax.transData)
    ax.text(0.07, label_y, label, color=color, fontsize=9, 
            verticalalignment='center', horizontalalignment='right', fontweight='bold',
            transform=trans)

# Remove spines from main axes
for spine in ax.spines.values():
    spine.set_visible(False)

# Grid
ax.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.5)
ax.tick_params(colors='white', labelsize=10)

# Legend
legend = ax.legend(loc='upper left', fontsize=11, framealpha=0.9, 
                  facecolor='black', edgecolor='white', labelcolor='white')
legend.get_frame().set_linewidth(1)

# --- HEADER SECTION ---
header_y = 0.96

# Bitcoin logo/title (left side)
fig.text(0.02, header_y, 'bitcoin',
         fontsize=24, fontweight='bold', color='white',
         verticalalignment='top', horizontalalignment='left')

# Title
fig.text(0.15, header_y, 'Bitcoin Halving Cycles (Block Height Aligned)',
         fontsize=20, fontweight='bold', color='white',
         verticalalignment='top', horizontalalignment='left')

# Date and Block Height (right side)
date_str = current_date.strftime('%b %d, %Y %H:%M (UTC)')
fig.text(0.98, header_y, date_str,
         fontsize=11, color='white',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.98, header_y - 0.02, f'Block Height: {current_block_height:,}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='right')

# Add current cycle info
current_cycle = 5  # E5 is current
if current_cycle in cycle_data:
    current_progress = ((current_block_height - cycle_data[current_cycle]['start_block']) / 210000) * 100
    current_multiple = cycle_data[current_cycle]['current_multiple']
    
    info_y = header_y - 0.04
    fig.text(0.02, info_y, f"E{current_cycle}: {current_progress:.1f}% Progress, {current_multiple:.1f}x Multiple",
             fontsize=10, color=CYCLE_COLORS[current_cycle],
             verticalalignment='top', horizontalalignment='left')


# Adjust layout
plt.subplots_adjust(left=0.08, right=0.92, top=0.92, bottom=0.08)

# Save the chart
output_path = script_dir / 'halving_cycles.png'
try:
    plt.savefig(output_path, dpi=150, facecolor='black', bbox_inches='tight', pad_inches=0.2)
    print(f"\nChart saved as '{output_path}'")
    print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
    print(f"Current Price: ${current_price:,.2f}")
    print(f"Block Height: {current_block_height:,}")
    print("\nCycle Summary:")
    for cycle_num in sorted(cycle_data.keys()):
        cycle_info = cycle_data[cycle_num]
        print(f"  {CYCLE_NAMES[cycle_num]}: Start ${cycle_info['start_price']:,.2f}, Current {cycle_info['current_multiple']:.2f}x")
except Exception as e:
    print(f"Error saving chart: {e}")
    import traceback
    traceback.print_exc()
    raise

plt.close(fig)
print("Halving cycles chart generated successfully!")

