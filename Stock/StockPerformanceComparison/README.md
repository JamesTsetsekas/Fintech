# Stock Performance Comparison Tool

This tool compares the normalized performance of multiple stocks over time, showing which stocks have outperformed or underperformed relative to each other.

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
python3 stock_performance_comparison.py
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
```

Then run:
```bash
python3 stock_performance_comparison.py --source file
```

Or specify a custom file:
```bash
python3 stock_performance_comparison.py --source file --file my_tickers.txt
```

### Using Stock Indices

Analyze stocks from major indices:
```bash
python3 stock_performance_comparison.py --source sp500    # All S&P 500 stocks
python3 stock_performance_comparison.py --source nasdaq   # All NASDAQ-100 stocks
python3 stock_performance_comparison.py --source dow      # Dow Jones stocks
```

### Top N Stocks from Index

Get top N stocks by market cap, return, or volatility:
```bash
python3 stock_performance_comparison.py --source sp500 --top 10              # Top 10 by market cap
python3 stock_performance_comparison.py --source nasdaq --top 20 --metric return    # Top 20 by return
python3 stock_performance_comparison.py --source sp500 --top 15 --metric volatility  # Top 15 by volatility
```

### Sector Analysis

Analyze stocks from a specific sector:
```bash
python3 stock_performance_comparison.py --source sector --sector Technology
python3 stock_performance_comparison.py --source sector --sector Healthcare --top 5
```

Available sectors: Technology, Healthcare, Financials, Consumer Discretionary, Communication Services, Industrials, Consumer Staples, Energy, Utilities, Real Estate, Materials

### Specifying Time Period

Analyze different time periods:
```bash
python3 stock_performance_comparison.py --period 1y    # 1 year
python3 stock_performance_comparison.py --period 2y    # 2 years
python3 stock_performance_comparison.py --period 5y    # 5 years
python3 stock_performance_comparison.py --period 10y   # 10 years
```

Or use a specific date:
```bash
python3 stock_performance_comparison.py --period 2020-01-01
```

### Command-Line Options

```
--source {default,file,sp500,nasdaq,dow,sector}
    Data source to use (default: default)
    
--file PATH
    Path to file with tickers (used when --source=file, default: assets.txt)
    
--sector SECTOR
    Sector name (required when --source=sector)
    
--top N
    Return only top N stocks (by market cap, return, or volatility)
    
--metric {market_cap,return,volatility}
    Metric for top N selection (default: market_cap)
    
--period PERIOD
    Time period for analysis (default: 1y)
    Examples: 1y, 2y, 5y, 10y, or YYYY-MM-DD format
```

## What it does

1. **Downloads stock data** from Yahoo Finance for the specified period
2. **Normalizes all prices** to a starting value of 100 for easy comparison
3. **Calculates performance metrics**:
   - Total return percentage
   - Annualized return percentage
   - Final normalized value
4. **Creates two visualizations**:
   - **Top chart**: Normalized price performance over time (all stocks start at 100)
   - **Bottom chart**: Bar chart showing total return percentages

The output is saved as `stock_performance_comparison.png` showing which stocks have performed best over the selected time period.

## Example Output

The chart shows:
- All stocks normalized to start at 100, making it easy to see relative performance
- A horizontal bar chart ranking stocks by total return
- Performance summary table printed to console

