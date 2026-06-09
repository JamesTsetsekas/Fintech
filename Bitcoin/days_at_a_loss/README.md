# Number of Days Spent at a Loss Chart

This script creates a visualization showing the number of days that purchases made at each price point have spent at a loss.

## Features

- **Gradient line chart** (green to yellow to red) showing days at a loss over time
- **Heatmap/bar chart** below the line chart with color-coded bars
- **Header information** showing:
  - Current date and block height
  - Price (Daily High)
  - Network Age
  - ATH purchase information

## Requirements

Install the required packages:

```bash
pip install pandas matplotlib numpy
```

Or use the requirements file from the parent directory.

## Usage

Run the script:

```bash
python3 days_at_a_loss.py
```

The script will:
1. Load price data from `../price.csv`
2. Calculate days at a loss for each date (this may take a few minutes for large datasets)
3. Generate a chart saved as `days_at_a_loss.png`
4. Display the chart

## How It Works

1. **Data Loading**: Reads Bitcoin price data from `price.csv` (must be in the parent directory)
2. **Days Calculation**: For each date in the dataset:
   - Takes the closing price as the "purchase price"
   - Counts how many days since then the price has been below that purchase price
   - This gives the "days at a loss" metric for purchases made on that date
3. **Visualization**: Creates a chart with:
   - Line graph with gradient colors (green = low days at loss, red = high days at loss)
   - Heatmap/bar chart below showing the same data
   - Header with current statistics

## Output

The script generates `days_at_a_loss.png` in the same directory, showing the complete history of days at a loss with gradient coloring to indicate severity.

## Performance Note

The calculation is O(n²) complexity, so for large datasets (5000+ rows), it may take several minutes to complete. Progress indicators are shown during calculation.

