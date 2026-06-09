# Bitcoin Epoch Candles Chart

Creates a visualization showing Bitcoin's price history divided into halving epochs with multipliers for each epoch period.

## Features

The chart displays:
- **Bitcoin Price**: Orange line showing price history on logarithmic scale
- **Epochs**: Five halving cycles marked with green shaded bands
- **Multipliers**: Price increase multiplier for each epoch (e.g., x52.2, x13.5, x7.3)
- **Halving Dates**: Orange dots marking each Bitcoin halving event
- **Header**: Current price data (Open, High, Low, Close) and block height
- **Footer**: Creator information and website

## Epochs

The chart divides Bitcoin's history into five epochs based on halving events:

1. **Epoch 1** (Jan 3, 2010 - Nov 28, 2012): First halving cycle
2. **Epoch 2** (Nov 28, 2012 - Jul 9, 2016): Second halving cycle
3. **Epoch 3** (Jul 9, 2016 - May 11, 2020): Third halving cycle
4. **Epoch 4** (May 11, 2020 - Apr 20, 2024): Fourth halving cycle
5. **Epoch 5** (Apr 20, 2024 - Apr 10, 2028): Fifth halving cycle (projected)

Each epoch shows the price multiplier achieved during that period, demonstrating the diminishing returns trend across halving cycles.

## Requirements

Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

Run the script:

```bash
python3 epoch_candles.py
```

The script will:
1. Load Bitcoin price data from `../price.csv`
2. Calculate multipliers for each epoch period
3. Generate the chart and save it as `epoch_candles.png`
4. Display the chart (if running in an environment with display capabilities)

## Multiplier Calculation

The multiplier for each epoch is calculated as:
```
Multiplier = End Price / Start Price
```

Where:
- **Start Price**: Closing price at the beginning of the epoch (halving date)
- **End Price**: Closing price at the end of the epoch (next halving date, or current price for ongoing epoch)

## Output

- **Image**: `epoch_candles.png` - High-resolution (300 DPI) chart with black background
- **Console**: Current price, block height, and multiplier for each epoch

## Data Source

The script uses Bitcoin price data from `../price.csv` which should contain daily OHLC (Open, High, Low, Close) data with columns:
- `Start`: Start date of the period
- `End`: End date of the period
- `Open`: Opening price
- `High`: Highest price
- `Low`: Lowest price
- `Close`: Closing price

