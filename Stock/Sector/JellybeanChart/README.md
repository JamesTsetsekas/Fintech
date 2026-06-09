# Jellybean Chart - Annual Sector Returns Visualization

Creates a colorful table showing annual returns by sector, similar to traditional jellybean charts used in financial planning and portfolio analysis.

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

Run with default year range (2005 to current year):
```bash
python3 jellybean_chart.py
```

### Custom Year Range

Specify start and end years:
```bash
python3 jellybean_chart.py --start 2010 --end 2024
```

### Using Period

Use a period to calculate the range:
```bash
python3 jellybean_chart.py --period 10y   # Last 10 years
python3 jellybean_chart.py --period 15y   # Last 15 years
```

### Command-Line Options

```
--start YEAR
    Start year for analysis (default: 2005)

--end YEAR
    End year for analysis (default: current year)

--period PERIOD
    Time period (e.g., 10y, 15y) - overrides start/end if specified
```

## What it does

1. **Downloads sector ETF data** from Yahoo Finance for the specified years:
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

2. **Falls back to representative stocks** if ETFs fail to download

3. **Calculates annual returns** for each sector for each year

4. **Creates a jellybean chart** showing:
   - **Main table**: Annual returns for each sector by year, color-coded by sector
   - **BEST row**: Highlights the top-performing sector for each year
   - **WORST row**: Highlights the worst-performing sector for each year
   - **ANNUALIZED RETURN column**: Shows the annualized return for each sector over the entire period
   - **Color legend**: Maps each sector to its unique color
   - **Standard Deviation table**: Shows volatility for each sector

## Understanding the Chart

- **Color coding**: Each sector has a distinct color that appears consistently throughout the chart
- **Cell intensity**: Brighter/darker colors indicate higher absolute returns (positive or negative)
- **BEST/WORST rows**: Quickly identify which sectors performed best and worst each year
- **Annualized Return**: Shows long-term performance, accounting for compounding
- **Standard Deviation**: Measures volatility - higher values indicate more risk/volatility

## Output

The chart is saved as `jellybean_chart.png` with high resolution (300 DPI) suitable for presentations and reports.

## Use Cases

- **Portfolio Planning**: Understand which sectors have historically performed well
- **Risk Analysis**: Compare volatility across sectors
- **Trend Analysis**: Identify patterns in sector performance over time
- **Diversification**: See how different sectors perform relative to each other
- **Client Presentations**: Visual representation of market segment performance

