#!/usr/bin/env python3
"""
Master script to run all Bitcoin visualization reports.

This script executes all chart generation scripts in the correct order
and handles errors gracefully, continuing with other reports if one fails.

Before running reports, it updates the data files from the GitHub repository.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Get the script directory (Bitcoin folder)
script_dir = Path(__file__).parent

# Define all reports to run (in order)
REPORTS = [
    {
        'name': '200 DMA & 200 WMA',
        'path': script_dir / '200_dma_200_wma' / '200_dma_200_wma.py',
        'output': '200_dma_200_wma.png'
    },
    {
        'name': 'Mayer Multiple',
        'path': script_dir / 'mayer_multiple' / 'mayer_multiple.py',
        'output': 'mayer_multiple.png'
    },
    {
        'name': 'Days at a Loss',
        'path': script_dir / 'days_at_a_loss' / 'days_at_a_loss.py',
        'output': 'days_at_a_loss.png'
    },
    {
        'name': 'Days Since ATH',
        'path': script_dir / 'days_since_ath' / 'days_since_ath.py',
        'output': 'days_since_ath.png'
    },
    {
        'name': 'Regime Mosaic',
        'path': script_dir / 'regime_mosaic' / 'regime_mosaic.py',
        'output': 'regime_mosaic.png'
    },
    {
        'name': 'Price Acceptance Heatmap',
        'path': script_dir / 'price_acceptance_heatmap' / 'price_acceptance_heatmap.py',
        'output': 'price_acceptance_heatmap.png'
    },
    {
        'name': 'Bollinger Bands',
        'path': script_dir / 'bollinger-bands' / 'bollinger_bands.py',
        'output': 'bollinger_bands.png'
    },
    {
        'name': 'Volatility Regimes',
        'path': script_dir / 'volatility_regimes' / 'volatility_regimes.py',
        'output': 'volatility_regimes.png'
    },
    {
        'name': 'Intraday Volatility Heatmap',
        'path': script_dir / 'intraday_volatility_heatmap' / 'intraday_volatility_heatmap.py',
        'output': 'intraday_volatility_heatmap.png'
    },
    {
        'name': 'Distance From 200DMA Heatmap',
        'path': script_dir / 'distance_from_200dma_heatmap' / 'distance_from_200dma_heatmap.py',
        'output': 'distance_from_200dma_heatmap.png'
    },
    {
        'name': 'Monthly & Yearly Returns',
        'path': script_dir / 'monthly_yearly_returns' / 'monthly_yearly_returns.py',
        'output': 'monthly_yearly_returns.png'
    },
    {
        'name': 'Quarterly & Yearly Returns',
        'path': script_dir / 'quarterly_yearly_returns' / 'quarterly_yearly_returns.py',
        'output': 'quarterly_yearly_returns.png'
    },
    {
        'name': 'Yearly Windows',
        'path': script_dir / 'yearly_windows' / 'yearly_windows.py',
        'output': 'yearly_windows.png'
    },
    {
        'name': 'CAGR',
        'path': script_dir / 'cagr' / 'cagr.py',
        'output': 'cagr.png'
    },
    {
        'name': 'Risk-Adjusted Returns',
        'path': script_dir / 'risk_adjusted_returns' / 'risk_adjusted_returns.py',
        'output': 'risk_adjusted_returns.png'
    },
    {
        'name': 'Return-Volatility Map',
        'path': script_dir / 'return_volatility_map' / 'return_volatility_map.py',
        'output': 'return_volatility_map.png'
    },
    {
        'name': 'Seasonality Heatmap',
        'path': script_dir / 'seasonality_heatmap' / 'seasonality_heatmap.py',
        'output': 'seasonality_heatmap.png'
    },
    {
        'name': 'Pi Cycle Top',
        'path': script_dir / 'pi-cycle-top' / 'pi_cycle_top.py',
        'output': 'pi_cycle_top.png'
    },
    {
        'name': 'Pi Cycle Top Estimate',
        'path': script_dir / 'pi-cycle-top-estimate' / 'pi_cycle_top_estimate.py',
        'output': 'pi_cycle_top_estimate.png'
    },
    {
        'name': 'Power Law',
        'path': script_dir / 'power-law' / 'power_law.py',
        'output': 'power_law.png'
    },
    {
        'name': 'Power Law 2',
        'path': script_dir / 'power-law' / 'power_law2.py',
        'output': 'power_law2.png'
    },
    {
        'name': 'Power Law 3',
        'path': script_dir / 'power-law' / 'power_law3.py',
        'output': 'power_law3.png'
    },
    {
        'name': 'Power Law Oscillator',
        'path': script_dir / 'power-law-oscillator' / 'power_law_oscillator.py',
        'output': 'power_law_oscillator.png'
    },
    {
        'name': 'Unit of Account (BTC/USD)',
        'path': script_dir / 'uoa_btc_usd' / 'uoa_btc_usd.py',
        'output': 'uoa_btc_usd.png'
    },
    {
        'name': 'Rainbow Chart',
        'path': script_dir / 'rainbow' / 'rainbow_chart.py',
        'output': 'rainbow_chart.png'
    },
    {
        'name': 'Never Look Back Price',
        'path': script_dir / 'never_look_back_price' / 'never_look_back_price.py',
        'output': 'never_look_back_price.png'
    },
    {
        'name': 'Epoch Candles',
        'path': script_dir / 'epoch_candles' / 'epoch_candles.py',
        'output': 'epoch_candles.png'
    },
    {
        'name': 'Monthly Candles',
        'path': script_dir / 'monthly_candles' / 'monthly_candles.py',
        'output': 'monthly_candles.png'
    },
    {
        'name': 'Yearly Candles',
        'path': script_dir / 'yearly_candles' / 'yearly_candles.py',
        'output': 'yearly_candles.png'
    },
    {
        'name': 'DCA Cost Basis',
        'path': script_dir / 'dca_cost_basis' / 'dca_cost_basis.py',
        'output': 'dca_cost_basis.png'
    },
    {
        'name': 'Node Count',
        'path': script_dir / 'node_count' / 'node_count.py',
        'output': 'node_count.png'
    },
    {
        'name': 'HODL Waves Price',
        'path': script_dir / 'hodl_waves_price' / 'hodl_waves_price.py',
        'output': 'hodl_waves_price.png'
    },
    {
        'name': 'Price Distribution',
        'path': script_dir / 'price_distribution' / 'price_distribution.py',
        'output': 'price_distribution.png'
    },
    {
        'name': 'Epoch-Over-Epoch (EOE) Growth',
        'path': script_dir / 'eoe_growth' / 'eoe_growth.py',
        'output': 'eoe_growth.png'
    },
    {
        'name': 'Halving Cycles',
        'path': script_dir / 'halving_cycles' / 'halving_cycles.py',
        'output': 'halving_cycles.png'
    },
    {
        'name': 'Halving Phase Compass',
        'path': script_dir / 'halving_phase_compass' / 'halving_phase_compass.py',
        'output': 'halving_phase_compass.png'
    },
    {
        'name': 'Halving Era ROI Heatmap',
        'path': script_dir / 'halving_era_roi_heatmap' / 'halving_era_roi_heatmap.py',
        'output': 'halving_era_roi_heatmap.png'
    },
    {
        'name': 'Cycle High Drawdown',
        'path': script_dir / 'cycle_high_drawdown' / 'cycle_high_drawdown.py',
        'output': 'cycle_high_drawdown.png'
    },
    {
        'name': 'Drawdown Recovery Map',
        'path': script_dir / 'drawdown_recovery_map' / 'drawdown_recovery_map.py',
        'output': 'drawdown_recovery_map.png'
    },
    {
        'name': 'Drawdown Duration Heatmap',
        'path': script_dir / 'drawdown_duration_heatmap' / 'drawdown_duration_heatmap.py',
        'output': 'drawdown_duration_heatmap.png'
    },
    {
        'name': 'Price Prediction Models',
        'path': script_dir / 'model_price_prediction' / 'model_price_prediction.py',
        'output': 'model_price_prediction.png'
    },
    {
        'name': 'Cycle Phase Dashboard',
        'path': script_dir / 'cycle_phase_dashboard' / 'cycle_phase_dashboard.py',
        'output': 'cycle_phase_dashboard.png'
    },
    {
        'name': 'Price Prediction (ML)',
        'path': script_dir / 'price_prediction' / 'price_prediction.py',
        'output': 'price_prediction.png'
    },
    {
        'name': 'Puell Multiple',
        'path': script_dir / 'puell_multiple' / 'puell_multiple.py',
        'output': 'puell_multiple.png'
    },
    {
        'name': 'Fee Pressure',
        'path': script_dir / 'fee_pressure' / 'fee_pressure.py',
        'output': 'fee_pressure.png'
    },
    {
        'name': 'Fee Pressure Heatmap',
        'path': script_dir / 'fee_pressure_heatmap' / 'fee_pressure_heatmap.py',
        'output': 'fee_pressure_heatmap.png'
    },
    {
        'name': 'Miner Hashprice',
        'path': script_dir / 'miner_hashprice' / 'miner_hashprice.py',
        'output': 'miner_hashprice.png'
    },
]

def parse_args():
    """Parse runner options."""
    parser = argparse.ArgumentParser(description="Run Bitcoin chart reports.")
    parser.add_argument(
        '--skip-update',
        action='store_true',
        help='Skip the data update step before running reports.',
    )
    parser.add_argument(
        '--only',
        action='append',
        default=[],
        metavar='TEXT',
        help='Run only reports whose name, script path, or output filename contains TEXT. Can be used multiple times.',
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available reports and exit.',
    )
    return parser.parse_args()

def filter_reports(reports, filters):
    """Return reports matching any requested filter."""
    if not filters:
        return reports

    lowered_filters = [value.lower() for value in filters]
    selected = []
    for report in reports:
        haystack = " ".join(
            [
                report['name'],
                str(report['path'].relative_to(script_dir)),
                report['output'],
            ]
        ).lower()
        if any(value in haystack for value in lowered_filters):
            selected.append(report)
    return selected

def update_data():
    """Update Bitcoin data files before running reports."""
    update_script = script_dir / 'data' / 'update.py'
    
    if not update_script.exists():
        print(f"WARNING: Update script not found: {update_script}")
        print("Continuing with existing data files...")
        return False
    
    print("\n" + "="*60)
    print("UPDATING BITCOIN DATA FILES")
    print("="*60)
    print(f"Running: {update_script}")
    print("="*60)
    
    try:
        # Run the update script to download/update all files
        # This ensures we always have the latest data for all reports
        result = subprocess.run(
            [sys.executable, str(update_script)],
            cwd=update_script.parent,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout for all downloads (block data files are large)
        )
        
        if result.returncode == 0:
            print("[OK] Data update completed successfully")
            if result.stdout:
                # Print last few lines of output
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:
                    if line.strip():
                        print(f"  {line}")
            return True
        else:
            print("⚠ Warning: Data update failed or had errors")
            print("Continuing with existing data files...")
            if result.stderr:
                print("Error output:")
                for line in result.stderr.strip().split('\n')[-5:]:
                    if line.strip():
                        print(f"  {line}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠ Warning: Data update timed out (exceeded 30 minutes)")
        print("Continuing with existing data files...")
        return False
    except Exception as e:
        print(f"⚠ Warning: Exception during data update: {e}")
        print("Continuing with existing data files...")
        return False

def run_report(report_info):
    """Run a single report script and return success status."""
    name = report_info['name']
    script_path = report_info['path']
    
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"Script: {script_path}")
    print(f"{'='*60}")
    
    # Check if script exists
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        return False
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=script_path.parent,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per script
        )
        
        if result.returncode == 0:
            print(f"[OK] Successfully completed: {name}")
            if result.stdout:
                # Print last few lines of output for context
                lines = result.stdout.strip().split('\n')
                for line in lines[-3:]:
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
        print(f"[FAILED] Timeout: {name} (exceeded 5 minutes)")
        return False
    except Exception as e:
        print(f"[FAILED] Exception running {name}: {e}")
        return False

def main():
    """Main function to run all reports."""
    args = parse_args()
    if args.list:
        print("Available Bitcoin reports:")
        for report in REPORTS:
            rel_path = report['path'].relative_to(script_dir)
            print(f"  {report['name']} ({rel_path})")
        sys.exit(0)

    selected_reports = filter_reports(REPORTS, args.only)
    if not selected_reports:
        print(f"ERROR: No reports matched --only filters: {', '.join(args.only)}")
        sys.exit(2)

    start_time = datetime.now()
    
    print("\n" + "="*60)
    print("BITCOIN VISUALIZATION REPORTS RUNNER")
    print("="*60)
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total reports: {len(selected_reports)}")
    if args.only:
        print(f"Filters: {', '.join(args.only)}")
    print("="*60)
    
    # Update data files first
    if args.skip_update:
        print("\nSkipping Bitcoin data update (--skip-update).")
    else:
        update_data()
    
    # Track results
    results = {
        'success': [],
        'failed': []
    }
    
    # Run each report
    for report in selected_reports:
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
    print(f"Total reports: {len(selected_reports)}")
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
