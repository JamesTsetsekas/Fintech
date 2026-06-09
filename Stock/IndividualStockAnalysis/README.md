# Individual Stock Analysis Tool

Comprehensive analysis tool for individual stocks including overview, options data, volume analysis, technical indicators, and key metrics.

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

Analyze a stock (default is MSTR):
```bash
python3 individual_stock_analysis.py --ticker MSTR
```

### Analyze Different Stocks

```bash
python3 individual_stock_analysis.py --ticker AAPL
python3 individual_stock_analysis.py --ticker TSLA
python3 individual_stock_analysis.py --ticker NVDA
```

### Specify Time Period

```bash
python3 individual_stock_analysis.py --ticker MSTR --period 6m    # 6 months
python3 individual_stock_analysis.py --ticker MSTR --period 2y    # 2 years
python3 individual_stock_analysis.py --ticker MSTR --period 5y    # 5 years
```

### Options Analysis

Change the options expiration window:
```bash
python3 individual_stock_analysis.py --ticker MSTR --options-days 45    # 45 days out
python3 individual_stock_analysis.py --ticker MSTR --options-days 7     # 7 days out
```

### Command-Line Options

```
--ticker TICKER
    Stock ticker symbol to analyze (default: MSTR)
    
--period PERIOD
    Time period for historical analysis (default: 1y)
    Examples: 6m, 1y, 2y, 5y
    
--options-days DAYS
    Number of days out for options analysis (default: 30)
```

## What it does

The tool provides a comprehensive analysis including:

### 1. Stock Overview
- Company name, sector, industry
- Current price and market cap
- Key financial metrics

### 2. Performance Metrics
- Total return over the period
- Annualized return
- Volatility (annualized)
- Maximum drawdown

### 3. Technical Indicators
- **RSI (14)**: Relative Strength Index with overbought/oversold levels
- **MACD**: Moving Average Convergence Divergence with signal line
- **Bollinger Bands**: Volatility bands around price
- **Moving Averages**: SMA 20, 50, 200

### 4. Volume Analysis
- Volume bars colored by price direction
- Average volume comparison
- Volume ratio (current vs average)

### 5. Options Data
- Call options volume by strike price
- Put options volume by strike price
- Open interest analysis
- Near-the-money options focus

### 6. Statistical Analysis
- Daily returns distribution
- Drawdown visualization
- Risk metrics

## Output

The tool generates:
- **Console output**: Summary metrics and options data
- **PNG chart**: `{TICKER}_stock_analysis.png` with comprehensive visualizations

## Chart Layout

The generated chart includes 9 panels:
1. **Price Action**: Price with moving averages and Bollinger Bands
2. **Volume**: Volume bars with average volume line
3. **RSI**: Relative Strength Index
4. **MACD**: MACD with signal line and histogram
5. **Returns Distribution**: Histogram of daily returns
6. **Drawdown**: Drawdown over time
7. **Call Options Volume**: Volume by strike price for calls
8. **Put Options Volume**: Volume by strike price for puts
9. **Key Metrics Summary**: Text summary of all metrics

## Example: MSTR Analysis

```bash
python3 individual_stock_analysis.py --ticker MSTR --period 1y --options-days 30
```

This will analyze MicroStrategy (MSTR) with:
- 1 year of historical data
- Options data for the nearest expiration within 30 days
- Comprehensive technical and fundamental analysis

## Notes

- **Options data**: Not all stocks have options. The tool will gracefully handle missing options data.
- **Volume data**: Some stocks may have limited volume data. The tool handles missing data gracefully.
- **Market cap**: May not be available for all stocks depending on data source.
- **API rate limiting**: The tool includes appropriate delays to avoid rate limiting.

## Use Cases

- **Stock research**: Comprehensive overview before investing
- **Options trading**: Analyze options volume and open interest
- **Technical analysis**: All major technical indicators in one view
- **Risk assessment**: Volatility, drawdown, and return metrics
- **Volume analysis**: Identify unusual volume patterns

