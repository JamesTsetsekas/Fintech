# Stock Technical Indicators Tool

This tool analyzes and visualizes technical indicators including RSI, MACD, and Bollinger Bands for multiple stocks.

## Setup

Install the required dependencies:
```bash
pip3 install -r requirements.txt
```

If you encounter permission issues:
```bash
pip3 install --user -r requirements.txt
```

## Usage

### Basic Usage (Default Asset List)

Run the analysis with the default asset list:
```bash
python3 stock_technical_indicators.py
```

### Single Stock Analysis

Analyze a single stock in detail:
```bash
python3 stock_technical_indicators.py --source single --ticker AAPL
python3 stock_technical_indicators.py --source single --ticker TSLA
```

### Using a Custom Asset File

Create a text file (e.g., `assets.txt`) with one ticker per line:
```
AAPL
MSFT
GOOGL
NVDA
TSLA
```

Then run:
```bash
python3 stock_technical_indicators.py --source file
```

### Specifying Time Period

Analyze different time periods:
```bash
python3 stock_technical_indicators.py --period 6m    # 6 months
python3 stock_technical_indicators.py --period 1y    # 1 year
python3 stock_technical_indicators.py --period 2y    # 2 years
```

### Command-Line Options

```
--source {default,file,single}
    Data source to use (default: default)
    
--file PATH
    Path to file with tickers (used when --source=file, default: assets.txt)
    
--ticker TICKER
    Single ticker to analyze (used when --source=single, default: AAPL)
    
--period PERIOD
    Time period for analysis (default: 1y)
    Examples: 6m, 1y, 2y
```

## What it does

For each stock, the tool:

1. **Downloads stock data** from Yahoo Finance
2. **Calculates technical indicators**:
   - **RSI (Relative Strength Index)**: Momentum oscillator (0-100)
     - RSI > 70: Overbought (potential sell signal)
     - RSI < 30: Oversold (potential buy signal)
   - **MACD (Moving Average Convergence Divergence)**: Trend-following momentum indicator
     - MACD > Signal: Bullish
     - MACD < Signal: Bearish
   - **Bollinger Bands**: Volatility bands around price
     - Price near upper band: Potentially overbought
     - Price near lower band: Potentially oversold
3. **Creates a comprehensive chart** with 4 panels:
   - **Top panel**: Price with Bollinger Bands and SMA
   - **Second panel**: RSI with overbought/oversold levels
   - **Third panel**: MACD with signal line and histogram
   - **Bottom panel**: Volume (if available)

Each stock gets its own chart saved as `{TICKER}_technical_indicators.png`.

## Understanding the Indicators

### RSI (Relative Strength Index)
- Range: 0-100
- **> 70**: Overbought territory (potential reversal down)
- **< 30**: Oversold territory (potential reversal up)
- **30-70**: Neutral zone

### MACD (Moving Average Convergence Divergence)
- **MACD line**: Difference between 12-day and 26-day EMAs
- **Signal line**: 9-day EMA of MACD line
- **Histogram**: Difference between MACD and Signal
- **Bullish**: MACD crosses above Signal
- **Bearish**: MACD crosses below Signal

### Bollinger Bands
- **Middle band**: 20-day Simple Moving Average
- **Upper/Lower bands**: 2 standard deviations from SMA
- **Squeeze**: Bands close together = low volatility (potential breakout)
- **Expansion**: Bands widen = high volatility

## Example Output

The tool prints current indicator values to the console and generates PNG charts for each stock showing all indicators over time.

