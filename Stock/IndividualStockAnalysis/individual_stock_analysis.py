#!/usr/bin/env python3
"""
Individual Stock Analysis Tool

Comprehensive analysis of a single stock including:
- Stock overview and key metrics
- Options data (chain, volume, open interest)
- Volume analysis
- Price action and technical indicators
- Financial metrics
- Analyst information
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import argparse
import logging
import time

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description='Individual Stock Analysis Tool',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python individual_stock_analysis.py --ticker MSTR
  python individual_stock_analysis.py --ticker AAPL --period 2y
  python individual_stock_analysis.py --ticker TSLA --options-days 30
    """
)
parser.add_argument(
    '--ticker',
    default='MSTR',
    help='Stock ticker symbol to analyze (default: MSTR)'
)
parser.add_argument(
    '--period',
    default='1y',
    help='Time period for historical analysis (e.g., 6m, 1y, 2y, 5y)'
)
parser.add_argument(
    '--options-days',
    type=int,
    default=30,
    help='Number of days out for options analysis (default: 30)'
)
args = parser.parse_args()

TICKER = args.ticker.upper()
PERIOD = args.period
OPTIONS_DAYS = args.options_days

print("="*70)
print(f"INDIVIDUAL STOCK ANALYSIS: {TICKER}")
print("="*70)
print(f"Period: {PERIOD}")
print(f"Options analysis: {OPTIONS_DAYS} days out")
print("="*70 + "\n")

# Calculate start date
if PERIOD.endswith('y'):
    years = int(PERIOD[:-1])
    start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
elif PERIOD.endswith('m'):
    months = int(PERIOD[:-1])
    start_date = (datetime.now() - timedelta(days=months*30)).strftime('%Y-%m-%d')
else:
    start_date = PERIOD

end_date = datetime.now().strftime('%Y-%m-%d')

# Fetch stock data
print("Fetching stock data...")
ticker_obj = yf.Ticker(TICKER)

# Get stock info
print("  Fetching company information...")
try:
    info = ticker_obj.info
    company_name = info.get('longName', TICKER)
    sector = info.get('sector', 'N/A')
    industry = info.get('industry', 'N/A')
    market_cap = info.get('marketCap', 0)
    employees = info.get('fullTimeEmployees', 'N/A')
    website = info.get('website', 'N/A')
    print(f"  [OK] Company: {company_name}")
except Exception as e:
    print(f"  [FAILED] Error fetching info: {e}")
    info = {}
    company_name = TICKER
    sector = 'N/A'
    industry = 'N/A'
    market_cap = 0

# Get historical data
print("  Fetching historical price data...")
try:
    hist = ticker_obj.history(start=start_date, end=end_date)
    if hist.empty:
        raise ValueError("No historical data available")
    print(f"  [OK] Retrieved {len(hist)} days of data")
except Exception as e:
    print(f"  [FAILED] Error: {e}")
    raise

# Get options data
print("  Fetching options data...")
options_data = {}
try:
    expirations = ticker_obj.options
    if expirations:
        # Get nearest expiration within OPTIONS_DAYS
        target_date = datetime.now() + timedelta(days=OPTIONS_DAYS)
        nearest_exp = None
        for exp in expirations:
            exp_date = datetime.strptime(exp, '%Y-%m-%d')
            if exp_date <= target_date:
                if nearest_exp is None or exp_date > datetime.strptime(nearest_exp, '%Y-%m-%d'):
                    nearest_exp = exp
            elif not nearest_exp:
                nearest_exp = exp
                break
        
        if nearest_exp:
            opt_chain = ticker_obj.option_chain(nearest_exp)
            options_data['expiration'] = nearest_exp
            options_data['calls'] = opt_chain.calls
            options_data['puts'] = opt_chain.puts
            print(f"  [OK] Options data for expiration: {nearest_exp}")
    else:
        print("  ⚠ No options data available")
except Exception as e:
    print(f"  ⚠ Options data unavailable: {e}")

# Technical indicator functions
def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return sma, upper_band, lower_band

# Calculate indicators
prices = hist['Adj Close'] if 'Adj Close' in hist.columns else hist['Close']
volume = hist['Volume'] if 'Volume' in hist.columns else None

rsi = calculate_rsi(prices)
macd, signal, histogram = calculate_macd(prices)
sma_20, upper_bb, lower_bb = calculate_bollinger_bands(prices)
sma_50 = prices.rolling(window=50).mean()
sma_200 = prices.rolling(window=200).mean()

# Current metrics
current_price = prices.iloc[-1]
current_volume = volume.iloc[-1] if volume is not None else None
avg_volume = volume.mean() if volume is not None else None

