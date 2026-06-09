# Pi Cycle Top Indicator

A Python script to visualize the Pi Cycle Top Indicator for Bitcoin, which uses two key moving averages to identify potential market tops.

## Description

The Pi Cycle Top Indicator was introduced by Philip Swift of LookIntoBitcoin in April 2019. It utilizes:

- **111-Day Moving Average (111DMA)**: Captures Bitcoin's short-term price trends
- **350-Day Moving Average Multiplied by 2 (350DMA x2)**: Long-term moving average adjusted by a factor of two

The ratio of 350 to 111 is approximately 3.153, closely resembling the mathematical constant Pi (3.142), which is the foundation of the indicator's name.

### How It Works

The indicator signals a potential market top when the 111DMA crosses above the 350DMA x2, suggesting that Bitcoin's price might have accelerated too rapidly, potentially indicating a peak in the current cycle. Historically, this crossover has preceded significant price corrections.

## Features

- Visualizes Bitcoin price with two key moving averages
- Logarithmic price scale for better visualization across Bitcoin's price history
- Dark theme matching Bitbo chart style
- Automatically saves chart as PNG image
- Opens interactive chart window

## Requirements

Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python pi_cycle_top.py
```

The script will:
1. Load Bitcoin price data from `../price.csv`
2. Calculate the 111-day and 350-day Simple Moving Averages
3. Create a chart with price, SMA111d, and SMA350d X 2
4. Save the chart as `pi_cycle_top.png`
5. Display the chart in an interactive window

## Data Source

The script expects a CSV file at `../price.csv` with the following columns:
- `Start`: Date in YYYY-MM-DD format
- `Close`: Closing price (USD)

## Chart Elements

- **Gold Line**: Bitcoin price (USD)
- **Cyan Line**: 111-day Simple Moving Average
- **Magenta Line**: 350-day Simple Moving Average multiplied by 2

## Credits

- Charts by: @BitboBTC
- Model by: @PositiveCrypto

## References

- [LookIntoBitcoin - Pi Cycle Top Indicator](https://charts.bitbo.io/pi-cycle-top/)
- Original concept by Philip Swift

