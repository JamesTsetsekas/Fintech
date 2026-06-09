#!/usr/bin/env python3
"""
Bitcoin Cycle High Drawdown Chart

Creates a visualization showing Bitcoin's drawdown percentage from cycle highs
over time, comparing multiple historical cycles.

The chart shows:
- X-axis: Days After Cycle High (0-400 days)
- Y-axis: Percentage Drawdown (0% to 100%) and Dollar Values
- Multiple cycles overlaid for comparison
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import requests
import warnings

warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')

# Genesis block date
GENESIS_DATE = datetime(2009, 1, 3)

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
data['Date'] = pd.to_datetime(data['date'], format='%m/%d/%y')
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Price'])

# Filter out zero prices
data = data[data['Price'] > 0].copy()

# Sort by date
data = data.sort_values('Date').reset_index(drop=True)

print(f"Data range: {data['Date'].min()} to {data['Date'].max()}")

# Get current date and block height
current_date = data['Date'].max()
current_block_height = get_block_height_from_mempool()
if current_block_height is None:
    current_block_height = calculate_block_height_fallback(current_date)

# Identify cycle highs (major ATHs)
# We'll identify peaks that are followed by significant drawdowns (>50%)
data['Running_Max'] = data['Price'].expanding().max()
prev_running_max = data['Running_Max'].shift(1).fillna(0)
tolerance = 0.01
data['Is_ATH'] = (data['Running_Max'] - prev_running_max) > tolerance

# Get all ATH dates
ath_dates = data[data['Is_ATH']]['Date'].values

# Define major cycle highs (approximate dates, we'll find closest in data)
# Note: For current cycle, we'll use the most recent high price in the data
cycle_high_dates_target = [
    datetime(2011, 6, 8),    # 2011 cycle high
    datetime(2013, 11, 30),  # 2013-2015 cycle high
    datetime(2017, 12, 17),  # 2017-2018 cycle high
    datetime(2021, 11, 10),  # 2021-2022 cycle high
]

# For current cycle, find the most recent high in the data (within last year)
one_year_ago = current_date - timedelta(days=365)
recent_data = data[(data['Date'] >= one_year_ago) & (data['Date'] <= current_date)]
if len(recent_data) > 0:
    # Find the maximum price point in recent data (current cycle high)
    max_price_idx = recent_data['Price'].idxmax()
    current_cycle_high_date = recent_data.loc[max_price_idx, 'Date']
    cycle_high_dates_target.append(current_cycle_high_date)
    print(f"Current cycle high (from data): {current_cycle_high_date.strftime('%Y-%m-%d')}")

# Find closest dates in data for each cycle high
cycle_highs = []
for target_date in cycle_high_dates_target:
    # Find closest date in data within 30 days
    time_diffs = abs(data['Date'] - target_date)
    closest_idx = time_diffs.idxmin()
    closest_date = data.loc[closest_idx, 'Date']
    closest_price = data.loc[closest_idx, 'Price']
    
    if abs((closest_date - target_date).days) <= 30:
        cycle_highs.append({
            'date': closest_date,
            'price': closest_price,
            'target_date': target_date
        })
        print(f"Found cycle high: {closest_date.strftime('%Y-%m-%d')} at ${closest_price:,.2f} (target: {target_date.strftime('%Y-%m-%d')})")

# Sort cycle highs by date
cycle_highs = sorted(cycle_highs, key=lambda x: x['date'])

if len(cycle_highs) == 0:
    print("ERROR: No cycle highs found in data!")
    print("Available date range:", data['Date'].min(), "to", data['Date'].max())
    raise ValueError("No cycle highs found")

print(f"\nFound {len(cycle_highs)} cycle highs")

# Prepare data for each cycle
cycles_data = []

for i, cycle_high in enumerate(cycle_highs):
    cycle_start_date = cycle_high['date']
    cycle_high_price = cycle_high['price']
    
    # Get data from cycle high onward
    cycle_data = data[data['Date'] >= cycle_start_date].copy()
    
    if len(cycle_data) == 0:
        continue
    
    # Calculate days after cycle high
    cycle_data['Days_After_High'] = (cycle_data['Date'] - cycle_start_date).dt.days
    
    # Calculate drawdown percentage (negative values: 0% at high, -100% at zero price)
    cycle_data['Drawdown_Pct'] = ((cycle_data['Price'] - cycle_high_price) / cycle_high_price) * 100
    
    # Limit to 400 days or until next cycle high (if not the last cycle)
    if i < len(cycle_highs) - 1:
        next_cycle_date = cycle_highs[i + 1]['date']
        cycle_end_date = min(cycle_start_date + timedelta(days=400), next_cycle_date)
        cycle_data = cycle_data[cycle_data['Date'] <= cycle_end_date].copy()
    else:
        # Last cycle - go up to 400 days or current date
        cycle_data = cycle_data[cycle_data['Days_After_High'] <= 400].copy()
    
    # Create date range for label
    start_str = cycle_start_date.strftime('%m/%d/%y')
    if len(cycle_data) > 0:
        end_date = cycle_data['Date'].max()
        end_str = end_date.strftime('%m/%d/%y')
        days_duration = (end_date - cycle_start_date).days
    else:
        end_str = cycle_start_date.strftime('%m/%d/%y')
        days_duration = 0
    
    cycles_data.append({
        'cycle_high': cycle_high,
        'data': cycle_data,
        'label': f"{start_str} - {end_str} ({days_duration} days)",
        'days_duration': days_duration
    })

# Create figure with dark background
fig, ax = plt.subplots(figsize=(20, 12))
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# Define colors for each cycle (matching image description)
cycle_colors = [
    '#FFD700',  # Yellow for 2011 cycle
    '#90EE90',  # Light Green for 2013-2015 cycle
    '#FF69B4',  # Pink/Magenta for 2017-2018 cycle
    '#4169E1',  # Blue for 2021-2022 cycle
    '#FF8C00',  # Orange for 2025 cycle (current)
]

# Plot each cycle
for i, cycle_info in enumerate(cycles_data):
    cycle_data = cycle_info['data']
    color = cycle_colors[i % len(cycle_colors)]
    
    if len(cycle_data) == 0:
        continue
    
    # Use dotted line for current cycle (last one)
    linestyle = '--' if i == len(cycles_data) - 1 else '-'
    linewidth = 2.5
    
    # Plot drawdown line
    ax.plot(cycle_data['Days_After_High'], cycle_data['Drawdown_Pct'],
            color=color, linestyle=linestyle, linewidth=linewidth,
            label=cycle_info['label'], zorder=10 + i)
    
    # Add price annotations at key points
    # Annotate at the final price point (lowest drawdown typically)
    if len(cycle_data) > 0:
        # Use the last point in the cycle data (or minimum drawdown if cycle is complete)
        final_row = cycle_data.iloc[-1]
        final_price = final_row['Price']
        final_days = final_row['Days_After_High']
        final_drawdown = final_row['Drawdown_Pct']
        
        # Also check for minimum drawdown point
        min_idx = cycle_data['Drawdown_Pct'].idxmin()
        min_row = cycle_data.loc[min_idx]
        
        # Use whichever is more meaningful - typically the minimum drawdown
        if abs(min_row['Drawdown_Pct'] - final_drawdown) > 5:  # If significantly different
            annotate_price = min_row['Price']
            annotate_days = min_row['Days_After_High']
            annotate_drawdown = min_row['Drawdown_Pct']
        else:
            annotate_price = final_price
            annotate_days = final_days
            annotate_drawdown = final_drawdown
        
        # Format price for annotation
        if annotate_price >= 1000:
            price_str = f"${annotate_price/1000:.2f}k"
        elif annotate_price >= 1:
            price_str = f"${annotate_price:.2f}"
        else:
            price_str = f"${annotate_price:.4f}"
        
        # Add annotation near the line
        ax.annotate(price_str, 
                   xy=(annotate_days, annotate_drawdown),
                   xytext=(8, 8), textcoords='offset points',
                   fontsize=9, color=color, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='black', edgecolor=color, alpha=0.8),
                   zorder=20)

# Create secondary Y-axis for dollar values
ax2 = ax.twinx()
ax2.set_facecolor('black')

# For dollar values, we need to map from drawdown % to price
# We'll use the current cycle high price as reference for scaling
if len(cycles_data) > 0:
    current_cycle = cycles_data[-1]
    current_cycle_high_price = current_cycle['cycle_high']['price']
    
    # Set dollar value range based on typical cycle high prices
    # We'll use a log scale approach
    max_price = max([c['cycle_high']['price'] for c in cycles_data])
    min_price = min([c['cycle_high']['price'] * 0.1 for c in cycles_data])  # 90% drawdown
    
    # Calculate drawdown range for dollar axis
    # At 0% drawdown: price = cycle_high
    # At 100% drawdown: price = 0
    # We need to show prices for different cycles, so we'll use current cycle as reference
    
    # Format Y-axis (left axis) - drawdown percentage
    ax.set_ylabel('Drawdown (%)', color='white', fontsize=14, fontweight='bold')
    ax.tick_params(axis='y', colors='white', labelsize=10)
    ax.set_ylim(-100, 0)  # -100% at bottom, 0% at top
    
    # Set drawdown percentage ticks
    ax.set_yticks([0, -10, -20, -30, -40, -50, -60, -70, -80, -90, -100])
    ax.set_yticklabels(['0%', '-10%', '-20%', '-30%', '-40%', '-50%', '-60%', '-70%', '-80%', '-90%', '-100%'])
    
    # Right Y-axis will show specific dollar values at key drawdown levels
    # We'll label specific points rather than creating a full scale
    
    # Format X-axis
    ax.set_xlabel('Days After Cycle High', color='white', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 400)
    ax.set_xticks([0, 50, 100, 150, 200, 250, 300, 350, 400])
    ax.tick_params(axis='x', colors='white', labelsize=10)

# Remove spines
for spine in ax.spines.values():
    spine.set_visible(False)
for spine in ax2.spines.values():
    spine.set_visible(False)

# Grid
ax.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.5)
ax.set_axisbelow(True)

# Add horizontal reference line for current cycle drawdown (dotted line across chart)
if len(cycles_data) > 0:
    current_cycle = cycles_data[-1]
    current_cycle_data = current_cycle['data']
    if len(current_cycle_data) > 0:
        current_drawdown = current_cycle_data['Drawdown_Pct'].iloc[-1]
        ax.axhline(y=current_drawdown, color='#FF8C00', linestyle='--', 
                  linewidth=1.5, alpha=0.4, zorder=1, dashes=(5, 5))

# Format right Y-axis to show key drawdown percentages with color-coded labels
ax2.set_ylabel('Drawdown (%)', color='white', fontsize=14, fontweight='bold')
ax2.set_ylim(-100, 0)  # From -100% at bottom to 0% at top
ax2.set_yticks([0, -10, -20, -30, -40, -50, -60, -70, -80, -90, -100])
ax2.set_yticklabels(['0%', '-10%', '-20%', '-30%', '-40%', '-50%', '-60%', '-70%', '-80%', '-90%', '-100%'])
ax2.tick_params(axis='y', colors='white', labelsize=10)

# Add color-coded percentage labels on the right for key cycles
# Find final drawdown for each completed cycle and label on right axis
if len(cycles_data) > 0:
    # Get final drawdowns for labeling
    final_drawdowns = []
    for i, cycle_info in enumerate(cycles_data):
        if len(cycle_info['data']) > 0:
            final_dd = cycle_info['data']['Drawdown_Pct'].iloc[-1]
            final_drawdowns.append({
                'drawdown': final_dd,
                'color': cycle_colors[i % len(cycle_colors)],
                'cycle_num': i
            })
    
    # Label key drawdown percentages on right axis (matching image)
    key_drawdowns = sorted(set([round(dd['drawdown'], 0) for dd in final_drawdowns]), reverse=True)
    for dd_val in key_drawdowns[:5]:  # Top 5 unique values
        # Find which cycle has this drawdown
        matching_cycle = next((dd for dd in final_drawdowns if abs(dd['drawdown'] - dd_val) < 1), None)
        if matching_cycle:
            # Use data coordinates for positioning
            ax2.text(410, dd_val, f' {int(dd_val)}%',
                    color=matching_cycle['color'], fontsize=10, fontweight='bold',
                    verticalalignment='center', horizontalalignment='left',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='black', edgecolor=matching_cycle['color'], alpha=0.8),
                    zorder=25)

# Add legend at top
legend = ax.legend(loc='upper left', fontsize=10, framealpha=0.9, 
                  facecolor='black', edgecolor='white', labelcolor='white')
legend.get_frame().set_linewidth(1.5)

# --- HEADER SECTION ---
header_y = 0.96

# Title
fig.text(0.02, header_y, 'Bitcoin Cycle High Drawdown (Days After Cycle High)',
         fontsize=24, fontweight='bold', color='white',
         verticalalignment='top', horizontalalignment='left')

# Date and Block Height (right side)
date_str = current_date.strftime('%b %d, %Y %H:%M (UTC)')
fig.text(0.98, header_y, date_str,
         fontsize=11, color='white',
         verticalalignment='top', horizontalalignment='right')
fig.text(0.98, header_y - 0.02, f'Block Height: {current_block_height:,}',
         fontsize=10, color='white',
         verticalalignment='top', horizontalalignment='right')

# Add a font-safe Bitcoin label.
fig.text(0.02, header_y - 0.02, 'BTC',
         fontsize=12, color='#F7931A',
         verticalalignment='top', horizontalalignment='left')


# Adjust layout
plt.subplots_adjust(left=0.08, right=0.95, top=0.94, bottom=0.06)

# Save the chart
output_path = script_dir / 'cycle_high_drawdown.png'
try:
    plt.savefig(output_path, dpi=150, facecolor='black', bbox_inches='tight', pad_inches=0.2)
    print(f"\nChart saved as '{output_path}'")
    print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
    print(f"Block Height: {current_block_height:,}")
    print(f"Cycles plotted: {len(cycles_data)}")
    for i, cycle_info in enumerate(cycles_data):
        if len(cycle_info['data']) > 0:
            current_dd = cycle_info['data']['Drawdown_Pct'].iloc[-1]
            print(f"  {cycle_info['label']}: Current drawdown {current_dd:.1f}%")
except Exception as e:
    print(f"Error saving chart: {e}")
    import traceback
    traceback.print_exc()
    raise

plt.close(fig)
print("Cycle High Drawdown chart generated successfully!")
