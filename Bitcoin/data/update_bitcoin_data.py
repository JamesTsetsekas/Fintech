#!/usr/bin/env python3
"""
Bitcoin Power Law Data Updater

This script automates the process of updating Bitcoin historical price data
for the power law charts. It can:
1. Convert CoinMarketCap CSV format to price.csv format
2. Optionally download latest data from CoinMarketCap
3. Update price.csv with the latest data

Usage:
    python update_bitcoin_data.py [--download] [--input-file INPUT_CSV] [--output-file OUTPUT_CSV]
"""

import pandas as pd
import argparse
import sys
from pathlib import Path
from datetime import datetime
import os

try:
    from cryptocmd import CmcScraper
    CRYPTO_CMD_AVAILABLE = True
except ImportError:
    CRYPTO_CMD_AVAILABLE = False
    print("Warning: cryptocmd not installed. Use --input-file to convert existing CSV files.")
    print("Install with: pip install cryptocmd")


def convert_coinmarketcap_to_law(input_file, output_file=None, allow_overwrite=False):
    """
    Convert CoinMarketCap CSV format to price.csv format.
    
    Args:
        input_file: Path to CoinMarketCap CSV file (semicolon-delimited)
        output_file: Path to output price.csv file (default: price.csv in same directory)
        allow_overwrite: If False, will warn before overwriting existing price.csv
    
    Returns:
        DataFrame with converted data
    """
    print(f"Reading CoinMarketCap CSV: {input_file}")
    
    # Read CoinMarketCap CSV (semicolon-delimited)
    # Use utf-8-sig encoding to handle UTF-8 BOM if present
    try:
        df = pd.read_csv(input_file, sep=';', quotechar='"', encoding='utf-8-sig')
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    print(f"Found {len(df)} rows in input file")
    
    # Convert date columns from ISO format to datetime
    # Start is the date from timeOpen
    df['Start'] = pd.to_datetime(df['timeOpen']).dt.normalize()  # Normalize to remove time component
    # End is Start + 1 day (matching price.csv format where End is the next day)
    df['End'] = df['Start'] + pd.Timedelta(days=1)
    
    # Map columns from CoinMarketCap format to price.csv format
    converted_df = pd.DataFrame({
        'Start': df['Start'],
        'End': df['End'],
        'Open': df['open'],
        'High': df['high'],
        'Low': df['low'],
        'Close': df['close'],
        'Volume': df['volume'],
        'Market Cap': df['marketCap']
    })
    
    # Sort by date (newest first, to match price.csv format)
    converted_df = converted_df.sort_values('Start', ascending=False)  # Newest first
    
    # Format dates as strings (YYYY-MM-DD)
    converted_df['Start'] = converted_df['Start'].dt.strftime('%Y-%m-%d')
    converted_df['End'] = converted_df['End'].dt.strftime('%Y-%m-%d')
    
    # Round numeric columns to reasonable precision
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'Market Cap']
    for col in numeric_cols:
        converted_df[col] = pd.to_numeric(converted_df[col], errors='coerce')
    
    # Remove any rows with missing critical data
    converted_df = converted_df.dropna(subset=['Start', 'Close'])
    
    print(f"Converted {len(converted_df)} rows")
    
    # Save to output file
    if output_file is None:
        output_file = Path(__file__).parent / 'price.csv'
    
    # Safety check: warn if overwriting existing price.csv without explicit permission
    output_path = Path(output_file)
    if output_path.exists() and output_path.name in ['law.csv', 'price.csv'] and not allow_overwrite:
        print(f"\n⚠️  WARNING: {output_file} already exists!")
        print("   This will OVERWRITE all existing data.")
        print("   Use --merge flag to merge with existing data instead.")
        response = input(f"   Continue and overwrite? (yes/no): ").strip().lower()
        if response != 'yes':
            print("   Aborted. Use --merge to preserve existing data.")
            sys.exit(0)
    
    print(f"Saving to: {output_file}")
    converted_df.to_csv(output_file, index=False)
    print(f"[OK] Successfully converted and saved to {output_file}")
    
    return converted_df


def download_bitcoin_data(output_file=None, start_date=None):
    """
    Download Bitcoin historical data from CoinMarketCap using cryptocmd.
    
    Args:
        output_file: Path to save the downloaded CSV (default: bitcoin_data_cmc.csv)
        start_date: Start date for data download (YYYY-MM-DD format, optional)
    
    Returns:
        DataFrame with downloaded data
    """
    if not CRYPTO_CMD_AVAILABLE:
        print("Error: cryptocmd library not installed.")
        print("Install with: pip install cryptocmd")
        sys.exit(1)
    
    print("Downloading Bitcoin historical data from CoinMarketCap...")
    
    try:
        # Initialize scraper for Bitcoin
        scraper = CmcScraper("BTC", start_date=start_date)
        
        # Get data as DataFrame
        df = scraper.get_dataframe()
        
        if df.empty:
            print("Error: No data downloaded")
            sys.exit(1)
        
        print(f"Downloaded {len(df)} rows")
        
        # Save raw data
        if output_file is None:
            output_file = Path.cwd() / 'bitcoin_data_cmc.csv'
        
        # Save in CoinMarketCap format (we'll need to convert it)
        # Note: cryptocmd returns data in a different format, so we need to adapt
        df.to_csv(output_file, index=False)
        print(f"[OK] Downloaded data saved to {output_file}")
        
        return df, output_file
    
    except Exception as e:
        print(f"Error downloading data: {e}")
        sys.exit(1)


