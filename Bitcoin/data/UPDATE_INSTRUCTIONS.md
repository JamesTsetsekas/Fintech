# How to Update Bitcoin Price Data

## Quick Start (Recommended)

```bash
python update_bitcoin_data.py --input-file Bitcoin_1_1_2008-1_2_2026_historical_data_coinmarketcap.csv --merge
```

This will:
- ✅ Convert CoinMarketCap CSV to price.csv format
- ✅ Merge with existing data (preserves all historical data)
- ✅ Only add new dates that don't already exist
- ✅ Fix End date format (End = Start + 1 day)
- ✅ Update the shared price.csv file in the Bitcoin folder

## What Was Fixed

1. **End Date Format**: Now correctly sets End = Start + 1 day (matching original format)
2. **Safety Check**: Warns before overwriting existing price.csv
3. **Merge Functionality**: Use `--merge` to preserve all existing data
4. **Shared Data File**: All scripts now use the shared `Bitcoin/price.csv` file

## Step-by-Step Process

1. **Download latest data from CoinMarketCap**:
   - Go to https://coinmarketcap.com/currencies/bitcoin/historical-data/
   - Set date range (e.g., 2008-01-01 to today)
   - Download as CSV

2. **Run the update script with --merge**:
   ```bash
   cd Bitcoin
   python update_bitcoin_data.py --input-file [your_downloaded_file].csv --merge
   ```

3. **Verify the update**:
   ```bash
   # Check the latest date in price.csv
   head -2 price.csv
   
   # Run your scripts (from their respective directories)
   cd PowerLaw/bitcoin-power-law
   python power_law.py
   
   # Or generate monthly/yearly returns
   cd ../../monthly_yearly_returns
   python monthly_yearly_returns.py
   ```

## Important Notes

- ⚠️ **Always use --merge** to preserve existing data
- The script will automatically:
  - Convert date format (ISO → YYYY-MM-DD)
  - Set End = Start + 1 day
  - Sort by date (newest first)
  - Only add dates that don't already exist
  - Update the shared `Bitcoin/price.csv` file

## File Structure

- `Bitcoin/price.csv` - Shared Bitcoin price data file
- `Bitcoin/update_bitcoin_data.py` - Script to update price data
- `Bitcoin/UPDATE_INSTRUCTIONS.md` - This file
- `Bitcoin/PowerLaw/bitcoin-power-law/power_law.py` - Power law visualization scripts
- `Bitcoin/monthly_yearly_returns/monthly_yearly_returns.py` - Monthly/yearly returns visualization

## Troubleshooting

If you accidentally overwrote price.csv:
```bash
# Restore from git
git restore Bitcoin/price.csv

# Then run with --merge
cd Bitcoin
python update_bitcoin_data.py --input-file [file].csv --merge
```

