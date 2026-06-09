# Bitcoin Power Law Oscillator

This script generates a Bitcoin Power Law Oscillator chart that assesses whether Bitcoin is currently under or overvalued by comparing its market price to the Bitbo-style long-term power-law fair value.

## Description

The Power Law Oscillator is a tool designed to assess whether Bitcoin is currently under or overvalued by comparing its market price to the long-term power-law fair value. This oscillator ranges from -1 to 1, indicating the log-price deviation between the current market price and the power-law fair value. High oscillator values often correspond with market tops, while low values align with market bottoms.

## Features

- **Power Law Fair Value**: Bitbo-style long-term power law
  - Formula: `price = 10^-17.016 * (days_since_genesis ^ 5.845)`

- **Oscillator**: Normalized log deviation between actual price and power law fit
  - Ranges from -1.00 to 1.00
  - Values > 0 indicate overvaluation relative to power law trend
  - Values < 0 indicate undervaluation relative to power law trend
  - Normalized using percentile-based method for stability

- **Median**: Moving median of the oscillator (365-day window)
  - Provides a smoother trend line
  - Helps identify longer-term cycles

- **USD Price**: Actual Bitcoin price plotted on logarithmic scale

## Usage

```bash
cd Bitcoin/power-law-oscillator
python3 power_law_oscillator.py
```

The script will:
1. Load price data from `../price.csv`
2. Calculate the Bitbo-style power-law fair value
3. Calculate oscillator values (normalized log deviations)
4. Calculate moving median of oscillator
5. Generate and display the chart
6. Save the chart as `power_law_oscillator.png` (300 DPI)

## Requirements

- pandas
- matplotlib
- numpy

## Data Source

Uses `Bitcoin/price.csv` which contains daily Bitcoin price data with columns:
- Start: Date
- Close: Closing price (used for the chart)

## Chart Features

- **Dark Background**: Matches the original Bitbo chart style
- **Dual Y-Axes**: 
  - Left axis: Oscillator values (-1.00 to 1.00)
  - Right axis: USD price (logarithmic scale)
- **Three Lines**:
  - Purple: Oscillator
  - Orange: Median (365-day moving median)
  - Green: USD Price
- **Credits**: Attribution to @BitboBTC and @hcburger1
- **BiTBO Logo**: Displayed at bottom center

## References

- Inspired by [Bitbo Charts - Power Law Oscillator](https://charts.bitbo.io/power-law-oscillator/)
- Created by: @BitboBTC
- Inspired by: @hcburger1