def replace_year_data(new_data_df, existing_law_file='price.csv', output_file='price.csv', year=None):
    """
    Replace data for a specific year in existing price.csv file.
    
    Args:
        new_data_df: DataFrame with new data in price.csv format
        existing_law_file: Path to existing price.csv file
        output_file: Path to save updated data
        year: Year to replace (if None, will use the year from new_data_df)
    """
    existing_law_path = Path(existing_law_file)
    
    if not existing_law_path.exists():
        print(f"Error: {existing_law_file} not found")
        sys.exit(1)
    
    print(f"Reading existing price.csv: {existing_law_file}")
    existing_df = pd.read_csv(existing_law_path)
    existing_df['Start'] = pd.to_datetime(existing_df['Start'])
    existing_df['End'] = pd.to_datetime(existing_df['End'])
    new_data_df['Start'] = pd.to_datetime(new_data_df['Start'])
    new_data_df['End'] = pd.to_datetime(new_data_df['End'])
    
    # Determine year to replace
    if year is None:
        year = new_data_df['Start'].dt.year.iloc[0]
    
    print(f"Replacing data for year {year}")
    
    # Filter new data to only include the specified year
    new_data_df_filtered = new_data_df[new_data_df['Start'].dt.year == year]
    print(f"Filtered new data: {len(new_data_df_filtered)} rows for year {year} (out of {len(new_data_df)} total rows)")
    
    if len(new_data_df_filtered) == 0:
        print(f"Warning: No data found for year {year} in the new data file")
        sys.exit(1)
    
    # Remove existing data for the specified year
    existing_df_filtered = existing_df[existing_df['Start'].dt.year != year]
    print(f"Removed {len(existing_df) - len(existing_df_filtered)} rows from year {year}")
    
    # Add new data
    print(f"Adding {len(new_data_df_filtered)} new rows for year {year}")
    combined_df = pd.concat([existing_df_filtered, new_data_df_filtered], ignore_index=True)
    combined_df = combined_df.sort_values('Start', ascending=False)
    
    # Format dates as strings
    combined_df['Start'] = combined_df['Start'].dt.strftime('%Y-%m-%d')
    combined_df['End'] = combined_df['End'].dt.strftime('%Y-%m-%d')
    
    # Save updated data
    print(f"Saving updated data to: {output_file}")
    combined_df.to_csv(output_file, index=False)
    print(f"[OK] Successfully saved {len(combined_df)} total rows to {output_file}")


