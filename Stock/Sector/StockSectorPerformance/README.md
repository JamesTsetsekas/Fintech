# Stock Sector Performance Tool

This tool compares performance across different sectors using sector ETFs and representative stocks.

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

### Basic Usage

Run the analysis with default sector ETFs:
```bash
python3 stock_sector_performance.py
```

### Specifying Time Period

Analyze different time periods:
```bash
python3 stock_sector_performance.py --period 1y    # 1 year
python3 stock_sector_performance.py --period 2y    # 2 years
python3 stock_sector_performance.py --period 5y    # 5 years
python3 stock_sector_performance.py --period 10y   # 10 years
```

### Command-Line Options

```
--period PERIOD
    Time period for analysis (default: 1y)
    Examples: 1y, 2y, 5y, 10y
```

## What it does

1. **Downloads sector ETF data** from Yahoo Finance:
   - Technology (XLK)
   - Healthcare (XLV)
   - Financials (XLF)
   - Consumer Discretionary (XLY)
   - Communication Services (XLC)
   - Industrials (XLI)
   - Consumer Staples (XLP)
   - Energy (XLE)
   - Utilities (XLU)
   - Real Estate (XLRE)
   - Materials (XLB)

2. **If ETFs fail**, falls back to representative stocks for each sector

3. **Calculates performance metrics**:
   - Total return percentage
   - Annualized return percentage
   - Volatility (annualized)
   - Final normalized value

4. **Creates four visualizations**:
   - **Top left**: Normalized sector performance over time (all start at 100)
   - **Top right**: Bar chart ranking sectors by total return
   - **Bottom left**: Risk-return scatter plot (volatility vs return)
   - **Bottom right**: Monthly returns heatmap showing performance by month

The output is saved as `stock_sector_performance.png` showing comprehensive sector analysis.

## Understanding the Charts

- **Normalized Performance**: All sectors start at 100, making it easy to compare relative performance
- **Total Returns**: Shows which sectors have performed best over the period
- **Risk-Return Profile**: Higher volatility (x-axis) vs higher returns (y-axis). Ideal sectors are in the top-left (high return, low risk)
- **Monthly Returns Heatmap**: Shows which sectors performed well in which months (green = positive, red = negative)

## Sector ETFs Used

The tool uses SPDR sector ETFs (XLK, XLV, etc.) which are widely recognized sector benchmarks. If an ETF is unavailable, it uses representative stocks from that sector.

