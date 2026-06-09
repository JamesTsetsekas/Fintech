# Bitcoin Power Law Chart
AI Gen: 

The Bitcoin power law chart is a long-term price model that suggests Bitcoin's price follows a power law function over time. This model, unlike traditional linear or exponential growth models used in stock markets, posits that Bitcoin's price scales in a predictable, non-random way over the long run, indicating a structured mathematical pattern based on time rather than purely speculative movements.   

The chart is typically constructed by plotting Bitcoin's historical price data on a log-log scale, where both the time and price axes use logarithms. This scaling helps to reveal long-term growth trends while smoothing out short-term volatility. A power function of the form $\(P(t) = a \cdot t^b\)$ is then applied to this data, where $\(P(t)\)$ represents Bitcoin's price at time $\(t\)$, and $\(a\)$ and $\(b\)$ are constants determined by historical data. The variable $\(t\)$ usually represents the time since Bitcoin's inception, often measured in days or years. The model also includes upper and lower bounds, creating price bands that illustrate the historical range within which Bitcoin's price has fluctuated relative to the long-term trend. These bands can be used to identify potential overbought or oversold conditions.

The Bitcoin power law model offers a simple and visual way to assess Bitcoin's long-term price trend, suggesting that its growth follows a consistent pattern throughout history. By focusing on multi-year trends, it aims to help investors make more rational decisions, avoiding emotional reactions to short-term market fluctuations. When plotted on a logarithmic chart, the power law curve provides an intuitive visual guide to determine if Bitcoin is relatively overvalued or undervalued.

However, it's crucial to acknowledge the risks and shortcomings of this model. It assumes that past trends will continue, which may not hold true if future adoption slows or if unexpected challenges arise. The model also does not account for market and economic events, such as regulations, macroeconomic shifts, or major technological changes, that could significantly impact Bitcoin's price. As it is based entirely on historical price patterns, there's a risk of overfitting, and the model may not adapt if Bitcoin's growth trajectory changes. Additionally, Bitcoin's price can deviate from the predicted range, making it an unreliable sole tool for forecasting. Unlike other models like Stock-to-Flow, the power law model does not factor in Bitcoin's supply schedule, such as halvings. Investors should, therefore, exercise caution and use the power law chart in conjunction with other analysis methods and a comprehensive understanding of market dynamics.

## First Chart 
![BTC 1](./img/fig1.svg)

## Second Chart 
![BTC 2](./img/fig2.svg)

## Third Chart 
![BTC 3](./img/fig3.svg)

## Updating Price Data

To keep the power law charts up to date with the latest Bitcoin price data:

### Option 1: Manual Download and Convert

1. Download the latest Bitcoin historical data from [CoinMarketCap](https://coinmarketcap.com/currencies/bitcoin/historical-data/)
   - Set the date range (e.g., from 2008-01-01 to today)
   - Download as CSV

2. **IMPORTANT: Use --merge to preserve existing data!**
   ```bash
   cd ..  # Go to Bitcoin folder where update_bitcoin_data.py is located
   python update_bitcoin_data.py --input-file Bitcoin_historical_data_coinmarketcap.csv --merge
   ```
   
   This will:
   - Convert the CoinMarketCap CSV format to price.csv format
   - Merge new data with existing price.csv (only adds dates that don't already exist)
   - Preserve all historical data from 2008 onwards
   - Update the shared price.csv file used by all Bitcoin charts

3. ⚠️ **Warning**: Without --merge, the script will overwrite your entire price.csv file!

### Option 2: Automatic Download (Requires cryptocmd)

1. Install the required dependency:
   ```bash
   pip install cryptocmd
   ```

2. Download and convert automatically:
   ```bash
   cd ..  # Go to Bitcoin folder where update_bitcoin_data.py is located
   python update_bitcoin_data.py --download --merge
   ```

### Option 3: Replace Data for a Specific Year (Fix Errors)

If you need to fix data for a specific year (e.g., 2024 has errors):

1. Download the corrected data for that year from [CoinMarketCap](https://coinmarketcap.com/currencies/bitcoin/historical-data/)
   - Set the date range for the year you want to fix (e.g., 2024-01-01 to 2024-12-31)
   - Download as CSV

2. Replace the data for that year:
   ```bash
   cd ..  # Go to Bitcoin folder where update_bitcoin_data.py is located
   python update_bitcoin_data.py --input-file Bitcoin_1_1_2024-12_31_2024_historical_data_coinmarketcap.csv --replace-year 2024
   ```
   
   This will:
   - Remove all existing 2024 data from price.csv
   - Add the corrected 2024 data from your CSV file
   - Preserve all other years' data
   - Update the shared price.csv file used by all Bitcoin charts

### Requirements

Install dependencies:
```bash
pip install -r requirements.txt
```

## Buy me a Coffee: 
BTC: bc1q2kqvggm552h0csyr0awa2zepdapxdqnacw0z5w

![BTC](https://raw.githubusercontent.com/lcsig/API-Hooking/refs/heads/master/img/btc.png)
