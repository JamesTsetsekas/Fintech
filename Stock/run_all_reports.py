#!/usr/bin/env python3
"""
Master script to run all Stock visualization reports.

This script executes all chart generation scripts in the correct order
and handles errors gracefully, continuing with other reports if one fails.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Get the script directory (Stock folder)
script_dir = Path(__file__).parent

def generate_output_filename(report_info):
    """Generate a unique output filename based on report configuration."""
    args = report_info.get('args', [])
    
    # Determine base filename from default output
    default_output = report_info.get('default_output', report_info.get('output', 'output.png'))
    
    # For wildcard outputs (technical indicators), return as-is
    if '*' in default_output:
        return default_output
    
    # Check if script generates unique filenames (like Individual Stock Analysis with ticker)
    # In this case, the script generates {TICKER}_stock_analysis.png, which is already unique
    has_ticker_arg = '--ticker' in args
    if has_ticker_arg and 'stock_analysis.png' in default_output:
        # Script already generates unique filename based on ticker, return as-is
        return default_output
    
    # Extract base name without extension
    base_name = Path(default_output).stem
    ext = Path(default_output).suffix
    
    # Build suffix from args
    suffix_parts = []
    
    # Parse args to build unique identifier
    i = 0
    while i < len(args):
        if args[i] == '--source' and i + 1 < len(args):
            source = args[i + 1]
            if source in ['sp500', 'nasdaq', 'dow', 'sector']:
                suffix_parts.append(source)
            i += 2
        elif args[i] == '--sector' and i + 1 < len(args):
            sector = args[i + 1].lower().replace(' ', '_')
            suffix_parts.append(sector)
            i += 2
        elif args[i] == '--top' and i + 1 < len(args):
            suffix_parts.append(f'top{args[i + 1]}')
            i += 2
        else:
            i += 1
    
    # If no args, it's the default
    if not suffix_parts:
        suffix_parts.append('default')
    
    # Combine base name with suffix
    suffix = '_'.join(suffix_parts)
    return f"{base_name}_{suffix}{ext}"

# Define all reports to run (in order)
# Each report includes command-line arguments to generate example outputs
REPORTS = [
    {
        'name': 'Stock Correlation Analysis (Default List)',
        'path': script_dir / 'StockCorrelation' / 'stock_correlation_analysis.py',
        'args': [],  # Uses default asset list
        'output': 'correlation_clusters.png',
        'default_output': 'correlation_clusters.png'
    },
    {
        'name': 'Stock Correlation Analysis (Top 20 S&P 500)',
        'path': script_dir / 'StockCorrelation' / 'stock_correlation_analysis.py',
        'args': ['--source', 'sp500', '--top', '20'],
        'output': 'correlation_clusters.png',
        'default_output': 'correlation_clusters.png'
    },
    {
        'name': 'Stock Correlation Analysis (Top 15 NASDAQ-100)',
        'path': script_dir / 'StockCorrelation' / 'stock_correlation_analysis.py',
        'args': ['--source', 'nasdaq', '--top', '15'],
        'output': 'correlation_clusters.png',
        'default_output': 'correlation_clusters.png'
    },
    {
        'name': 'Stock Correlation Analysis (Dow Jones)',
        'path': script_dir / 'StockCorrelation' / 'stock_correlation_analysis.py',
        'args': ['--source', 'dow'],
        'output': 'correlation_clusters.png',
        'default_output': 'correlation_clusters.png'
    },
    {
        'name': 'Stock Performance Comparison (Default List)',
        'path': script_dir / 'StockPerformanceComparison' / 'stock_performance_comparison.py',
        'args': [],  # Uses default asset list
        'output': 'stock_performance_comparison.png',
        'default_output': 'stock_performance_comparison.png'
    },
    {
        'name': 'Stock Performance Comparison (Top 10 S&P 500)',
        'path': script_dir / 'StockPerformanceComparison' / 'stock_performance_comparison.py',
        'args': ['--source', 'sp500', '--top', '10', '--period', '1y'],
        'output': 'stock_performance_comparison.png',
        'default_output': 'stock_performance_comparison.png'
    },
    {
        'name': 'Stock Performance Comparison (Top 15 NASDAQ-100)',
        'path': script_dir / 'StockPerformanceComparison' / 'stock_performance_comparison.py',
        'args': ['--source', 'nasdaq', '--top', '15', '--period', '1y'],
        'output': 'stock_performance_comparison.png',
        'default_output': 'stock_performance_comparison.png'
    },
    {
        'name': 'Stock Performance Comparison (Dow Jones)',
        'path': script_dir / 'StockPerformanceComparison' / 'stock_performance_comparison.py',
        'args': ['--source', 'dow', '--period', '1y'],
        'output': 'stock_performance_comparison.png',
        'default_output': 'stock_performance_comparison.png'
    },
    {
        'name': 'Stock Volatility Analysis (Default List)',
        'path': script_dir / 'StockVolatilityAnalysis' / 'stock_volatility_analysis.py',
        'args': [],  # Uses default asset list
        'output': 'stock_volatility_analysis.png',
        'default_output': 'stock_volatility_analysis.png'
    },
    {
        'name': 'Stock Volatility Analysis (Top 10 S&P 500)',
        'path': script_dir / 'StockVolatilityAnalysis' / 'stock_volatility_analysis.py',
        'args': ['--source', 'sp500', '--top', '10', '--period', '1y'],
        'output': 'stock_volatility_analysis.png',
        'default_output': 'stock_volatility_analysis.png'
    },
    {
        'name': 'Stock Volatility Analysis (Top 10 NASDAQ-100)',
        'path': script_dir / 'StockVolatilityAnalysis' / 'stock_volatility_analysis.py',
        'args': ['--source', 'nasdaq', '--top', '10', '--period', '1y'],
        'output': 'stock_volatility_analysis.png',
        'default_output': 'stock_volatility_analysis.png'
    },
    {
        'name': 'Stock Volatility Analysis (Dow Jones)',
        'path': script_dir / 'StockVolatilityAnalysis' / 'stock_volatility_analysis.py',
        'args': ['--source', 'dow', '--period', '1y'],
        'output': 'stock_volatility_analysis.png',
        'default_output': 'stock_volatility_analysis.png'
    },
    {
        'name': 'Stock Volatility Analysis (Technology Sector)',
        'path': script_dir / 'StockVolatilityAnalysis' / 'stock_volatility_analysis.py',
        'args': ['--source', 'sector', '--sector', 'Technology', '--top', '8', '--period', '1y'],
        'output': 'stock_volatility_analysis.png',
        'default_output': 'stock_volatility_analysis.png'
    },
    {
        'name': 'Stock Technical Indicators (Default List)',
        'path': script_dir / 'StockTechnicalIndicators' / 'stock_technical_indicators.py',
        'args': [],  # Uses default asset list
        'output': '*_technical_indicators.png',  # Multiple files (one per ticker)
        'default_output': '*_technical_indicators.png'
    },
    {
        'name': 'Stock Technical Indicators (Top 5 S&P 500)',
        'path': script_dir / 'StockTechnicalIndicators' / 'stock_technical_indicators.py',
        'args': ['--source', 'sp500', '--top', '5', '--period', '1y'],
        'output': '*_technical_indicators.png',
        'default_output': '*_technical_indicators.png'
    },
    {
        'name': 'Stock Technical Indicators (Top 5 NASDAQ-100)',
        'path': script_dir / 'StockTechnicalIndicators' / 'stock_technical_indicators.py',
        'args': ['--source', 'nasdaq', '--top', '5', '--period', '1y'],
        'output': '*_technical_indicators.png',
        'default_output': '*_technical_indicators.png'
    },
    {
        'name': 'Stock Technical Indicators (Dow Jones)',
        'path': script_dir / 'StockTechnicalIndicators' / 'stock_technical_indicators.py',
        'args': ['--source', 'dow', '--period', '1y'],
        'output': '*_technical_indicators.png',
        'default_output': '*_technical_indicators.png'
    },
    {
        'name': 'Individual Stock Analysis (MSTR)',
        'path': script_dir / 'IndividualStockAnalysis' / 'individual_stock_analysis.py',
        'args': ['--ticker', 'MSTR', '--period', '1y'],
        'output': 'MSTR_stock_analysis.png',
        'default_output': 'MSTR_stock_analysis.png'
    },
    {
        'name': 'Individual Stock Analysis (AAPL)',
        'path': script_dir / 'IndividualStockAnalysis' / 'individual_stock_analysis.py',
        'args': ['--ticker', 'AAPL', '--period', '1y'],
        'output': 'AAPL_stock_analysis.png',
        'default_output': 'AAPL_stock_analysis.png'
    },
    {
        'name': 'Individual Stock Analysis (NVDA)',
        'path': script_dir / 'IndividualStockAnalysis' / 'individual_stock_analysis.py',
        'args': ['--ticker', 'NVDA', '--period', '1y'],
        'output': 'NVDA_stock_analysis.png',
        'default_output': 'NVDA_stock_analysis.png'
    },
    {
        'name': 'Stock Sector Performance',
        'path': script_dir / 'Sector' / 'StockSectorPerformance' / 'stock_sector_performance.py',
        'args': ['--period', '1y'],
        'output': 'stock_sector_performance.png',
        'default_output': 'stock_sector_performance.png'
    },
    {
        'name': 'Jellybean Chart - Sector Returns',
        'path': script_dir / 'Sector' / 'JellybeanChart' / 'jellybean_chart.py',
        'args': ['--period', '10y'],
        'output': 'jellybean_chart.png',
        'default_output': 'jellybean_chart.png'
    },
]

# Generate unique output filenames for all reports
for report in REPORTS:
    # Store the original output as default_output if not already set
    if 'default_output' not in report:
        report['default_output'] = report.get('output', 'output.png')
    # Generate unique filename based on args and store it in output
    report['output'] = generate_output_filename(report)

def run_report(report_info):
    """Run a single report script and return success status."""
    name = report_info['name']
    script_path = report_info['path']
    args = report_info.get('args', [])  # Get command-line arguments if provided
    default_output = report_info.get('default_output', report_info.get('output', 'output.png'))
    unique_output = report_info.get('output', default_output)
    
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"Script: {script_path}")
    if args:
        print(f"Arguments: {' '.join(args)}")
    print(f"Output: {unique_output}")
    print(f"{'='*60}")
    
    # Check if script exists
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        return False
    
    try:
        # Build command with arguments
        cmd = [sys.executable, str(script_path)] + args
        
        # Run the script
        result = subprocess.run(
            cmd,
            cwd=script_path.parent,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per script (stock data can take longer)
        )
        
        if result.returncode == 0:
            # Rename output file if it exists and has a default name
            if '*' not in default_output and default_output != unique_output:
                default_file = script_path.parent / default_output
                unique_file = script_path.parent / unique_output
                
                if default_file.exists():
                    # If unique file already exists, remove it first
                    if unique_file.exists():
                        unique_file.unlink()
                    default_file.rename(unique_file)
                    print(f"  Renamed output: {default_output} -> {unique_output}")
            
            print(f"[OK] Successfully completed: {name}")
            if result.stdout:
                # Print last few lines of output for context
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:
                    if line.strip():
                        print(f"  {line}")
            return True
        else:
            print(f"[FAILED] Failed: {name}")
            if result.stderr:
                print(f"Error output:")
                for line in result.stderr.strip().split('\n')[-10:]:
                    if line.strip():
                        print(f"  {line}")
            if result.stdout:
                print(f"Standard output:")
                for line in result.stdout.strip().split('\n')[-10:]:
                    if line.strip():
                        print(f"  {line}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[FAILED] Timeout: {name} (exceeded 10 minutes)")
        return False
    except Exception as e:
        print(f"[FAILED] Exception running {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to run all reports."""
    start_time = datetime.now()
    
    print("\n" + "="*60)
    print("STOCK VISUALIZATION REPORTS RUNNER")
    print("="*60)
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total reports: {len(REPORTS)}")
    print("="*60)
    print("\nNote: Some reports may take several minutes due to API rate limits.")
    print("The script will continue even if individual reports fail.\n")
    
    # Track results
    results = {
        'success': [],
        'failed': []
    }
    
    # Run each report
    for report in REPORTS:
        success = run_report(report)
        if success:
            results['success'].append(report['name'])
        else:
            results['failed'].append(report['name'])
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total reports: {len(REPORTS)}")
    print(f"Successful: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Duration: {duration}")
    print("="*60)
    
    if results['success']:
        print("\nSuccessful reports:")
        for name in results['success']:
            print(f"  [OK] {name}")
    
    if results['failed']:
        print("\nFailed reports:")
        for name in results['failed']:
            print(f"  [FAILED] {name}")
        sys.exit(1)
    
    print("\nAll reports completed successfully!")
    sys.exit(0)

if __name__ == '__main__':
    main()