# Calculate returns
returns = prices.pct_change().dropna()
total_return = ((prices.iloc[-1] / prices.iloc[0]) - 1) * 100
days = (hist.index[-1] - hist.index[0]).days
years = days / 365.25 if days > 0 else 1
annualized_return = ((prices.iloc[-1] / prices.iloc[0]) ** (1/years) - 1) * 100 if years > 0 else 0
volatility = returns.std() * np.sqrt(252) * 100

# Max drawdown
cumulative = (1 + returns).cumprod()
running_max = cumulative.expanding().max()
drawdown = (cumulative - running_max) / running_max
max_drawdown = drawdown.min() * 100

# Print summary
print("\n" + "="*70)
print("STOCK SUMMARY")
print("="*70)
print(f"Company: {company_name}")
print(f"Sector: {sector}")
print(f"Industry: {industry}")
print(f"Current Price: ${current_price:.2f}")
if market_cap > 0:
    market_cap_b = market_cap / 1e9
    print(f"Market Cap: ${market_cap_b:.2f}B")
print(f"Total Return ({PERIOD}): {total_return:.2f}%")
print(f"Annualized Return: {annualized_return:.2f}%")
print(f"Volatility (Annualized): {volatility:.2f}%")
print(f"Max Drawdown: {max_drawdown:.2f}%")
print(f"RSI (14): {rsi.iloc[-1]:.2f}")
print(f"MACD: {macd.iloc[-1]:.4f}")
if current_volume is not None and avg_volume is not None and avg_volume > 0:
    volume_ratio = current_volume / avg_volume
    print(f"Volume Ratio (Current/Avg): {volume_ratio:.2f}x")
print("="*70)

# Create comprehensive visualization
fig = plt.figure(figsize=(20, 24))
gs = gridspec.GridSpec(6, 2, figure=fig, hspace=0.4, wspace=0.3)

# Plot 1: Price with Technical Indicators
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(hist.index, prices.values, label='Price', linewidth=2, color='black')
ax1.plot(sma_20.index, sma_20.values, label='SMA 20', linewidth=1.5, color='blue', alpha=0.7)
ax1.plot(sma_50.index, sma_50.values, label='SMA 50', linewidth=1.5, color='orange', alpha=0.7)
if len(sma_200.dropna()) > 0:
    ax1.plot(sma_200.index, sma_200.values, label='SMA 200', linewidth=1.5, color='red', alpha=0.7)
ax1.fill_between(upper_bb.index, upper_bb.values, lower_bb.values, 
                 alpha=0.1, color='gray', label='Bollinger Bands')
ax1.set_title(f'{TICKER} - Price Action with Technical Indicators', 
              fontsize=16, fontweight='bold', pad=20)
ax1.set_ylabel('Price ($)', fontsize=12)
ax1.legend(loc='upper left', fontsize=10)
ax1.grid(True, alpha=0.3)

