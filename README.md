# Fintech

A comprehensive collection of Bitcoin on-chain analytics, market cycle indicators, and stock analysis tools. Each tool generates publication-quality charts with dark themes, built in Python using matplotlib.

## Web Dashboard

The repo includes a static, GitHub Pages-friendly dashboard at `index.html`. The source branch is kept history-light: generated PNGs, downloaded CSV snapshots, and generated `web/data/` JSON are ignored by git.

The cron runner generates the latest reports locally, builds the static dashboard data, and force-publishes a latest-only `gh-pages` branch. This keeps chart output available on GitHub Pages without committing every hourly chart refresh to `main`.

## Bitcoin Analytics

### Price Models & Cycle Indicators

#### Power Law
Long-term price model plotting Bitcoin on a log-log scale with Bitbo-style Power Law constants and support/resistance bands.

![Power Law](https://jamestsetsekas.github.io/Fintech/Bitcoin/power-law/power_law.png)

#### Rainbow Chart
Halving Price Regression (HPR) model with six color-coded bands (Low → Red) calculated from prices at the three halving dates. Useful for gauging where we are in the cycle.

![Rainbow Chart](https://jamestsetsekas.github.io/Fintech/Bitcoin/rainbow/rainbow_chart.png)

#### Power Law Oscillator
Measures deviation from the power law trend line, oscillating between oversold and overbought zones.

![Power Law Oscillator](https://jamestsetsekas.github.io/Fintech/Bitcoin/power-law-oscillator/power_law_oscillator.png)

#### Pi Cycle Top Indicator
Uses the 111-day MA and 350-day MA x2 crossover to signal potential market tops. The ratio (350/111 ≈ 3.153) approximates Pi.

![Pi Cycle Top](https://jamestsetsekas.github.io/Fintech/Bitcoin/pi-cycle-top/pi_cycle_top.png)

#### Pi Cycle Top Estimate
Extended version projecting when the next Pi Cycle crossover might occur based on current trajectory.

![Pi Cycle Top Estimate](https://jamestsetsekas.github.io/Fintech/Bitcoin/pi-cycle-top-estimate/pi_cycle_top_estimate.png)

#### Model Price Prediction
Concise overview chart showing spot price, Stock-to-Flow, and Power Law together, while detailed Rainbow/HPR and Power Law band views remain in their dedicated charts.

![Model Price Prediction](https://jamestsetsekas.github.io/Fintech/Bitcoin/model_price_prediction/model_price_prediction.png)

#### Cycle Phase Dashboard
Compact cycle snapshot combining trend, drawdown, halving progress, Puell, fees, and volatility gauges.

![Cycle Phase Dashboard](https://jamestsetsekas.github.io/Fintech/Bitcoin/cycle_phase_dashboard/cycle_phase_dashboard.png)

#### Regime Mosaic
Monthly state map showing how Bitcoin moves across trend, Mayer, Puell, drawdown, and volatility regimes over time.

![Regime Mosaic](https://jamestsetsekas.github.io/Fintech/Bitcoin/regime_mosaic/regime_mosaic.png)

#### Price Acceptance Heatmap
Heatmap showing where BTC spent the most time by price bucket, both by calendar year and by halving epoch, using repo-local 10-minute prices.

![Price Acceptance Heatmap](https://jamestsetsekas.github.io/Fintech/Bitcoin/price_acceptance_heatmap/price_acceptance_heatmap.png)

#### Price Prediction (Machine Learning)
Random Forest classifier predicting next-day price direction using features like daily % change, 7/21/200-day moving averages, and volatility measures.

![Price Prediction](https://jamestsetsekas.github.io/Fintech/Bitcoin/price_prediction/price_prediction.png)

---

### Halving & Epoch Analysis

#### Halving Cycles
Price performance across halving cycles normalized by block height, showing multipliers from cycle start on a log scale.

![Halving Cycles](https://jamestsetsekas.github.io/Fintech/Bitcoin/halving_cycles/halving_cycles.png)

#### Halving Phase Compass
Polar chart where one full rotation equals a halving epoch and radius shows the price multiple since that halving began.

![Halving Phase Compass](https://jamestsetsekas.github.io/Fintech/Bitcoin/halving_phase_compass/halving_phase_compass.png)

#### Halving Era ROI Heatmap
Month-by-month ROI heatmap for each halving epoch, normalized from that epoch's first post-halving daily close.

![Halving Era ROI Heatmap](https://jamestsetsekas.github.io/Fintech/Bitcoin/halving_era_roi_heatmap/halving_era_roi_heatmap.png)

#### Epoch Candles
Price history divided into halving epochs with multipliers showing the price increase during each period.

![Epoch Candles](https://jamestsetsekas.github.io/Fintech/Bitcoin/epoch_candles/epoch_candles.png)

#### Epoch-Over-Epoch Growth
Stacked area chart of epochs (E1-E5) with color-coded growth percentages showing diminishing returns across cycles.

![EOE Growth](https://jamestsetsekas.github.io/Fintech/Bitcoin/eoe_growth/eoe_growth.png)

---

### Technical Analysis

#### 200 DMA & 200 WMA
Three-panel chart showing Bitcoin with 200-day and 200-week moving averages across full history (log), 200-day window (linear), and 200-week window (linear).

![200 DMA 200 WMA](https://jamestsetsekas.github.io/Fintech/Bitcoin/200_dma_200_wma/200_dma_200_wma.png)

#### Mayer Multiple
BTC price divided by the 200-day moving average, with classic cycle zones for below-trend and overheated regimes.

![Mayer Multiple](https://jamestsetsekas.github.io/Fintech/Bitcoin/mayer_multiple/mayer_multiple.png)

#### Bollinger Bands
20-period SMA with upper/lower bands at 2 standard deviations. Includes a main chart (last 2 years) and mini chart (full history).

![Bollinger Bands](https://jamestsetsekas.github.io/Fintech/Bitcoin/bollinger-bands/bollinger_bands.png)

#### Volatility Regimes
Rolling realized volatility with percentile bands to distinguish low, high, and extreme volatility regimes.

![Volatility Regimes](https://jamestsetsekas.github.io/Fintech/Bitcoin/volatility_regimes/volatility_regimes.png)

#### Intraday Volatility Heatmap
Weekday-hour and month-hour heatmaps of annualized realized volatility from repo-local 10-minute BTC/USD returns.

![Intraday Volatility Heatmap](https://jamestsetsekas.github.io/Fintech/Bitcoin/intraday_volatility_heatmap/intraday_volatility_heatmap.png)

#### Distance From 200DMA Heatmap
Monthly regime map showing how often BTC trades at different percentage distances above or below its 200-day moving average.

![Distance From 200DMA Heatmap](https://jamestsetsekas.github.io/Fintech/Bitcoin/distance_from_200dma_heatmap/distance_from_200dma_heatmap.png)

---

### Returns & Performance

#### Monthly & Yearly Returns
Heatmap table showing monthly and yearly returns over the last 10 years, color-coded from red (losses) to green (gains).

![Monthly Yearly Returns](https://jamestsetsekas.github.io/Fintech/Bitcoin/monthly_yearly_returns/monthly_yearly_returns.png)

#### Quarterly & Yearly Returns
Same concept as above but broken down by quarters instead of months.

![Quarterly Yearly Returns](https://jamestsetsekas.github.io/Fintech/Bitcoin/quarterly_yearly_returns/quarterly_yearly_returns.png)

#### CAGR (Compound Annual Growth Rate)
Dual-panel chart showing Bitcoin price with CAGR lines overlaid, and CAGR evolution over network age.

![CAGR](https://jamestsetsekas.github.io/Fintech/Bitcoin/cagr/cagr.png)

#### Risk-Adjusted Returns
Rolling Sharpe and Sortino proxies using Bitcoin daily log returns with zero risk-free rate, plus annualized return and volatility.

![Risk Adjusted Returns](https://jamestsetsekas.github.io/Fintech/Bitcoin/risk_adjusted_returns/risk_adjusted_returns.png)

#### Return-Volatility Map
Monthly phase-space chart of annualized return versus realized volatility, grouped by halving epoch and overlaid with the recent path.

![Return Volatility Map](https://jamestsetsekas.github.io/Fintech/Bitcoin/return_volatility_map/return_volatility_map.png)

#### Seasonality Heatmap
Return seasonality maps for the 24/7 trading week and the calendar year, using intraday mean returns and daily hit rates.

![Seasonality Heatmap](https://jamestsetsekas.github.io/Fintech/Bitcoin/seasonality_heatmap/seasonality_heatmap.png)

---

### Price History & Drawdowns

#### Monthly Candlesticks
Aggregates daily data into monthly OHLC candles on a log scale.

![Monthly Candles](https://jamestsetsekas.github.io/Fintech/Bitcoin/monthly_candles/monthly_candles.png)

#### Yearly Candlesticks
Aggregates daily data into yearly OHLC candles on a log scale.

![Yearly Candles](https://jamestsetsekas.github.io/Fintech/Bitcoin/yearly_candles/yearly_candles.png)

#### Yearly Windows
2x2 grid showing 1Y, 2Y, 3Y, and 4Y price windows with open/high/low/close and percentage changes.

![Yearly Windows](https://jamestsetsekas.github.io/Fintech/Bitcoin/yearly_windows/yearly_windows.png)

#### Cycle High Drawdown
Compares drawdown percentages from cycle highs across multiple historical cycles, overlaid for pattern comparison.

![Cycle High Drawdown](https://jamestsetsekas.github.io/Fintech/Bitcoin/cycle_high_drawdown/cycle_high_drawdown.png)

#### Drawdown Recovery Map
Maps ATH drawdowns against recovery duration, highlighting the deepest historical underwater periods.

![Drawdown Recovery Map](https://jamestsetsekas.github.io/Fintech/Bitcoin/drawdown_recovery_map/drawdown_recovery_map.png)

#### Drawdown Duration Heatmap
Shows how long each major peak-to-recovery drawdown spent in different underwater depth buckets.

![Drawdown Duration Heatmap](https://jamestsetsekas.github.io/Fintech/Bitcoin/drawdown_duration_heatmap/drawdown_duration_heatmap.png)

#### Days Since ATH
Dashboard with BTCUSD price chart and days-since-ATH counter, showing halving events and cycle peaks.

![Days Since ATH](https://jamestsetsekas.github.io/Fintech/Bitcoin/days_since_ath/days_since_ath.png)

#### Days at a Loss
Shows how many days purchases at each price point have spent underwater, with a gradient heatmap.

![Days at a Loss](https://jamestsetsekas.github.io/Fintech/Bitcoin/days_at_a_loss/days_at_a_loss.png)

#### Never Look Back Price
Tracks the highest price Bitcoin reached and never fell below again.

![Never Look Back Price](https://jamestsetsekas.github.io/Fintech/Bitcoin/never_look_back_price/never_look_back_price.png)

---

### On-Chain & Supply

#### HODL Waves
Stacked area chart showing Bitcoin supply distribution by holding duration (short/medium/long term) with price overlay.

![HODL Waves](https://jamestsetsekas.github.io/Fintech/Bitcoin/hodl_waves_price/hodl_waves_price.png)

#### Puell Multiple
Miner revenue in USD divided by its 365-day moving average, with historical accumulation and overheated zones.

![Puell Multiple](https://jamestsetsekas.github.io/Fintech/Bitcoin/puell_multiple/puell_multiple.png)

#### Fee Pressure
Fees, fee share of miner revenue, and block-space fee rate using repo-local block CSV data.

![Fee Pressure](https://jamestsetsekas.github.io/Fintech/Bitcoin/fee_pressure/fee_pressure.png)

#### Fee Pressure Heatmap
Heatmap of monthly block-space congestion, showing how much of each month lived in each historical fee-rate percentile bucket.

![Fee Pressure Heatmap](https://jamestsetsekas.github.io/Fintech/Bitcoin/fee_pressure_heatmap/fee_pressure_heatmap.png)

#### Miner Hashprice
Miner revenue per PH/s/day using difficulty-implied network hashrate and repo-local miner revenue.

![Miner Hashprice](https://jamestsetsekas.github.io/Fintech/Bitcoin/miner_hashprice/miner_hashprice.png)

#### Node Count
Visualizes Bitcoin network node counts and software version distribution over time.

![Node Count](https://jamestsetsekas.github.io/Fintech/Bitcoin/node_count/node_count.png)

#### Price Distribution
Historical price trend with halving events and distribution of daily closing prices across price ranges.

![Price Distribution](https://jamestsetsekas.github.io/Fintech/Bitcoin/price_distribution/price_distribution.png)

#### DCA Cost Basis
Weighted average cost basis for daily Dollar-Cost Averaging over different durations vs. spot price.

![DCA Cost Basis](https://jamestsetsekas.github.io/Fintech/Bitcoin/dca_cost_basis/dca_cost_basis.png)

#### Unit of Account (BTC/USD)
Dual chart: price of 1 USD in satoshis (left) and price of 1 BTC in USD (right).

![UOA BTC USD](https://jamestsetsekas.github.io/Fintech/Bitcoin/uoa_btc_usd/uoa_btc_usd.png)

---

## Stock Analysis

A suite of tools for equities analysis covering individual stocks, sector performance, correlations, technical indicators, and volatility. Supports custom stock lists, Dow 30, NASDAQ top 15, and S&P 500 groupings.

### Individual Stock Analysis

Comprehensive single-stock reports with price history, volume, and key metrics.

| | | |
|:---:|:---:|:---:|
| ![AAPL](https://jamestsetsekas.github.io/Fintech/Stock/IndividualStockAnalysis/AAPL_stock_analysis.png) | ![NVDA](https://jamestsetsekas.github.io/Fintech/Stock/IndividualStockAnalysis/NVDA_stock_analysis.png) | ![MSTR](https://jamestsetsekas.github.io/Fintech/Stock/IndividualStockAnalysis/MSTR_stock_analysis.png) |

### Performance Comparison

Side-by-side performance comparison across different stock groups.

| Default | S&P 500 Top 10 |
|:---:|:---:|
| ![Default](https://jamestsetsekas.github.io/Fintech/Stock/StockPerformanceComparison/stock_performance_comparison_default.png) | ![SP500](https://jamestsetsekas.github.io/Fintech/Stock/StockPerformanceComparison/stock_performance_comparison_sp500_top10.png) |

### Correlation Analysis

Hierarchical clustering of stock correlations to identify related groups and diversification opportunities.

| Default | NASDAQ Top 15 |
|:---:|:---:|
| ![Default](https://jamestsetsekas.github.io/Fintech/Stock/StockCorrelation/correlation_clusters_default.png) | ![NASDAQ](https://jamestsetsekas.github.io/Fintech/Stock/StockCorrelation/correlation_clusters_nasdaq_top15.png) |

### Technical Indicators

RSI, MACD, and Bollinger Bands for individual stocks. Generated for all Dow 30 components.

| AAPL | NVDA | MSFT |
|:---:|:---:|:---:|
| ![AAPL](https://jamestsetsekas.github.io/Fintech/Stock/StockTechnicalIndicators/AAPL_technical_indicators.png) | ![NVDA](https://jamestsetsekas.github.io/Fintech/Stock/StockTechnicalIndicators/NVDA_technical_indicators.png) | ![MSFT](https://jamestsetsekas.github.io/Fintech/Stock/StockTechnicalIndicators/MSFT_technical_indicators.png) |

### Volatility Analysis

Historical volatility metrics comparing stocks across different groups.

| Default | S&P 500 Top 10 |
|:---:|:---:|
| ![Default](https://jamestsetsekas.github.io/Fintech/Stock/StockVolatilityAnalysis/stock_volatility_analysis_default.png) | ![SP500](https://jamestsetsekas.github.io/Fintech/Stock/StockVolatilityAnalysis/stock_volatility_analysis_sp500_top10.png) |

---

## Getting Started

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
git clone https://github.com/JamesTsetsekas/Fintech.git
cd Fintech
```

### Run All Bitcoin Reports

```bash
cd Bitcoin
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt  # from any subfolder
python3 run_all_reports.py
```

Run selected Bitcoin reports without updating data:

```bash
python3 run_all_reports.py --skip-update --only puell --only volatility
```

Create a quick local contact sheet for visual QA:

```bash
python3 create_contact_sheet.py --only puell --only volatility
```

### Run All Stock Reports

```bash
cd Stock
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 run_all_reports.py
```

Each tool can also be run independently from its own directory.

### Updating Bitcoin Data

See [Bitcoin/data/UPDATE_INSTRUCTIONS.md](https://jamestsetsekas.github.io/Fintech/Bitcoin/data/UPDATE_INSTRUCTIONS.md) for keeping price and blockchain data current.

### Ubuntu Server Setup

For automated deployment and scheduled reports, see [SETUP_UBUNTU.md](SETUP_UBUNTU.md).

## License

MIT
