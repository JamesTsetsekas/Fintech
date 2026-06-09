# Bitcoin Rainbow Chart

This script generates a Bitcoin Rainbow Chart based on the Halving Price Regression (HPR) model.

## Description

The Bitcoin Rainbow Chart visualizes Bitcoin's price history and future projections using colored bands that represent different price zones. The chart is based on the Halving Price Regression (HPR), which is calculated using only the Bitcoin prices on the three halving dates.

## Features

- **HPR (Halving Price Regression)**: A non-linear regression curve calculated using prices from halving dates
  - Formula: `log10(price) = 2.6521*LN(days_since_genesis) - 18.163`
  - Inputs: 28-Nov-2012 $12.33, 9-Jul-2016 $651.94, 11-May-2020 $8,591.65

- **Rainbow Bands**: Six colored bands representing different price zones:
  - **Low** (Dark Blue): 1 year behind trend
  - **Blue**: On trend (HPR line)
  - **Green**: 1 year ahead of trend
  - **Yellow**: 2 years ahead of trend
  - **Orange**: 3 years ahead of trend
  - **Red**: 4 years ahead of trend

- **Halving Events**: Vertical dashed green lines marking Bitcoin halving dates

- **Price History**: White line showing actual Bitcoin price from historical data

## Usage

```bash
cd Bitcoin/rainbow
python3 rainbow_chart.py
```

The script will:
1. Load price data from `../price.csv`
2. Calculate HPR and rainbow bands
3. Generate and display the chart
4. Save the chart as `rainbow_chart.png` (300 DPI)

## Requirements

- pandas
- matplotlib
- numpy

## Data Source

Uses `Bitcoin/price.csv` which contains daily Bitcoin price data with columns:
- Start: Date
- Close: Closing price (used for the chart)

## References

- Inspired by [Bitbo Charts](https://charts.bitbo.io/rainbow/)
- Original concept by [@ChartsBtc](https://twitter.com/ChartsBtc)

