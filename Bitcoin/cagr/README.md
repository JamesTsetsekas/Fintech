# Compound Annual Growth Rate (CAGR) Chart

Creates a visualization showing Bitcoin's Compound Annual Growth Rate (CAGR) over different time periods.

## Features

The chart displays:
- **Left Chart**: Bitcoin Price History with CAGR lines overlaid (straight lines from past price points to current price)
- **Right Chart**: CAGR Over Network Age showing how different CAGRs (4, 6, 8, 10, 12 years) evolve as Bitcoin's network matures
- **Header**: Current price and various CAGR values

## Requirements

Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

Run the script:

```bash
python3 cagr.py
```

The script will:
1. Load Bitcoin price data from `../price.csv`
2. Calculate CAGRs for 4, 6, 8, 10, and 12-year periods
3. Generate the chart and save it as `cagr.png`
4. Display the chart (if running in an environment with display capabilities)

## CAGR Calculation

CAGR is calculated using the formula:
```
CAGR = ((End Value / Start Value) ^ (1 / Years)) - 1
```

The script calculates CAGRs from various historical points to the current date, showing how Bitcoin's growth rate has changed over time.

## Output

- **Image**: `cagr.png` - High-resolution (300 DPI) chart with black background
- **Console**: Current price and CAGR values for each period

