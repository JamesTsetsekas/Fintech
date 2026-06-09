#!/usr/bin/env python3
"""
Bitcoin Monthly & Yearly Returns Visualization

Creates a table visualization showing monthly and yearly returns for Bitcoin
over the last 10 years
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from datetime import datetime
import numpy as np
from pathlib import Path

# Load data
dataset_path = Path(__file__).parent.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'
data = pd.read_csv(dataset_path)

# Convert dates and prices
data['Date'] = pd.to_datetime(data['date'], format='%m/%d/%y')
data['Close'] = pd.to_numeric(data['price'], errors='coerce')
data['High'] = pd.to_numeric(data['daily_high'], errors='coerce')
# daily_price.csv doesn't have Open or Low, so we'll use price for both
# Open = previous day's close, Low = current day's price (min approximation)
data = data.sort_values('Date').reset_index(drop=True)
data['Open'] = data['Close'].shift(1).fillna(data['Close'])
data['Low'] = data['Close']  # Use price as approximation for Low
data = data.dropna(subset=['Date', 'Open', 'High', 'Low', 'Close'])
data = data.sort_values(by='Date')

# Get last 10 years of data
current_date = data['Date'].max()
start_date = current_date - pd.DateOffset(years=10)
data = data[data['Date'] >= start_date]

# Group by month
data['Year'] = data['Date'].dt.year
data['Month'] = data['Date'].dt.month

# Calculate monthly aggregates
monthly_data = data.groupby(['Year', 'Month']).agg({
    'Open': 'first',  # First day's open
    'High': 'max',    # Maximum high
    'Low': 'min',     # Minimum low
    'Close': 'last'   # Last day's close
}).reset_index()

# Calculate monthly returns (from Open to Close of the month)
monthly_data = monthly_data.sort_values(['Year', 'Month'])
monthly_data['Return'] = ((monthly_data['Close'] - monthly_data['Open']) / monthly_data['Open']) * 100

# Calculate yearly aggregates
yearly_data = data.groupby('Year').agg({
    'Open': 'first',  # First day's open of the year
    'High': 'max',    # Maximum high of the year
    'Low': 'min',     # Minimum low of the year
    'Close': 'last'   # Last day's close of the year
}).reset_index()

# Calculate yearly returns (from Open to Close of the year)
yearly_data = yearly_data.sort_values('Year')
yearly_data['Return'] = ((yearly_data['Close'] - yearly_data['Open']) / yearly_data['Open']) * 100

# Get unique years (last 10 years)
years = sorted(monthly_data['Year'].unique(), reverse=True)[:10]
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Create figure - increased height to accommodate 10 years
fig, ax = plt.subplots(figsize=(16, 14))
ax.axis('off')

# Table dimensions
cell_width = 1.2
cell_height = 0.8
year_label_width = 0.8
year_label_x = -0.2  # Moved further left to avoid overlap
table_x_start = 1.0  # Moved right to create spacing from year column
table_y_start = 8.5

# Header row
header_y = table_y_start

# Year column header
rect = Rectangle((year_label_x - year_label_width/2, header_y - cell_height/2), 
                 year_label_width, cell_height, 
                 linewidth=1.5, edgecolor='white', facecolor='#1a1a1a')
ax.add_patch(rect)
ax.text(year_label_x, header_y, 'Year', ha='center', va='center', 
        fontsize=11, fontweight='bold', color='white')

# Month headers
month_x_positions = {}
for i, month in enumerate(months):
    x_pos = table_x_start + i * cell_width
    month_x_positions[i+1] = x_pos
    rect = Rectangle((x_pos - cell_width/2, header_y - cell_height/2), 
                     cell_width, cell_height, 
                     linewidth=1.5, edgecolor='white', facecolor='#1a1a1a')
    ax.add_patch(rect)
    ax.text(x_pos, header_y, month, ha='center', va='center', 
            fontsize=11, fontweight='bold', color='white')

# Yearly column header
yearly_x = table_x_start + 12 * cell_width
rect = Rectangle((yearly_x - cell_width/2, header_y - cell_height/2), 
                 cell_width, cell_height, 
                 linewidth=1.5, edgecolor='white', facecolor='#1a1a1a')
ax.add_patch(rect)
ax.text(yearly_x, header_y, 'Yearly', ha='center', va='center', 
        fontsize=11, fontweight='bold', color='white')

# Year label column
for idx, year in enumerate(years):
    y_pos = table_y_start - (idx + 1) * cell_height
    rect = Rectangle((year_label_x - year_label_width/2, y_pos - cell_height/2), 
                     year_label_width, cell_height, 
                     linewidth=1.5, edgecolor='white', facecolor='#1a1a1a')
    ax.add_patch(rect)
    ax.text(year_label_x, y_pos, str(year), ha='center', va='center', 
            fontsize=11, fontweight='bold', color='white')

# Fill monthly data
for idx, year in enumerate(years):
    year_y = table_y_start - (idx + 1) * cell_height
    year_monthly = monthly_data[monthly_data['Year'] == year]
    
    for month_num in range(1, 13):
        month_data = year_monthly[year_monthly['Month'] == month_num]
        x_pos = month_x_positions[month_num]
        
        if len(month_data) > 0:
            row = month_data.iloc[0]
            o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
            ret = row['Return'] if not pd.isna(row['Return']) else 0
            
            # Color based on return
            color = '#2d5016' if ret >= 0 else '#501616'  # Dark green or dark red
            rect = Rectangle((x_pos - cell_width/2, year_y - cell_height/2), 
                           cell_width, cell_height, 
                           linewidth=1, edgecolor='#333333', facecolor=color)
            ax.add_patch(rect)
            
            # Format text - O/H/L/C data (smaller, positioned above)
            # Position with va='top' to prevent overflow above the box
            text_data = f"O: ${o:,.0f}\nH: ${h:,.0f}\nL: ${l:,.0f}\nC: ${c:,.0f}"
            ax.text(x_pos, year_y - 0.38, text_data, ha='center', va='top', 
                   fontsize=6.5, color='white', family='monospace')
            
            # Return percentage (larger and bold, positioned at bottom)
            # Position with va='bottom' to prevent overflow below the box
            # Moved slightly lower to add margin above close price
            ax.text(x_pos, year_y + 0.30, f"{ret:+.2f}%", ha='center', va='bottom', 
                   fontsize=8.5, fontweight='bold', color='white', family='monospace')
        else:
            # Empty cell
            rect = Rectangle((x_pos - cell_width/2, year_y - cell_height/2), 
                           cell_width, cell_height, 
                           linewidth=1, edgecolor='#333333', facecolor='#0a0a0a')
            ax.add_patch(rect)
    
    # Yearly data
    year_row = yearly_data[yearly_data['Year'] == year]
    if len(year_row) > 0:
        row = year_row.iloc[0]
        o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
        ret = row['Return'] if not pd.isna(row['Return']) else 0
        
        # Color based on return
        color = '#2d5016' if ret >= 0 else '#501616'
        rect = Rectangle((yearly_x - cell_width/2, year_y - cell_height/2), 
                       cell_width, cell_height, 
                       linewidth=1, edgecolor='#333333', facecolor=color)
        ax.add_patch(rect)
        
        # Format text - O/H/L/C data (smaller, positioned above)
        # Position with va='top' to prevent overflow above the box
        text_data = f"O: ${o:,.0f}\nH: ${h:,.0f}\nL: ${l:,.0f}\nC: ${c:,.0f}"
        ax.text(yearly_x, year_y - 0.38, text_data, ha='center', va='top', 
               fontsize=6.5, color='white', family='monospace')
        
        # Return percentage (larger and bold, positioned at bottom)
        # Position with va='bottom' to prevent overflow below the box
        # Moved slightly lower to add margin above close price
        ax.text(yearly_x, year_y + 0.30, f"{ret:+.2f}%", ha='center', va='bottom', 
               fontsize=8.5, fontweight='bold', color='white', family='monospace')

# Title
title_y = table_y_start + 0.95
ax.text(table_x_start + 6 * cell_width, title_y, 
        'Monthly & Yearly Returns (Last 10 Years)', 
        ha='center', va='center', fontsize=18, fontweight='bold', color='white')

# Use dark background
fig.patch.set_facecolor('black')
ax.set_facecolor('black')

# Set limits - adjusted to accommodate year column on the left and 10 years of data
ax.set_xlim(-1, table_x_start + 13 * cell_width + 1)
ax.set_ylim(0, title_y + 0.65)
ax.set_aspect('equal')
ax.invert_yaxis()

plt.tight_layout()
output_path = Path(__file__).parent / 'monthly_yearly_returns.png'
plt.savefig(output_path, dpi=300, facecolor='black', bbox_inches='tight')
print(f"Chart saved as '{output_path}'")
plt.close(fig)  # Explicitly close the figure to free memory
# plt.show()  # Commented out for automation
