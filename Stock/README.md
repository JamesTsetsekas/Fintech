# Stock Analysis Tools

A collection of stock analysis and visualization tools for comparing performance, analyzing volatility, technical indicators, correlations, and sector performance.

## Structure

```
Stock/
├── run_all_reports.py          # Master script to run all reports
├── stock_utils.py              # Shared utilities for fetching stocks
├── StockCorrelation/           # Correlation analysis
├── StockPerformanceComparison/ # Performance comparison
├── StockVolatilityAnalysis/    # Volatility metrics
├── StockTechnicalIndicators/   # RSI, MACD, Bollinger Bands
├── IndividualStockAnalysis/   # Comprehensive single stock analysis
└── Sector/                     # Sector-related reports
    └── StockSectorPerformance/ # Sector performance comparison
```

## Quick Start

### Run All Reports

```bash
cd Stock
python3 run_all_reports.py
```

### Individual Reports

Each tool can be run independently. See individual README files in each folder for detailed usage.

## Common Features

All stock analysis tools support multiple data sources:

### 1. Custom Stock Lists
```bash
# From a file
python3 tool.py --source file --file assets.txt
```

### 2. Stock Indices
```bash
# S&P 500
python3 tool.py --source sp500

# NASDAQ-100
python3 tool.py --source nasdaq

# Dow Jones
python3 tool.py --source dow
```

### 3. Top N Stocks
```bash
# Top 10 by market cap
python3 tool.py --source sp500 --top 10

# Top 20 by return
python3 tool.py --source nasdaq --top 20 --metric return

# Top 15 by volatility
python3 tool.py --source sp500 --top 15 --metric volatility
```

### 4. Sector Analysis
```bash
# All stocks in Technology sector
python3 tool.py --source sector --sector Technology

# Top 5 Healthcare stocks by market cap
python3 tool.py --source sector --sector Healthcare --top 5
```

Available sectors:
- Technology
- Healthcare
- Financials
- Consumer Discretionary
- Communication Services
- Industrials
- Consumer Staples
- Energy
- Utilities
- Real Estate
- Materials

## Available Tools

### Stock Correlation Analysis
Analyzes correlation clusters between stocks using hierarchical clustering.
- Location: `StockCorrelation/`
- Output: `correlation_clusters.png`

### Stock Performance Comparison
Compares normalized performance of multiple stocks over time.
- Location: `StockPerformanceComparison/`
- Output: `stock_performance_comparison.png`

### Stock Volatility Analysis
Analyzes volatility metrics including rolling volatility, beta, and max drawdown.
- Location: `StockVolatilityAnalysis/`
- Output: `stock_volatility_analysis.png`

### Stock Technical Indicators
Analyzes RSI, MACD, and Bollinger Bands for individual stocks.
- Location: `StockTechnicalIndicators/`
- Output: `{TICKER}_technical_indicators.png` (one per stock)

### Individual Stock Analysis
Comprehensive analysis of a single stock including overview, options data, volume analysis, and technical indicators.
- Location: `IndividualStockAnalysis/`
- Output: `{TICKER}_stock_analysis.png`
- Example: `python individual_stock_analysis.py --ticker MSTR`

### Stock Sector Performance
Compares performance across 11 major sectors using sector ETFs.
- Location: `Sector/StockSectorPerformance/`
- Output: `stock_sector_performance.png`

## Shared Utilities

The `stock_utils.py` module provides:
- Index ticker fetching (S&P 500, NASDAQ-100, Dow)
- Sector ticker mapping
- Top N stock selection by market cap, return, or volatility
- File-based ticker loading

## Requirements

Each tool has its own `requirements.txt`. Common dependencies:
- pandas
- yfinance
- matplotlib
- numpy

Some tools require additional packages (e.g., `riskfolio-lib` for correlation analysis).

## Notes

- API rate limiting: Tools include delays to avoid rate limiting when fetching multiple stocks
- Time periods: Most tools support flexible time periods (1y, 2y, 5y, etc.)
- Error handling: Tools continue gracefully if individual stocks fail to download

