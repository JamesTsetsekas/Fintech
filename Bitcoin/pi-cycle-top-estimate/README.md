# Bitcoin Pi Cycle Top Future Cross Estimate

This script generates a Bitcoin Pi Cycle Top Future Cross Estimate chart that predicts potential future peaks in Bitcoin's price cycles by analyzing when the 111-day and 350-day moving averages might intersect.

## Description

The Pi Cycle Top indicator is a tool designed to predict potential future peaks in Bitcoin's price cycles. It analyzes the slopes of two key moving averages—the 111-day moving average (111DMA) and the 350-day moving average multiplied by two (350DMA x2)—over the past 10 days. By extrapolating these slopes into the future, the chart estimates when these moving averages might intersect, which could signal an upcoming Pi Cycle Top.

## Features

- **111-Day SMA**: Short-to-medium term moving average (cyan line)
- **350-Day SMA × 2**: Long-term moving average multiplied by 2 (magenta line)
- **Price (USD)**: Actual Bitcoin price (gold line)
- **Future Projection**: Extrapolates moving average slopes to estimate potential cross points
- **Cross Detection**: Identifies if and when the moving averages are projected to cross

## Usage

```bash
cd Bitcoin/pi-cycle-top-estimate
python3 pi_cycle_top_estimate.py
```

The script will:
1. Load price data from `../price.csv`
2. Calculate 111-day SMA
3. Calculate 350-day SMA and multiply by 2
4. Analyze slopes over the past 10 days
5. Project moving averages forward up to 1 year
6. Detect if/when a cross is projected
7. Generate and display the chart
8. Save the chart as `pi_cycle_top_estimate.png` (300 DPI)

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
- **Logarithmic Y-Axis**: Price scale from $5,000 to $200,000
- **Three Lines**:
  - Gold: Price (USD)
  - Cyan: SMA111d (111-day Simple Moving Average)
  - Magenta: SMA350d X 2 (350-day SMA multiplied by 2)
- **Projected Lines**: Dashed lines showing future projections
- **Cross Annotation**: 
  - Green box with "No Projected Cross" if lines won't cross
  - Yellow box with projected cross date if a cross is detected
- **Credits**: Attribution to @BitboBTC and @PositiveCrypto
- **Time Range**: Shows data from January 2020 onwards with projection up to 1 year ahead

## How It Works

1. **Moving Average Calculation**: 
   - Calculates 111-day and 350-day simple moving averages
   - Multiplies the 350-day SMA by 2

2. **Slope Analysis**:
   - Analyzes the slopes of both moving averages over the past 10 days
   - Uses linear regression to determine the trend direction

3. **Future Projection**:
   - Extrapolates the moving averages forward based on their current slopes
   - Projects up to 365 days into the future

4. **Cross Detection**:
   - Checks if the projected lines will intersect
   - Identifies the date of potential intersection
   - Displays appropriate annotation

## References

- Inspired by [Bitbo Charts - Pi Cycle Top Future Cross Estimate](https://charts.bitbo.io/pi-cycle-top-estimate/)
- Charts by: @BitboBTC
- Model by: @PositiveCrypto

## Note

This chart provides insights based on historical patterns and mathematical projections. It should not be considered financial advice. Always conduct your own research before making any investment decisions.