# Plot 2: Volume
ax2 = fig.add_subplot(gs[1, :])
if volume is not None:
    # Color bars: green if price went up, red if price went down
    colors = []
    for i in range(len(prices)):
        if i == 0:
            colors.append('green')  # First bar is green by default
        else:
            colors.append('green' if prices.iloc[i] >= prices.iloc[i-1] else 'red')
    ax2.bar(hist.index, volume.values, alpha=0.6, color=colors, width=1)
    if avg_volume:
        ax2.axhline(y=avg_volume, color='orange', linestyle='--', 
                   linewidth=1.5, label=f'Avg Volume: {avg_volume:,.0f}')
    ax2.set_title('Volume', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Volume', fontsize=11)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3, axis='y')
else:
    ax2.text(0.5, 0.5, 'Volume data not available', 
             ha='center', va='center', transform=ax2.transAxes, fontsize=12)

# Plot 3: RSI
ax3 = fig.add_subplot(gs[2, 0])
ax3.plot(rsi.index, rsi.values, label='RSI', linewidth=2, color='purple')
ax3.axhline(y=70, color='red', linestyle='--', linewidth=1, label='Overbought (70)')
ax3.axhline(y=30, color='green', linestyle='--', linewidth=1, label='Oversold (30)')
ax3.fill_between(rsi.index, 30, 70, alpha=0.1, color='gray')
ax3.set_title('RSI (14)', fontsize=12, fontweight='bold')
ax3.set_ylabel('RSI', fontsize=10)
ax3.set_ylim(0, 100)
ax3.legend(loc='upper left', fontsize=8)
ax3.grid(True, alpha=0.3)

# Plot 4: MACD
ax4 = fig.add_subplot(gs[2, 1])
ax4.plot(macd.index, macd.values, label='MACD', linewidth=2, color='blue')
ax4.plot(signal.index, signal.values, label='Signal', linewidth=2, color='red')
ax4.bar(histogram.index, histogram.values, label='Histogram', alpha=0.3, color='gray')
ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax4.set_title('MACD (12, 26, 9)', fontsize=12, fontweight='bold')
ax4.set_ylabel('MACD', fontsize=10)
ax4.legend(loc='upper left', fontsize=8)
ax4.grid(True, alpha=0.3)

# Plot 5: Returns Distribution
ax5 = fig.add_subplot(gs[3, 0])
ax5.hist(returns.values * 100, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
ax5.axvline(x=0, color='red', linestyle='--', linewidth=1)
ax5.set_title('Daily Returns Distribution', fontsize=12, fontweight='bold')
ax5.set_xlabel('Daily Return (%)', fontsize=10)
ax5.set_ylabel('Frequency', fontsize=10)
ax5.grid(True, alpha=0.3, axis='y')

# Plot 6: Drawdown
ax6 = fig.add_subplot(gs[3, 1])
ax6.fill_between(drawdown.index, drawdown.values * 100, 0, alpha=0.5, color='red')
ax6.set_title('Drawdown', fontsize=12, fontweight='bold')
ax6.set_ylabel('Drawdown (%)', fontsize=10)
ax6.grid(True, alpha=0.3)

# Plot 7: Options Chain (Calls)
ax7 = fig.add_subplot(gs[4, 0])
if options_data and 'calls' in options_data and not options_data['calls'].empty:
    calls = options_data['calls']
    # Filter to near-the-money options
    calls_filtered = calls[(calls['strike'] >= current_price * 0.8) & 
                           (calls['strike'] <= current_price * 1.2)]
    if not calls_filtered.empty:
        ax7.bar(calls_filtered['strike'], calls_filtered['volume'], 
               alpha=0.6, color='green', label='Call Volume')
        ax7.axvline(x=current_price, color='black', linestyle='--', 
                   linewidth=1.5, label=f'Current Price: ${current_price:.2f}')
        ax7.set_title(f'Call Options Volume (Exp: {options_data["expiration"]})', 
                     fontsize=12, fontweight='bold')
        ax7.set_xlabel('Strike Price ($)', fontsize=10)
        ax7.set_ylabel('Volume', fontsize=10)
        ax7.legend(loc='upper left', fontsize=8)
        ax7.grid(True, alpha=0.3, axis='y')
    else:
        ax7.text(0.5, 0.5, 'No near-the-money call options', 
                ha='center', va='center', transform=ax7.transAxes, fontsize=11)
else:
    ax7.text(0.5, 0.5, 'Options data not available', 
            ha='center', va='center', transform=ax7.transAxes, fontsize=11)
    ax7.set_title('Call Options Volume', fontsize=12, fontweight='bold')

# Plot 8: Options Chain (Puts)
ax8 = fig.add_subplot(gs[4, 1])
if options_data and 'puts' in options_data and not options_data['puts'].empty:
    puts = options_data['puts']
    # Filter to near-the-money options
    puts_filtered = puts[(puts['strike'] >= current_price * 0.8) & 
                         (puts['strike'] <= current_price * 1.2)]
    if not puts_filtered.empty:
        ax8.bar(puts_filtered['strike'], puts_filtered['volume'], 
               alpha=0.6, color='red', label='Put Volume')
        ax8.axvline(x=current_price, color='black', linestyle='--', 
                   linewidth=1.5, label=f'Current Price: ${current_price:.2f}')
        ax8.set_title(f'Put Options Volume (Exp: {options_data["expiration"]})', 
                     fontsize=12, fontweight='bold')
        ax8.set_xlabel('Strike Price ($)', fontsize=10)
        ax8.set_ylabel('Volume', fontsize=10)
        ax8.legend(loc='upper left', fontsize=8)
        ax8.grid(True, alpha=0.3, axis='y')
    else:
        ax8.text(0.5, 0.5, 'No near-the-money put options', 
                ha='center', va='center', transform=ax8.transAxes, fontsize=11)
else:
    ax8.text(0.5, 0.5, 'Options data not available', 
            ha='center', va='center', transform=ax8.transAxes, fontsize=11)
    ax8.set_title('Put Options Volume', fontsize=12, fontweight='bold')

# Plot 9: Key Metrics Table
ax9 = fig.add_subplot(gs[5, :])
ax9.axis('off')

# Format volume strings
current_volume_str = f"{current_volume:,.0f}" if current_volume is not None else "N/A"
avg_volume_str = f"{avg_volume:,.0f}" if avg_volume is not None else "N/A"
if current_volume is not None and avg_volume is not None and avg_volume > 0:
    volume_ratio_str = f"{current_volume/avg_volume:.2f}x"
else:
    volume_ratio_str = "N/A"

metrics_text = f"""
KEY METRICS SUMMARY
{'='*70}
Company: {company_name}
Sector: {sector} | Industry: {industry}
Current Price: ${current_price:.2f}
Market Cap: ${market_cap/1e9:.2f}B (if available)

PERFORMANCE METRICS
Total Return ({PERIOD}): {total_return:.2f}%
Annualized Return: {annualized_return:.2f}%
Volatility (Annualized): {volatility:.2f}%
Max Drawdown: {max_drawdown:.2f}%

TECHNICAL INDICATORS
RSI (14): {rsi.iloc[-1]:.2f} {'(Overbought)' if rsi.iloc[-1] > 70 else '(Oversold)' if rsi.iloc[-1] < 30 else '(Neutral)'}
MACD: {macd.iloc[-1]:.4f}
Signal: {signal.iloc[-1]:.4f}
MACD Signal: {'Bullish' if macd.iloc[-1] > signal.iloc[-1] else 'Bearish'}

VOLUME
Current Volume: {current_volume_str}
Average Volume: {avg_volume_str}
Volume Ratio: {volume_ratio_str}

OPTIONS
Expiration Analyzed: {options_data.get('expiration', 'N/A')}
"""

if options_data and 'calls' in options_data and not options_data['calls'].empty:
    calls = options_data['calls']
    calls_near_money = calls[(calls['strike'] >= current_price * 0.95) & 
                            (calls['strike'] <= current_price * 1.05)]
    if not calls_near_money.empty:
        max_call_volume = calls_near_money['volume'].max()
        max_call_strike = calls_near_money.loc[calls_near_money['volume'].idxmax(), 'strike']
        metrics_text += f"\nMax Call Volume (near ATM): {max_call_volume:,.0f} @ ${max_call_strike:.2f}"

if options_data and 'puts' in options_data and not options_data['puts'].empty:
    puts = options_data['puts']
    puts_near_money = puts[(puts['strike'] >= current_price * 0.95) & 
                          (puts['strike'] <= current_price * 1.05)]
    if not puts_near_money.empty:
        max_put_volume = puts_near_money['volume'].max()
        max_put_strike = puts_near_money.loc[puts_near_money['volume'].idxmax(), 'strike']
        metrics_text += f"\nMax Put Volume (near ATM): {max_put_volume:,.0f} @ ${max_put_strike:.2f}"

ax9.text(0.05, 0.95, metrics_text, transform=ax9.transAxes, 
         fontsize=10, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.suptitle(f'{TICKER} - Comprehensive Stock Analysis', 
             fontsize=18, fontweight='bold', y=0.995)

# Save figure
filename = f'{TICKER}_stock_analysis.png'
plt.savefig(filename, dpi=300, bbox_inches='tight')
print(f"\n[OK] Analysis saved as '{filename}'")
plt.close()

# Print options summary if available
if options_data and ('calls' in options_data or 'puts' in options_data):
    print("\n" + "="*70)
    print("OPTIONS SUMMARY")
    print("="*70)
    print(f"Expiration: {options_data['expiration']}")
    
    if 'calls' in options_data and not options_data['calls'].empty:
        calls = options_data['calls']
        calls_near_money = calls[(calls['strike'] >= current_price * 0.9) & 
                                (calls['strike'] <= current_price * 1.1)]
        if not calls_near_money.empty:
            total_call_volume = calls_near_money['volume'].sum()
            total_call_oi = calls_near_money['openInterest'].sum()
            print(f"\nCalls (90-110% of current price):")
            print(f"  Total Volume: {total_call_volume:,.0f}")
            print(f"  Total Open Interest: {total_call_oi:,.0f}")
    
    if 'puts' in options_data and not options_data['puts'].empty:
        puts = options_data['puts']
        puts_near_money = puts[(puts['strike'] >= current_price * 0.9) & 
                              (puts['strike'] <= current_price * 1.1)]
        if not puts_near_money.empty:
            total_put_volume = puts_near_money['volume'].sum()
            total_put_oi = puts_near_money['openInterest'].sum()
            print(f"\nPuts (90-110% of current price):")
            print(f"  Total Volume: {total_put_volume:,.0f}")
            print(f"  Total Open Interest: {total_put_oi:,.0f}")

print("\n" + "="*70)
print("Analysis complete!")
print("="*70)

