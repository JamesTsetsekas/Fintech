# Stock Correlation Analysis

This project implements Ray Dalio's principle of seeking uncorrelated returns by analyzing stock correlations using Riskfolio.

## Setup

### On macOS (using python3 and pip3):

1. Install the required dependencies:
```bash
pip3 install -r requirements.txt
```

If you encounter permission issues, you may need to use:
```bash
pip3 install --user -r requirements.txt
```

### Troubleshooting: Python Version Compatibility

If you get a `TypeError: unsupported operand type(s) for |` error, you're likely using Python 3.9 or earlier, but yfinance 1.0 requires Python 3.10+.

**Solution 1: Upgrade to Python 3.10+ (Recommended)**
yfinance 1.0 fixes critical bugs including data download failures. Upgrade Python first, then install:
```bash
pip3 install --upgrade yfinance==1.0
```

Note: The script now uses yfinance 1.0 which fixes the known bug where data downloads fail after September 28, 2025. This version requires Python 3.10+. The script also includes improved error handling and session management to avoid API blocking.

**Solution 2: Upgrade Python to 3.10+**
If you have Homebrew installed:
```bash
brew install python@3.11
python3.11 -m pip install --user -r requirements.txt
python3.11 stock_correlation_analysis.py
```

## Usage

### Basic Usage (Default Asset List)

Run the analysis script with the default expanded asset list:
```bash
python3 stock_correlation_analysis.py
```

### Using a Custom Asset File

Create a text file (e.g., `assets.txt`) with one ticker per line:
```
NVDA
AAPL
MSFT
GOOG
TSLA
DIS
MRK
JNJ
HD
```

Then run:
```bash
python3 stock_correlation_analysis.py --source file
```

Or specify a custom file:
```bash
python3 stock_correlation_analysis.py --source file --file my_tickers.txt
```

### Analyzing Index Constituents

To analyze all S&P 500 stocks:
```bash
python3 stock_correlation_analysis.py --source sp500
```

To analyze all NASDAQ-100 stocks:
```bash
python3 stock_correlation_analysis.py --source nasdaq
```

**Note:** Analyzing full indices (500+ stocks) will take significantly longer due to API rate limits. The script includes delays to avoid rate limiting.

### Command-Line Options

```
--source {default,file,sp500,nasdaq}
    Data source to use (default: default)
    
--file PATH
    Path to file with tickers (used when --source=file, default: assets.txt)
```

### Optional: Create aliases for convenience

To use `python` and `pip` instead of `python3` and `pip3`, add these to your `~/.zshrc`:
```bash
alias python='python3'
alias pip='pip3'
```

Then reload your shell:
```bash
source ~/.zshrc
```

## What it does

1. **Downloads stock data** from Yahoo Finance. The default list includes:
   - Tech stocks: NVDA, AAPL, MSFT, GOOG, TSLA, PANW, etc.
   - Financial: AXP, PFG, NTRS, STT, BX, etc.
   - Healthcare: MRK, JNJ, etc.
   - Consumer: DIS, HD, ULTA, DRI, etc.
   - Energy: FANG, VLO, etc.
   - And many more (45+ stocks total)
   - Plus: GLD (Gold ETF) and ^GSPC (S&P 500 benchmark)

2. **Converts prices to returns** and calculates median returns

3. **Creates a hierarchical dendrogram** showing correlation clusters between stocks using Pearson correlation

The output will be saved as `correlation_clusters.png` showing which stocks are most correlated with each other.


