# Bitcoin Bollinger Bands Chart

A visualization of Bitcoin price with Bollinger Bands, showing price volatility and potential support/resistance levels.

## Features

- **Price Line (Orange)**: Current Bitcoin price
- **SMA 20 (Green)**: 20-period Simple Moving Average
- **Bollinger Bands**: Upper and Lower bands showing 2 standard deviations from the SMA
  - **Upper Band**: Grey line forming the upper boundary
  - **Lower Band**: Black line forming the lower boundary
  - **Shaded Area**: Grey region between the bands indicating volatility range

## Chart Components

1. **Main Chart**: Shows the last 2 years of data with detailed view
2. **Mini Chart**: Shows full historical context with vertical lines indicating the zoomed period

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python bollinger_bands.py
```

The chart will be saved as `bollinger_bands.png` in the same directory.

## Data Source

The script reads Bitcoin price data from `../price.csv` which should contain columns:
- `Start`: Date in YYYY-MM-DD format
- `Close`: Closing price

## Bollinger Bands Calculation

- **Period**: 20 days
- **Standard Deviation Multiplier**: 2
- **Middle Band**: SMA 20
- **Upper Band**: SMA 20 + (2 × Standard Deviation)
- **Lower Band**: SMA 20 - (2 × Standard Deviation)

## Chart Styling

- Dark grey background (#1a1a1a)
- Professional financial chart appearance
- Credits: "Charts by: @BitboBTC"
- BITBO branding