def merge_with_existing_law(new_data_df, existing_law_file='price.csv', output_file='price.csv'):
    """
    Merge new data with existing price.csv file, avoiding duplicates.
    
    Args:
        new_data_df: DataFrame with new data in price.csv format
        existing_law_file: Path to existing price.csv file
        output_file: Path to save merged data
    """
    existing_law_path = Path(existing_law_file)
    
    if existing_law_path.exists():
        print(f"Reading existing price.csv: {existing_law_file}")
        existing_df = pd.read_csv(existing_law_path)
        # Convert dates to datetime for comparison
        existing_df['Start'] = pd.to_datetime(existing_df['Start'])
        existing_df['End'] = pd.to_datetime(existing_df['End'])
        new_data_df['Start'] = pd.to_datetime(new_data_df['Start'])
        new_data_df['End'] = pd.to_datetime(new_data_df['End'])
        
        # Find the latest date in existing data
        latest_existing_date = existing_df['Start'].max()
        print(f"Latest date in existing data: {latest_existing_date.date()}")
        
        # Filter new data to only include dates after the latest existing date
        new_data_df_filtered = new_data_df[new_data_df['Start'] > latest_existing_date]
        
        if len(new_data_df_filtered) > 0:
            print(f"Adding {len(new_data_df_filtered)} new rows")
            # Combine and sort
            combined_df = pd.concat([existing_df, new_data_df_filtered], ignore_index=True)
            combined_df = combined_df.sort_values('Start', ascending=False)
        else:
            print("No new data to add (all dates already exist)")
            combined_df = existing_df
        
        # Format dates as strings
        combined_df['Start'] = combined_df['Start'].dt.strftime('%Y-%m-%d')
        combined_df['End'] = combined_df['End'].dt.strftime('%Y-%m-%d')
    else:
        print("No existing price.csv found, creating new file")
        # Ensure dates are datetime before formatting
        if not pd.api.types.is_datetime64_any_dtype(new_data_df['Start']):
            new_data_df['Start'] = pd.to_datetime(new_data_df['Start'])
        if not pd.api.types.is_datetime64_any_dtype(new_data_df['End']):
            new_data_df['End'] = pd.to_datetime(new_data_df['End'])
        combined_df = new_data_df
        combined_df['Start'] = combined_df['Start'].dt.strftime('%Y-%m-%d')
        combined_df['End'] = combined_df['End'].dt.strftime('%Y-%m-%d')
    
    # Save merged data
    print(f"Saving merged data to: {output_file}")
    combined_df.to_csv(output_file, index=False)
    print(f"[OK] Successfully saved {len(combined_df)} total rows to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Update Bitcoin Power Law data from CoinMarketCap',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert existing CoinMarketCap CSV to price.csv format
  python update_bitcoin_data.py --input-file Bitcoin_1_1_2008-1_2_2026_historical_data_coinmarketcap.csv
  
  # Download latest data and convert
  python update_bitcoin_data.py --download
  
  # Convert and merge with existing price.csv
  python update_bitcoin_data.py --input-file Bitcoin_1_1_2008-1_2_2026_historical_data_coinmarketcap.csv --merge
  
  # Replace data for a specific year (e.g., fix 2024 data)
  python update_bitcoin_data.py --input-file Bitcoin_1_1_2024-12_31_2024_historical_data_coinmarketcap.csv --replace-year 2024
        """
    )
    
    parser.add_argument(
        '--download',
        action='store_true',
        help='Download latest data from CoinMarketCap (requires cryptocmd)'
    )
    
    parser.add_argument(
        '--input-file',
        type=str,
        help='Path to CoinMarketCap CSV file to convert'
    )
    
    parser.add_argument(
        '--output-file',
        type=str,
        default='price.csv',
        help='Path to output price.csv file (default: price.csv)'
    )
    
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Merge new data with existing price.csv (avoids duplicates)'
    )
    
    parser.add_argument(
        '--replace-year',
        type=int,
        help='Replace data for a specific year (e.g., --replace-year 2024)'
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for download (YYYY-MM-DD format, only used with --download)'
    )
    
    args = parser.parse_args()
    
    # Determine script directory and resolve output file path
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    # Resolve relative paths relative to script directory
    if args.output_file and not Path(args.output_file).is_absolute():
        args.output_file = str(Path(script_dir / args.output_file).resolve())
    
    if args.download:
        # Download new data
        if not CRYPTO_CMD_AVAILABLE:
            print("Error: cryptocmd not installed. Install with: pip install cryptocmd")
            sys.exit(1)
        
        downloaded_file = script_dir / 'bitcoin_data_cmc_temp.csv'
        df, _ = download_bitcoin_data(downloaded_file, args.start_date)
        
        # Note: cryptocmd format might be different, so we may need to adapt
        # For now, let's try to convert it
        print("\nNote: cryptocmd format may differ from manual download.")
        print("If conversion fails, please download CSV manually from CoinMarketCap.")
        
        # Try to convert the downloaded file
        try:
            converted_df = convert_coinmarketcap_to_law(downloaded_file, args.output_file)
            if args.merge:
                merge_with_existing_law(converted_df, args.output_file, args.output_file)
        except Exception as e:
            print(f"Error converting downloaded file: {e}")
            print("Please check the format and adjust the conversion function if needed.")
            sys.exit(1)
        
        # Clean up temp file
        if downloaded_file.exists():
            downloaded_file.unlink()
    
    elif args.input_file:
        # Convert existing file
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}")
            sys.exit(1)
        
        # If replacing a year, convert to temp file first, then replace
        if args.replace_year:
            temp_output = Path(args.output_file).parent / 'price_temp.csv'
            converted_df = convert_coinmarketcap_to_law(input_path, temp_output, allow_overwrite=True)
            replace_year_data(converted_df, args.output_file, args.output_file, year=args.replace_year)
            # Clean up temp file
            if temp_output.exists():
                temp_output.unlink()
        # If merging, convert to temp file first, then merge
        elif args.merge:
            temp_output = Path(args.output_file).parent / 'price_temp.csv'
            converted_df = convert_coinmarketcap_to_law(input_path, temp_output, allow_overwrite=True)
            merge_with_existing_law(converted_df, args.output_file, args.output_file)
            # Clean up temp file
            if temp_output.exists():
                temp_output.unlink()
        else:
            converted_df = convert_coinmarketcap_to_law(input_path, args.output_file, allow_overwrite=False)
    
    else:
        parser.print_help()
        print("\nError: Either --download or --input-file must be specified")
        sys.exit(1)
    
    print("\n[OK] Update complete!")


if __name__ == '__main__':
    main()

