# Days Since All-Time High (ATH) Chart

This script creates a visualization showing the number of days that have passed since Bitcoin's last All-Time High.

## Features

- **Orange line** that rises (days since ATH increases) and drops to near zero when a new ATH is reached
- **Vertical dashed lines** indicating new ATH events
- **Labels** for peak values in previous cycles
- **Header statistics** showing:
  - All-Time High price
  - Daily High price
  - Drawdown from ATH percentage
  - Current days since ATH

## Requirements

Install the required packages:

```bash
pip install pandas matplotlib numpy
```

Or use the requirements file from the parent directory.

## Usage

Run the script:

```bash
python3 days_since_ath.py
```

The script will:
1. Load price data from `../price.csv`
2. Calculate days since ATH for each date
3. Generate a chart saved as `days_since_ath.png`

## How It Works

1. **Data Loading**: Reads Bitcoin price data from `price.csv` (must be in the parent directory)
2. **ATH Detection**: Identifies new all-time highs by tracking when the running maximum price increases
3. **Days Calculation**: For each date, calculates how many days have passed since the last ATH
4. **Visualization**: Creates a chart with:
   - Orange line showing days since ATH over time
   - Vertical dashed lines at each ATH event
   - Labels for significant peaks (>50 days)

## Output

The script generates `days_since_ath.png` in the same directory, showing the complete history of days since ATH with all major cycles labeled.

