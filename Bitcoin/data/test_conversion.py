#!/usr/bin/env python3
"""
Simple test script to verify CoinMarketCap CSV to price.csv conversion
"""

import pandas as pd
from pathlib import Path

# Test conversion
input_file = "Bitcoin_1_1_2008-1_2_2026_historical_data_coinmarketcap.csv"
output_file = "price_test.csv"

print(f"Reading: {input_file}")
df = pd.read_csv(input_file, sep=';', quotechar='"')

print(f"Found {len(df)} rows")
print(f"Columns: {df.columns.tolist()}")
print(f"\nFirst few rows:")
print(df.head(3))

# Convert dates
df['Start'] = pd.to_datetime(df['timeOpen']).dt.date
df['End'] = pd.to_datetime(df['timeClose']).dt.date

# Create converted dataframe
converted_df = pd.DataFrame({
    'Start': df['Start'],
    'End': df['End'],
    'Open': df['open'],
    'High': df['high'],
    'Low': df['low'],
    'Close': df['close'],
    'Volume': df['volume'],
    'Market Cap': df['marketCap']
})

# Sort by date (newest first)
converted_df['Start'] = pd.to_datetime(converted_df['Start'])
converted_df['End'] = pd.to_datetime(converted_df['End'])
converted_df = converted_df.sort_values('Start', ascending=False)

# Format dates
converted_df['Start'] = converted_df['Start'].dt.strftime('%Y-%m-%d')
converted_df['End'] = converted_df['End'].dt.strftime('%Y-%m-%d')

print(f"\nConverted {len(converted_df)} rows")
print(f"\nFirst few converted rows:")
print(converted_df.head(5))

# Save
converted_df.to_csv(output_file, index=False)
print(f"\n[OK] Saved to {output_file}")



