#!/usr/bin/env python3
"""
Modeled HODL Waves Price Chart

Creates a proxy visualization estimating Bitcoin supply by holding duration
(HODL waves) over time, with the Bitcoin price overlaid. Real HODL waves
require UTXO age data that is not available in the repo-local CSV files.

The chart shows:
- Stacked area chart of modeled HODL waves (supply distribution by age bands)
- Bitcoin price line overlaid on the chart
- Key metrics including percentage mined, block height, current price, etc.
- Legend showing different HODL duration bands
- Current distribution summary (Short, Medium, Long Term)
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Genesis block date
GENESIS_DATE = datetime(2009, 1, 3)

# Halving dates (approximate)
HALVINGS = [
    {'block': 210000, 'date': datetime(2012, 11, 28), 'label': '1st Halving'},
    {'block': 420000, 'date': datetime(2016, 7, 9), 'label': '2nd Halving'},
    {'block': 630000, 'date': datetime(2020, 5, 11), 'label': '3rd Halving'},
    {'block': 840000, 'date': datetime(2024, 4, 20), 'label': '4th Halving'},
]

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

def get_hodl_waves_data_from_api():
    """Attempt to fetch HODL wave data from public API"""
    # Try multiple APIs that might have HODL wave data
    apis = [
        {
            'url': 'https://api.glassnode.com/v1/metrics/supply/hodl_waves',
            'params': {'a': 'BTC', 'i': '1d'},
            'headers': {}  # Some require API key
        },
    ]
    
    # For now, return None to use approximation
    # This would require API keys for most services
    return None

def approximate_hodl_waves(dates, prices, supply_data):
    """
    Approximate HODL waves based on price movements and supply.
    This is a simplified model - real HODL waves require UTXO age data.
    """
    print("Generating modeled HODL waves proxy data...")
    
    # HODL wave bands (in days)
    bands = [
        {'name': 'Less than 1 Day', 'min': 0, 'max': 1},
        {'name': '1 Day - 1 Week', 'min': 1, 'max': 7},
        {'name': '1 Week - 1 Month', 'min': 7, 'max': 30},
        {'name': '1 Month - 3 Months', 'min': 30, 'max': 90},
        {'name': '3 Months - 6 Months', 'min': 90, 'max': 180},
        {'name': '6 Months - 1 Year', 'min': 180, 'max': 365},
        {'name': '1 Year - 2 Years', 'min': 365, 'max': 730},
        {'name': '2 Years - 3 Years', 'min': 730, 'max': 1095},
        {'name': '3 Years - 5 Years', 'min': 1095, 'max': 1825},
        {'name': '5 Years - 7 Years', 'min': 1825, 'max': 2555},
        {'name': '7 Years - 10 Years', 'min': 2555, 'max': 3650},
        {'name': '10 Years - 15 Years', 'min': 3650, 'max': 5475},
        {'name': '15 Years - 20 Years', 'min': 5475, 'max': 7300},
        {'name': 'More than 20 Years', 'min': 7300, 'max': float('inf')},
    ]
    
    # Initialize results
    hodl_data = {}
    for band in bands:
        hodl_data[band['name']] = []
    
    # Calculate network age at each date
    # Convert GENESIS_DATE to pandas Timestamp for proper date arithmetic with numpy datetime64
    genesis_ts = pd.Timestamp(GENESIS_DATE)
    # Handle both pandas Timestamp and numpy datetime64
    network_ages = [(pd.Timestamp(date) - genesis_ts).days for date in dates]
    
    # Approximate HODL waves using a model based on:
    # - Recent activity increases short-term holdings
    # - Long-term holders accumulate over time
    # - Price volatility affects short-term movements
    
    for i, (date, price, supply) in enumerate(zip(dates, prices, supply_data)):
        network_age = network_ages[i]
        
        # Calculate price volatility (30-day rolling)
        if i >= 30:
            recent_prices = prices[max(0, i-30):i+1]
            if len(recent_prices) > 1:
                price_mean = np.mean(recent_prices)
                if price_mean > 0:
                    volatility = np.std(recent_prices) / price_mean
                else:
                    volatility = 0.1
            else:
                volatility = 0.1
        else:
            volatility = 0.1
        
        # Model: higher volatility = more short-term activity
        short_term_multiplier = min(1.0, 0.3 + volatility * 2)
        
        # Distribute supply across bands (simplified model)
        total_distributed = 0
        band_values = {}
        
        # Short term (0-1 year)
        if network_age >= 365:
            # Short term: 30-50% typically, varies with volatility
            short_term_pct = 0.35 + (volatility - 0.05) * 0.3
            short_term_pct = max(0.20, min(0.50, short_term_pct))
        else:
            short_term_pct = 0.95  # Very early, most coins are short-term
        
        # Distribute short-term bands
        short_bands = ['Less than 1 Day', '1 Day - 1 Week', '1 Week - 1 Month', 
                      '1 Month - 3 Months', '3 Months - 6 Months', '6 Months - 1 Year']
        short_weights = [0.05, 0.05, 0.15, 0.25, 0.20, 0.30]
        short_total = supply * short_term_pct
        
        # Initialize all short-term bands
        for band_name in short_bands:
            band_idx = next((i for i, b in enumerate(bands) if b['name'] == band_name), None)
            if band_idx is not None and network_age >= bands[band_idx]['min']:
                weight_idx = short_bands.index(band_name)
                value = short_total * short_weights[weight_idx]
                band_values[band_name] = value
                total_distributed += value
            else:
                band_values[band_name] = 0.0
        
        # Medium term (1-5 years)
        if network_age >= 1825:
            medium_pct = 0.25
        elif network_age >= 365:
            # Medium term increases as network ages
            medium_pct = 0.15 + (network_age - 365) / 1825 * 0.10
        else:
            medium_pct = 0.05
        
        medium_bands = ['1 Year - 2 Years', '2 Years - 3 Years', '3 Years - 5 Years']
        medium_weights = [0.40, 0.20, 0.40]
        medium_total = supply * medium_pct
        
        # Initialize all medium-term bands
        for band_name in medium_bands:
            band_idx = next((i for i, b in enumerate(bands) if b['name'] == band_name), None)
            if band_idx is not None and network_age >= bands[band_idx]['min']:
                weight_idx = medium_bands.index(band_name)
                value = medium_total * medium_weights[weight_idx]
                band_values[band_name] = value
                total_distributed += value
            else:
                band_values[band_name] = 0.0
        
        # Long term (5+ years)
        if network_age >= 1825:
            long_pct = 1.0 - short_term_pct - medium_pct
        else:
            long_pct = 0.0
        
        long_bands = ['5 Years - 7 Years', '7 Years - 10 Years', '10 Years - 15 Years',
                     '15 Years - 20 Years', 'More than 20 Years']
        long_weights = [0.20, 0.25, 0.25, 0.25, 0.05]
        
        # Only assign to bands that are possible given network age
        long_total = supply * long_pct
        valid_long_bands = []
        valid_long_weights = []
        
        # Initialize all long-term bands to 0 first
        for band_name in long_bands:
            band_values[band_name] = 0.0
        
        for band_name, weight in zip(long_bands, long_weights):
            band_idx = next((i for i, b in enumerate(bands) if b['name'] == band_name), None)
            if band_idx is not None and network_age >= bands[band_idx]['min']:
                valid_long_bands.append(band_name)
                valid_long_weights.append(weight)
        
        if valid_long_bands and sum(valid_long_weights) > 0:
            weight_sum = sum(valid_long_weights)
            for band_name, weight in zip(valid_long_bands, valid_long_weights):
                value = long_total * (weight / weight_sum)
                band_values[band_name] = value
                total_distributed += value
        
        # Ensure all bands are in band_values
        for band in bands:
            if band['name'] not in band_values:
                band_values[band['name']] = 0.0
        
        # Normalize to match total supply
        if total_distributed > 0 and total_distributed != supply:
            scale = supply / total_distributed
            for band_name in band_values:
                band_values[band_name] *= scale
        
        # Ensure total matches supply (handle rounding errors)
        current_total = sum(band_values.values())
        if abs(current_total - supply) > 0.01 and current_total > 0:
            # Adjust proportionally
            adjustment = supply / current_total
            for band_name in band_values:
                band_values[band_name] *= adjustment
        
        # Add to results
        for band in bands:
            value = band_values.get(band['name'], 0.0)
            hodl_data[band['name']].append(value)
    
    return hodl_data, bands

# Load data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'

print("Loading price data...")
data = pd.read_csv(dataset_path)

# Convert dates and prices
data['Date'] = pd.to_datetime(data['date'], format='%m/%d/%y')
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data['Supply'] = pd.to_numeric(data['supply'], errors='coerce')

# Get block height if available
if 'block_height' in data.columns:
    data['BlockHeight'] = pd.to_numeric(data['block_height'], errors='coerce')
else:
    data['BlockHeight'] = None

data = data.dropna(subset=['Date', 'Price', 'Supply'])
data = data.sort_values(by='Date').reset_index(drop=True)

# Sample data for performance (daily data can be large)
# Use weekly sampling for historical data, daily for recent data
cutoff_date = data['Date'].max() - timedelta(days=365)
recent_data = data[data['Date'] >= cutoff_date]
historical_data = data[data['Date'] < cutoff_date]

# Sample historical data (weekly)
historical_sampled = historical_data.iloc[::7]  # Every 7 days

# Combine
data_sampled = pd.concat([historical_sampled, recent_data]).sort_values('Date').reset_index(drop=True)

print(f"Loaded {len(data)} rows, using {len(data_sampled)} for chart")

# Get HODL waves data
hodl_waves_data = get_hodl_waves_data_from_api()
if hodl_waves_data is None:
    # Use approximation
    hodl_data, bands = approximate_hodl_waves(
        data_sampled['Date'].values,
        data_sampled['Price'].values,
        data_sampled['Supply'].values
    )
else:
    # Process API data (not implemented in this version)
    hodl_data, bands = approximate_hodl_waves(
        data_sampled['Date'].values,
        data_sampled['Price'].values,
        data_sampled['Supply'].values
    )

# Get current values
current_date = data['Date'].max()
current_row = data[data['Date'] == current_date].iloc[0]
current_price = current_row['Price']
current_supply = current_row['Supply']
current_block_height = current_row.get('BlockHeight')

if pd.isna(current_block_height):
    current_block_height = get_block_height_from_mempool()
    if current_block_height is None:
        current_block_height = calculate_block_height_fallback(current_date)

# Calculate current HODL wave distribution (use last data point)
current_idx = len(data_sampled) - 1
current_distribution = {}
for band in bands:
    band_name = band['name']
    if band_name in hodl_data and len(hodl_data[band_name]) > current_idx:
        current_distribution[band_name] = hodl_data[band_name][current_idx]
    else:
        current_distribution[band_name] = 0.0

# Calculate percentages
total_supply = sum(current_distribution.values())
current_percentages = {k: (v / total_supply * 100) if total_supply > 0 else 0 
                       for k, v in current_distribution.items()}

# Calculate Short, Medium, Long Term
short_term_bands = ['Less than 1 Day', '1 Day - 1 Week', '1 Week - 1 Month', 
                   '1 Month - 3 Months', '3 Months - 6 Months', '6 Months - 1 Year']
medium_term_bands = ['1 Year - 2 Years', '2 Years - 3 Years', '3 Years - 5 Years']
long_term_bands = ['5 Years - 7 Years', '7 Years - 10 Years', '10 Years - 15 Years',
                  '15 Years - 20 Years', 'More than 20 Years']

short_term_btc = sum(current_distribution.get(band, 0) for band in short_term_bands)
medium_term_btc = sum(current_distribution.get(band, 0) for band in medium_term_bands)
long_term_btc = sum(current_distribution.get(band, 0) for band in long_term_bands)

short_term_pct = (short_term_btc / total_supply * 100) if total_supply > 0 else 0
medium_term_pct = (medium_term_btc / total_supply * 100) if total_supply > 0 else 0
long_term_pct = (long_term_btc / total_supply * 100) if total_supply > 0 else 0

# Calculate network age
network_age_days = (current_date - GENESIS_DATE).days
network_age_years = network_age_days / 365.25

# Calculate percentage of 21M mined
total_possible_supply = 21000000
mined_percentage = (current_supply / total_possible_supply) * 100

# Create figure - larger size for better detail
fig = plt.figure(figsize=(26, 15))
fig.patch.set_facecolor('#0a0a0a')
gs = fig.add_gridspec(2, 4, height_ratios=[0.18, 0.82], width_ratios=[0.23, 0.52, 0.15, 0.10],
                     hspace=0.03, wspace=0.03)

# Main chart area
ax_main = fig.add_subplot(gs[1, 1])
ax_main.set_facecolor('#0a0a0a')

# Header area (top)
ax_header = fig.add_subplot(gs[0, :])
ax_header.set_facecolor('#0a0a0a')
ax_header.axis('off')

# Left sidebar (legend)
ax_legend = fig.add_subplot(gs[1, 0])
ax_legend.set_facecolor('#0a0a0a')
ax_legend.axis('off')

# Right sidebar (current distribution)
ax_current = fig.add_subplot(gs[1, 2])
ax_current.set_facecolor('#0a0a0a')
ax_current.axis('off')

# Define colors for HODL bands (warm to cool) - matching example colors more closely
colors = {
    'Less than 1 Day': '#FF69B4',  # Hot pink
    '1 Day - 1 Week': '#FF1493',  # Deep pink
    '1 Week - 1 Month': '#FF6B6B',  # Coral red
    '1 Month - 3 Months': '#FF8C42',  # Orange
    '3 Months - 6 Months': '#FFA500',  # Orange
    '6 Months - 1 Year': '#FFD700',  # Gold
    '1 Year - 2 Years': '#ADFF2F',  # Green yellow
    '2 Years - 3 Years': '#32CD32',  # Lime green
    '3 Years - 5 Years': '#20B2AA',  # Light sea green
    '5 Years - 7 Years': '#1E90FF',  # Dodger blue
    '7 Years - 10 Years': '#4169E1',  # Royal blue
    '10 Years - 15 Years': '#6A5ACD',  # Slate blue
    '15 Years - 20 Years': '#4682B4',  # Steel blue
    'More than 20 Years': '#708090',  # Slate gray
}

# Plot stacked area chart
dates_array = data_sampled['Date'].values
band_values_list = []

for band in bands:
    band_name = band['name']
    if band_name in hodl_data:
        values = np.array(hodl_data[band_name])
        # Convert to percentages
        supply_array = np.array(data_sampled['Supply'].values)
        percentages = (values / supply_array * 100) if len(supply_array) > 0 else values * 0
        band_values_list.append({
            'name': band_name,
            'values': percentages,
            'color': colors.get(band_name, '#808080')
        })

# Stack the areas (bottom to top, oldest to newest)
stacked_data = np.zeros(len(dates_array))
for band_info in reversed(band_values_list):  # Reverse to stack from bottom
    ax_main.fill_between(dates_array, stacked_data, stacked_data + band_info['values'],
                        color=band_info['color'], alpha=0.85, linewidth=0.1, 
                        edgecolor=band_info['color'], label=band_info['name'])
    stacked_data += band_info['values']

# Overlay price line - make it more prominent
ax_price = ax_main.twinx()
ax_price.plot(dates_array, data_sampled['Price'].values, 
             color='black', linewidth=3.5, zorder=100, label='BTC Price', alpha=0.95)

# Format main chart
ax_main.set_xlim(dates_array.min(), dates_array.max())
ax_main.set_ylim(0, 100)
ax_main.set_ylabel('Supply Distribution (%)', color='#E0E0E0', fontsize=13, fontweight='bold')
ax_main.tick_params(axis='y', colors='#E0E0E0', labelsize=11)
ax_main.tick_params(axis='x', colors='#E0E0E0', labelsize=11)

# Format price axis
price_max = data_sampled['Price'].max()
price_ticks = np.arange(0, price_max + 20000, 20000)
ax_price.set_ylim(0, price_max * 1.15)
ax_price.set_yticks(price_ticks)
ax_price.set_ylabel('Price (USD)', color='black', fontsize=13, fontweight='bold', alpha=0.9)
ax_price.tick_params(axis='y', colors='black', labelsize=11, width=1.5)
ax_price.spines['right'].set_color('black')
ax_price.spines['right'].set_linewidth(1.5)

# Add halving lines
dates_min = pd.Timestamp(dates_array.min())
dates_max = pd.Timestamp(dates_array.max())
for halving in HALVINGS:
    halving_date = pd.Timestamp(halving['date'])
    if dates_min <= halving_date <= dates_max:
        ax_main.axvline(x=halving['date'], color='#FFFFFF', linestyle='--', 
                       linewidth=2, alpha=0.6, zorder=50)
        ax_main.text(halving['date'], 97, halving['label'], 
                    rotation=90, color='#FFFFFF', fontsize=10, fontweight='bold',
                    ha='right', va='top', alpha=0.9)

# Format x-axis
ax_main.xaxis.set_major_locator(mdates.YearLocator())
ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax_main.xaxis.set_minor_locator(mdates.MonthLocator((1, 7)))

# Grid - more subtle
ax_main.grid(True, which="major", linestyle='-', alpha=0.08, color='#808080', linewidth=0.5)
ax_main.grid(True, which="minor", linestyle='--', alpha=0.03, color='#808080', linewidth=0.3)

# Remove spines
for spine in ax_main.spines.values():
    spine.set_visible(False)

# HEADER SECTION
header_y = 0.88

# Left side - Title
ax_header.text(0.015, header_y, 'Modeled HODL Waves',
              fontsize=29, fontweight='bold', color='#FFA500',
              verticalalignment='top', horizontalalignment='left',
              transform=ax_header.transAxes)
ax_header.text(0.018, 0.58, 'Proxy estimate; not UTXO-age data',
              fontsize=10, color='#BDBDBD',
              verticalalignment='top', horizontalalignment='left',
              transform=ax_header.transAxes)

# Compact header metrics. Keep labels short so they do not collide on save.
date_str = current_date.strftime('%Y-%m-%d %H:%M:%S UTC')
ax_header.text(0.018, 0.32, date_str,
              fontsize=11, color='#BDBDBD',
              verticalalignment='top', horizontalalignment='left',
              transform=ax_header.transAxes)

metric_columns = [
    ('Mined', f'{mined_percentage:.1f}% of 21M', '#FFA500'),
    ('Block', f'{int(current_block_height):,}', '#E0E0E0'),
    ('BTCUSD', f'${current_price:,.0f}', '#E0E0E0'),
    ('Supply', f'{current_supply:,.0f} BTC', '#E0E0E0'),
    ('Age', f'{network_age_years:.2f} years', '#E0E0E0'),
]

for idx, (label, value, value_color) in enumerate(metric_columns):
    x_pos = 0.34 + idx * 0.12
    ax_header.text(x_pos, 0.84, label,
                  fontsize=9, color='#9E9E9E', fontweight='bold',
                  verticalalignment='top', horizontalalignment='left',
                  transform=ax_header.transAxes)
    ax_header.text(x_pos, 0.57, value,
                  fontsize=12, color=value_color, fontweight='bold',
                  verticalalignment='top', horizontalalignment='left',
                  transform=ax_header.transAxes)

holder_columns = [
    ('Short-term', short_term_btc, short_term_pct),
    ('Medium-term', medium_term_btc, medium_term_pct),
    ('Long-term', long_term_btc, long_term_pct),
]

for idx, (label, btc_value, pct_value) in enumerate(holder_columns):
    x_pos = 0.34 + idx * 0.20
    ax_header.text(x_pos, 0.27, label,
                  fontsize=9, color='#9E9E9E', fontweight='bold',
                  verticalalignment='top', horizontalalignment='left',
                  transform=ax_header.transAxes)
    ax_header.text(x_pos + 0.065, 0.27,
                  f'{btc_value:,.0f} BTC ({pct_value:.1f}%)',
                  fontsize=10, color='#E0E0E0',
                  verticalalignment='top', horizontalalignment='left',
                  transform=ax_header.transAxes)

# LEFT SIDEBAR - Legend
legend_y = 0.97
legend_title_y = legend_y
ax_legend.text(0.06, legend_title_y, 'HODL Duration',
              fontsize=15, fontweight='bold', color='#FFFFFF',
              verticalalignment='top', horizontalalignment='left',
              transform=ax_legend.transAxes)

legend_y -= 0.05

# Group by category
short_legend = []
medium_legend = []
long_legend = []

for band in bands:
    band_name = band['name']
    pct = current_percentages.get(band_name, 0)
    color = colors.get(band_name, '#808080')
    
    if band_name in short_term_bands:
        short_legend.append((band_name, pct, color))
    elif band_name in medium_term_bands:
        medium_legend.append((band_name, pct, color))
    elif band_name in long_term_bands:
        long_legend.append((band_name, pct, color))

# Short Term
ax_legend.text(0.06, legend_y, 'Short Term',
              fontsize=12, fontweight='bold', color='#E0E0E0',
              verticalalignment='top', horizontalalignment='left',
              transform=ax_legend.transAxes)
legend_y -= 0.035

for band_name, pct, color in short_legend:
    # Color square - larger and more visible
    rect = Rectangle((0.06, legend_y), 0.028, 0.022,
                    transform=ax_legend.transAxes, facecolor=color,
                    edgecolor='none', alpha=0.9)
    ax_legend.add_patch(rect)
    
    # Label and percentage
    label_text = f"{band_name}: {pct:.1f}%"
    ax_legend.text(0.095, legend_y + 0.006, label_text,
                  fontsize=10, color='#E0E0E0',
                  verticalalignment='center', horizontalalignment='left',
                  transform=ax_legend.transAxes)
    legend_y -= 0.028

legend_y -= 0.025

# Medium Term
ax_legend.text(0.06, legend_y, 'Medium Term',
              fontsize=12, fontweight='bold', color='#E0E0E0',
              verticalalignment='top', horizontalalignment='left',
              transform=ax_legend.transAxes)
legend_y -= 0.035

for band_name, pct, color in medium_legend:
    rect = Rectangle((0.06, legend_y), 0.028, 0.022,
                    transform=ax_legend.transAxes, facecolor=color,
                    edgecolor='none', alpha=0.9)
    ax_legend.add_patch(rect)
    
    label_text = f"{band_name}: {pct:.1f}%"
    ax_legend.text(0.095, legend_y + 0.006, label_text,
                  fontsize=10, color='#E0E0E0',
                  verticalalignment='center', horizontalalignment='left',
                  transform=ax_legend.transAxes)
    legend_y -= 0.028

legend_y -= 0.025

# Long Term
ax_legend.text(0.06, legend_y, 'Long Term',
              fontsize=12, fontweight='bold', color='#E0E0E0',
              verticalalignment='top', horizontalalignment='left',
              transform=ax_legend.transAxes)
legend_y -= 0.035

for band_name, pct, color in long_legend:
    rect = Rectangle((0.06, legend_y), 0.028, 0.022,
                    transform=ax_legend.transAxes, facecolor=color,
                    edgecolor='none', alpha=0.9)
    ax_legend.add_patch(rect)
    
    label_text = f"{band_name}: {pct:.1f}%"
    ax_legend.text(0.095, legend_y + 0.006, label_text,
                  fontsize=10, color='#E0E0E0',
                  verticalalignment='center', horizontalalignment='left',
                  transform=ax_legend.transAxes)
    legend_y -= 0.028

# RIGHT SIDEBAR - Current Distribution Summary (vertical bar chart)
current_y = 0.97
ax_current.text(0.05, current_y, 'Current Distribution',
               fontsize=15, fontweight='bold', color='#FFFFFF',
               verticalalignment='top', horizontalalignment='left',
               transform=ax_current.transAxes)

current_y -= 0.12

# Horizontal bar chart of current distribution
categories = ['Short Term', 'Medium Term', 'Long Term']
category_values = [short_term_pct, medium_term_pct, long_term_pct]
category_colors = ['#FF6347', '#32CD32', '#1E90FF']

for i, (cat, val, color) in enumerate(zip(categories, category_values, category_colors)):
    y_pos = current_y - 0.12 - i * 0.17
    bar_width = (val / 100) * 0.78

    ax_current.text(0.08, y_pos + 0.075, cat,
                   fontsize=11, color='#E0E0E0', fontweight='bold',
                   verticalalignment='bottom', horizontalalignment='left',
                   transform=ax_current.transAxes)

    rect = Rectangle((0.08, y_pos), bar_width, 0.055,
                    transform=ax_current.transAxes, facecolor=color,
                    edgecolor='none', alpha=0.85)
    ax_current.add_patch(rect)

    ax_current.text(0.08 + bar_width + 0.025, y_pos + 0.0275, f'{val:.1f}%',
                   fontsize=12, fontweight='bold', color='#FFFFFF',
                   verticalalignment='center', horizontalalignment='left',
                   transform=ax_current.transAxes)

# Footer area left empty

# Save chart
output_path = script_dir / 'hodl_waves_price.png'
plt.savefig(output_path, dpi=300, facecolor='#0a0a0a', bbox_inches='tight', pad_inches=0.1)
print(f"\nChart saved as '{output_path}'")
print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
print(f"Current Price: ${current_price:,.2f}")
print(f"Block Height: {int(current_block_height):,}")
print(f"Mined Supply: {current_supply:,.0f} BTC ({mined_percentage:.1f}%)")
print(f"Short Term: {short_term_pct:.1f}% ({short_term_btc:,.0f} BTC)")
print(f"Medium Term: {medium_term_pct:.1f}% ({medium_term_btc:,.0f} BTC)")
print(f"Long Term: {long_term_pct:.1f}% ({long_term_btc:,.0f} BTC)")

plt.close(fig)
