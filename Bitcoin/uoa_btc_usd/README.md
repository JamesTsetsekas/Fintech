# Unit of Account: BTC/USD Chart

This script creates a dual chart visualization showing the relationship between Bitcoin and the US Dollar.

## Features

- **Left Chart**: Price of 1 USD in terms of Bitcoin (displayed in satoshis)
- **Right Chart**: Price of 1 BTC in terms of US Dollar

Both charts use:
- Log-linear scale (logarithmic y-axis, linear x-axis)
- Dark background with colored lines (orange for USD/BTC, green for BTC/USD)
- Current values displayed prominently
- Block height estimation based on date
- Historical data from 2010 to present

## Requirements

Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

Run the script:

```bash
python3 uoa_btc_usd.py
```

The chart will be saved as `uoa_btc_usd.png` in the same directory.

## Data Source

The script reads Bitcoin price data from `../price.csv` (relative to the script directory).

## Output

The script generates a high-resolution PNG image (300 DPI) with:
- Two side-by-side charts
- Current price values displayed prominently
- Block height information
- Date information
- Log-linear scale for better visualization of price changes over time


