# Bitcoin Price Distribution Chart

Creates a visualization showing Bitcoin's historical price trend with halving events and a distribution of daily closing prices across various price ranges.

## Features

- **Main Price Chart**: Logarithmic scale price history from genesis to present
- **Halving Events**: Vertical dashed lines marking all four Bitcoin halving events
- **Price Distribution**: Horizontal bar chart showing the number of daily closes in each price range:
  - $10M - $100M
  - $1M - $10M
  - $100k - $1M
  - $10k - $100k
  - $1k - $10k
  - $100 - $1k
  - $10 - $100
  - $1 - $10
  - 10¢ - $1
  - 1¢ - 10¢
  - 0.1¢ - 1¢
  - 0.01¢ - 0.1¢
  - Not Valued (days when price was 0)

## Header Information

- Current date
- Block height (fetched from mempool.space API with fallback calculation)
- Current Bitcoin price (BTCUSD)
- Network age in days (since genesis block)

## Data Source

- Uses `daily_price.csv` from the Bitcoin data directory
- Requires daily price data with date, price, and block_height columns

## Installation

Install required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the script to generate the chart:

```bash
python3 price_distribution.py
```

The chart will be saved as `price_distribution.png` in the same directory.

## Output

The script generates a dark-themed chart (black background, orange Bitcoin elements) showing:
- Price history on a logarithmic scale
- Halving event markers with labels
- Price distribution breakdown
- Current statistics in the header
- Creator attribution in the footer

