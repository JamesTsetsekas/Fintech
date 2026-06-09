#!/usr/bin/env python3
"""
Daily DCA Cost Basis (Weighted Average Cost) Chart

Creates a visualization showing the weighted average cost basis for a daily 
Dollar-Cost Averaging (DCA) strategy over different durations, compared to 
the Bitcoin price at each duration point.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Constants
GENESIS_DATE = datetime(2009, 1, 3)

HALVING_DATES = [
    datetime(2012, 11, 28),  # 1st Halving
    datetime(2016, 7, 9),    # 2nd Halving
    datetime(2020, 5, 11),   # 3rd Halving
    datetime(2024, 4, 20),   # 4th Halving
]

def get_block_height():
    """Get current block height from API or calculate fallback"""
    try:
        url = 'https://mempool.space/api/blocks/tip/height'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return int(response.text.strip())
    except Exception:
        pass
    
    # Fallback calculation
    days_since_genesis = (datetime.now() - GENESIS_DATE).days
    return int(days_since_genesis * 144)  # ~144 blocks per day

def calculate_dca_cost_basis(data, start_date, end_date):
    """
    Calculate weighted average cost basis for daily DCA strategy.
    
    Assumes $1 invested per day.
    Returns: cost_basis (weighted average price)
    """
    mask = (data['Date'] >= start_date) & (data['Date'] <= end_date)
    period_data = data[mask].copy()
    
    if len(period_data) == 0:
        return None
    
    prices = period_data['Close'].values
    
    # Total invested = number of days * $1
    total_invested = len(period_data)
    
    # Total BTC purchased = sum($1 / price for each day)
    btc_purchased = np.sum(1.0 / prices)
    
    if btc_purchased <= 0:
        return None
    
    # Cost basis = Total invested / Total BTC purchased
    cost_basis = total_invested / btc_purchased
    return cost_basis

def get_price_at_date(data, target_date):
    """Get Bitcoin price at or before target_date"""
    mask = data['Date'] <= target_date
    if mask.any():
        return data[mask].iloc[-1]['Close']
    return data.iloc[0]['Close']

# Load and prepare data
script_dir = Path(__file__).parent
data = pd.read_csv(script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv')
data['Date'] = pd.to_datetime(data['date'])
data['Close'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Close']).sort_values('Date').reset_index(drop=True)

current_date = data['Date'].max()
current_price = data[data['Date'] == current_date]['Close'].iloc[0]
block_height = get_block_height()

# Calculate maximum duration
max_duration_days = (current_date - data['Date'].min()).days

# Create duration points for calculation
# Use daily granularity for recent periods, coarser for older periods
duration_points_days = []

# Last 2 years: daily
for days in range(1, min(730, max_duration_days) + 1):
    duration_points_days.append(days)

# 2-5 years: every 7 days (weekly)
for days in range(730, min(1825, max_duration_days) + 1, 7):
    if days not in duration_points_days:
        duration_points_days.append(days)

# 5+ years: every 30 days (monthly)
for days in range(1825, max_duration_days + 1, 30):
    if days not in duration_points_days:
        duration_points_days.append(days)

# Ensure key year markers are included
for years in [14, 12, 10, 8, 6, 4, 2, 1]:
    days = int(years * 365.25)
    if days <= max_duration_days and days not in duration_points_days:
        duration_points_days.append(days)

duration_points_days = sorted(set(duration_points_days), reverse=True)

# Calculate DCA cost basis and Bitcoin prices
dca_cost_basis_list = []
bitcoin_prices_list = []
durations_years_list = []

print("Calculating DCA cost basis and prices...")
for duration_days in duration_points_days:
    if duration_days > max_duration_days:
        continue
    
    start_date = current_date - timedelta(days=duration_days)
    
    # Calculate DCA cost basis
    cost_basis = calculate_dca_cost_basis(data, start_date, current_date)
    if cost_basis is None:
        continue
    
    # Get Bitcoin price at start date
    price_at_start = get_price_at_date(data, start_date)
    
    dca_cost_basis_list.append(cost_basis)
    bitcoin_prices_list.append(price_at_start)
    durations_years_list.append(duration_days / 365.25)

# Smooth the DCA cost basis line using interpolation
try:
    from scipy.interpolate import interp1d
    
    # Create fine-grained x-axis for smooth plotting
    min_years = min(durations_years_list)
    max_years = max(durations_years_list)
    smooth_years = np.linspace(max_years, min_years, 2000)
    
    # Interpolate DCA cost basis
    f_dca = interp1d(durations_years_list, dca_cost_basis_list, 
                     kind='cubic', bounds_error=False, fill_value='extrapolate')
    dca_smooth = f_dca(smooth_years)
    
    # Interpolate Bitcoin prices
    f_price = interp1d(durations_years_list, bitcoin_prices_list,
                       kind='linear', bounds_error=False, fill_value='extrapolate')
    price_smooth = f_price(smooth_years)
    
    plot_years = smooth_years
    plot_dca = dca_smooth
    plot_prices = price_smooth
    
except ImportError:
    # Fallback: use original points
    print("Note: scipy not available, using original data points")
    plot_years = durations_years_list
    plot_dca = dca_cost_basis_list
    plot_prices = bitcoin_prices_list

# Create figure
fig = plt.figure(figsize=(20, 12))
fig.patch.set_facecolor('black')
ax = fig.add_subplot(111)
ax.set_facecolor('black')

# Set y-axis limits
ax.set_ylim(0, 120000)

# Plot DCA Cost Basis (orange line) - behind
ax.plot(plot_years, plot_dca, color='#FF8C00', linewidth=2.5, 
        zorder=8, alpha=0.95, label='DCA Cost Basis')

# Plot Bitcoin price line with green/red coloring
# Color based on price change direction
if len(plot_prices) > 1:
    for i in range(len(plot_years) - 1):
        x1, x2 = plot_years[i], plot_years[i + 1]
        y1, y2 = plot_prices[i], plot_prices[i + 1]
        
        color = '#00FF00' if y2 >= y1 else '#FF0000'
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=2.0, 
                zorder=12, alpha=0.95)

# Add halving event markers
halving_labels = ['1st Halving', '2nd Halving', '3rd Halving', '4th Halving']
for i, halving_date in enumerate(HALVING_DATES):
    if halving_date > current_date:
        continue
    
    days_ago = (current_date - halving_date).days
    years_ago = days_ago / 365.25
    
    min_years = min(durations_years_list)
    max_years = max(durations_years_list)
    
    if min_years <= years_ago <= max_years:
        ax.axvline(x=years_ago, color='white', linewidth=1.5, 
                   linestyle='--', alpha=0.7, zorder=5)
        
        date_str = halving_date.strftime('%m/%d/%Y')
        ax.text(years_ago, 120000 * 0.96, f'{halving_labels[i]}\n{date_str}',
                ha='center', va='top', fontsize=9, color='white',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='black', 
                         edgecolor='white', alpha=0.7))

# Format axes
ax.set_ylabel('Price (USD)', color='white', fontsize=12, fontweight='bold')
ax.tick_params(axis='y', colors='white', labelsize=10)
ax.set_yticks(np.arange(0, 120001, 20000))
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x:,.0f}'))

ax.set_xlabel('Daily DCA Duration', color='white', fontsize=12, fontweight='bold')
ax.tick_params(axis='x', colors='white', labelsize=10)

min_years = min(durations_years_list)
max_years = max(durations_years_list)
ax.set_xlim(max_years, min_years)

# X-axis tick labels
x_ticks = []
x_labels = []
for years in [14, 12, 10, 8, 6, 4, 2, 1]:
    if min_years <= years <= max_years:
        x_ticks.append(years)
        x_labels.append(f'{int(years)} Year{"s" if years > 1 else ""}')

if min_years <= 0.0027 <= max_years:
    x_ticks.append(0.0027)
    x_labels.append('1 Day')

ax.set_xticks(x_ticks)
ax.set_xticklabels(x_labels)

# Grid
ax.grid(True, which="major", linestyle='--', alpha=0.15, color='white', linewidth=0.5)
ax.grid(True, which="minor", linestyle=':', alpha=0.08, color='white', linewidth=0.3)

# Remove spines
for spine in ax.spines.values():
    spine.set_visible(False)

# Title and headers
title_y = 0.98
ax.text(0.5, title_y, 'Daily DCA Cost Basis (Weighted Average Cost)', 
        ha='center', va='top', transform=ax.transAxes,
        fontsize=24, fontweight='bold', color='white')

ax.text(0.02, title_y, 'bitcoin', 
        ha='left', va='top', transform=ax.transAxes,
        fontsize=14, fontweight='bold', color='#FF8C00')

current_date_str = current_date.strftime('%b %d, %Y %H:%M (UTC)')
ax.text(0.98, title_y, current_date_str, 
        ha='right', va='top', transform=ax.transAxes,
        fontsize=10, color='#888888')
ax.text(0.98, title_y - 0.03, f'Block Height: {block_height:,}', 
        ha='right', va='top', transform=ax.transAxes,
        fontsize=10, color='#888888')

# Add cost basis labels at key points
key_years = [14, 10, 6, 2, 1]
for years in key_years:
    days = int(years * 365.25)
    if days in duration_points_days:
        idx = duration_points_days.index(days)
        if idx < len(dca_cost_basis_list):
            cost = dca_cost_basis_list[idx]
            years_pos = days / 365.25
            if min_years <= years_pos <= max_years:
                ax.text(years_pos, cost * 1.08, f'${cost:,.0f}', 
                        ha='center', va='bottom', fontsize=10, color='#FF8C00', 
                        fontweight='bold')

# 1 day label
if 1 in duration_points_days:
    idx = duration_points_days.index(1)
    if idx < len(dca_cost_basis_list):
        cost = dca_cost_basis_list[idx]
        if min_years <= 0.0027 <= max_years:
            ax.text(0.0027, cost * 1.08, f'${cost:,.0f}', 
                    ha='center', va='bottom', fontsize=10, color='#FF8C00', 
                    fontweight='bold')

# Layout
plt.subplots_adjust(left=0.08, right=0.95, top=0.90, bottom=0.08)

# Save
output_path = script_dir / 'dca_cost_basis.png'
plt.savefig(output_path, dpi=300, facecolor='black', bbox_inches='tight')
print(f"\nChart saved as '{output_path}'")
print(f"Current Price: ${current_price:,.2f}")
print(f"Current Date: {current_date_str}")
print(f"Block Height: {block_height:,}")

# Print key values
print("\nKey DCA Cost Basis Values:")
for years in [14, 10, 6, 2, 1]:
    days = int(years * 365.25)
    if days in duration_points_days:
        idx = duration_points_days.index(days)
        if idx < len(dca_cost_basis_list):
            print(f"  {years} Year{'s' if years > 1 else ''}: ${dca_cost_basis_list[idx]:,.2f}")
