# Stock Volatility Analysis Tool

This tool analyzes volatility metrics including rolling volatility, beta (relative to S&P 500), and volatility comparison across multiple stocks.

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
python3 stock_volatility_analysis.py
```

### Using a Custom Asset File

Create a text file (e.g., `assets.txt`) with one ticker per line:
```
AAPL
MSFT
GOOGL
AMZN
NVDA
TSLA
SPY
```

Then run:
```bash
python3 stock_volatility_analysis.py --source file
```

### Specifying Time Period and Window

Analyze different time periods:
```bash
python3 stock_volatility_analysis.py --period 1y    # 1 year
python3 stock_volatility_analysis.py --period 2y    # 2 years
python3 stock_volatility_analysis.py --period 5y    # 5 years
```

Change the rolling window:
```bash
python3 stock_volatility_analysis.py --window 20    # 20-day window
python3 stock_volatility_analysis.py --window 60   # 60-day window
```

### Command-Line Options

```
--source {default,file}
    Data source to use (default: default)
    
--file PATH
    Path to file with tickers (used when --source=file, default: assets.txt)
    
--period PERIOD
    Time period for analysis (default: 1y)
    Examples: 1y, 2y, 5y
    
--window DAYS
    Rolling window for volatility calculation (default: 30 days)
```

## What it does

1. **Downloads stock data** from Yahoo Finance for the specified period
2. **Calculates volatility metrics**:
   - Annualized volatility (standard deviation of returns × √252)
   - Rolling volatility over time
   - Beta (relative to S&P 500, if SPY or ^GSPC is included)
   - Maximum drawdown
3. **Creates four visualizations**:
   - **Top chart**: Rolling volatility over time for all stocks
   - **Top left**: Bar chart comparing annual volatility
   - **Top right**: Beta comparison (if benchmark available)
   - **Bottom**: Box plot showing volatility distribution

The output is saved as `stock_volatility_analysis.png` showing comprehensive volatility metrics.

## Understanding the Metrics

- **Annual Volatility**: Standard deviation of daily returns, annualized. Higher = more volatile
- **Beta**: Measures sensitivity to market movements. Beta > 1 = more volatile than market, Beta < 1 = less volatile
- **Max Drawdown**: Largest peak-to-trough decline during the period
- **Rolling Volatility**: Shows how volatility changes over time

## Note

For beta calculations, include SPY (S&P 500 ETF) or ^GSPC (S&P 500 index) in your asset list. The tool will automatically use it as the benchmark.

