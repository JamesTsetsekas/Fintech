# Modeled HODL Waves Price Chart

A Python script to visualize a proxy for Bitcoin HODL Waves - an estimated distribution of Bitcoin supply by holding duration over time, with the Bitcoin price overlaid.

## Overview

This script generates a comprehensive modeled HODL Waves chart that shows:
- Stacked area chart displaying an estimated distribution of Bitcoin supply across different HODL duration bands
- Bitcoin price line overlaid on the modeled HODL waves
- Key metrics including percentage mined, block height, current price, network age, etc.
- Detailed legend showing different HODL duration bands with current percentages
- Current distribution summary (Short, Medium, Long Term percentages)

## HODL Duration Bands

The chart divides Bitcoin supply into the following holding duration bands:

**Short Term (0-1 Year):**
- Less than 1 Day
- 1 Day - 1 Week
- 1 Week - 1 Month
- 1 Month - 3 Months
- 3 Months - 6 Months
- 6 Months - 1 Year

**Medium Term (1-5 Years):**
- 1 Year - 2 Years
- 2 Years - 3 Years
- 3 Years - 5 Years

**Long Term (5+ Years):**
- 5 Years - 7 Years
- 7 Years - 10 Years
- 10 Years - 15 Years
- 15 Years - 20 Years
- More than 20 Years

## Data Sources

- **Price Data**: Uses `daily_price.csv` from the Bitcoin data folder
- **Modeled HODL Waves**: Uses an approximation model based on price volatility, network age, and supply distribution
  - Note: Real HODL wave data requires UTXO age analysis which is not available in the block CSV files
  - The script includes infrastructure to integrate API-based HODL wave data if available

## Requirements

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the script:

```bash
python hodl_waves_price.py
```

The script will:
1. Load price and supply data from the Bitcoin data folder
2. Generate approximate HODL wave distributions
3. Create the visualization with all components
4. Save the chart as `hodl_waves_price.png`

## Output

The script generates a high-resolution PNG chart (`hodl_waves_price.png`) that includes:
- Header section with key metrics (percentage mined, block height, date, price, network age, etc.)
- Main stacked area chart showing modeled HODL waves over time
- Bitcoin price line overlay (black line)
- Halving event markers (vertical dashed lines)
- Left sidebar with detailed legend of all HODL duration bands
- Right sidebar with current distribution summary

## Notes

- HODL waves are approximated using a model based on price volatility and network age
- For accurate HODL wave data, integration with APIs that provide UTXO age analysis would be required
- The chart matches the style and layout of the reference image
- Historical data is sampled weekly for performance, while recent data (last year) is daily
