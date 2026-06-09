# Bitcoin Node Count Chart

This script generates a horizontal bar chart showing Bitcoin node counts by software type and version, similar to the visualization from luke.dashjr.org.

## Features

- Displays node counts grouped by software (Bitcoin Core, Bitcoin Knots, Other)
- Shows version breakdowns within each software type
- Color-coded segments (orange for Core, green for Knots)
- Displays total node count, date/time, and estimated block height
- Dark theme matching other Bitcoin charts in this repository

## Setup

Install the required dependencies:

```bash
pip3 install -r requirements.txt
```

## Usage

Run the script:

```bash
python3 node_count.py
```

The chart will be saved as `node_count.png` in the same directory.

## Data Sources

- Node software counts: `../data/bitcoin_csv_data/node_software_counts_grouped.csv`
- Node history: `../data/bitcoin_csv_data/bitcoin_node_history.csv`
- Original source: https://luke.dashjr.org/programs/bitcoin/files/charts/software.html

## Output

The chart displays:
- Total node count (includes listening and estimated non-listening nodes)
- Date and time of the data snapshot
- Estimated block height
- Segmented horizontal bar showing:
  - Bitcoin Core versions (v30, v29, v28, etc.) in orange shades
  - Bitcoin Knots versions in green shades
  - Other software types in gray
- Each segment shows version, count, and percentage

