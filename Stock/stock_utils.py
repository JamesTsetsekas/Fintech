#!/usr/bin/env python3
"""
Stock Utilities Module

Helper functions for fetching stock lists from indices, sectors, and other sources.
"""

import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta
import logging
import requests
from io import StringIO

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# Flag to control verbose output
VERBOSE = True

STOCK_CHART_BG = '#080b10'
STOCK_CHART_PANEL = '#10151d'
STOCK_CHART_GRID = '#2f3a46'
STOCK_CHART_TEXT = '#eef3f8'
STOCK_CHART_MUTED = '#aeb7c2'
STOCK_CHART_SPINE = '#3d4652'

def log_info(message):
    """Print info messages if verbose mode is enabled"""
    if VERBOSE:
        print(f"[INFO] {message}")

def _axes_list(axes):
    if axes is None:
        return None
    if isinstance(axes, (list, tuple)):
        return list(axes)
    try:
        return list(axes.ravel())
    except AttributeError:
        return [axes]

def apply_dark_chart_style(fig, axes=None):
    """Apply the dashboard dark theme to stock Matplotlib exports."""
    from matplotlib.colors import to_rgba

    def is_near_black(color):
        try:
            r, g, b, alpha = to_rgba(color)
            return alpha > 0 and (r + g + b) < 0.35
        except (TypeError, ValueError):
            return False

    def restyle_text(text):
        if is_near_black(text.get_color()):
            text.set_color(STOCK_CHART_TEXT)

    def restyle_legend(legend):
        if legend is None:
            return
        frame = legend.get_frame()
        frame.set_facecolor(STOCK_CHART_PANEL)
        frame.set_edgecolor(STOCK_CHART_SPINE)
        frame.set_alpha(0.94)
        for text in legend.get_texts():
            text.set_color(STOCK_CHART_TEXT)
        title = legend.get_title()
        if title:
            title.set_color(STOCK_CHART_TEXT)

    fig.patch.set_facecolor(STOCK_CHART_BG)
    target_axes = _axes_list(axes) or list(fig.get_axes())

    for ax in target_axes:
        ax.set_facecolor(STOCK_CHART_PANEL)
        ax.title.set_color(STOCK_CHART_TEXT)
        ax.xaxis.label.set_color(STOCK_CHART_TEXT)
        ax.yaxis.label.set_color(STOCK_CHART_TEXT)
        ax.xaxis.get_offset_text().set_color(STOCK_CHART_MUTED)
        ax.yaxis.get_offset_text().set_color(STOCK_CHART_MUTED)
        ax.tick_params(colors=STOCK_CHART_MUTED)

        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_color(STOCK_CHART_MUTED)

        for spine in ax.spines.values():
            spine.set_color(STOCK_CHART_SPINE)

        for gridline in ax.get_xgridlines() + ax.get_ygridlines():
            gridline.set_color(STOCK_CHART_GRID)
            gridline.set_alpha(0.45)
            gridline.set_linewidth(0.7)

        for line in ax.lines:
            if is_near_black(line.get_color()):
                line.set_color(STOCK_CHART_TEXT)

        for text in ax.texts:
            restyle_text(text)

        restyle_legend(ax.get_legend())

    for legend in fig.legends:
        restyle_legend(legend)

    for text in fig.texts:
        restyle_text(text)

    return fig

def get_sp500_tickers():
    """Get S&P 500 tickers from Wikipedia with improved error handling"""
    log_info("Fetching S&P 500 ticker list from Wikipedia...")

    # Try Wikipedia with proper headers
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        sp500_table = tables[0]

        if 'Symbol' in sp500_table.columns:
            tickers = sp500_table['Symbol'].tolist()
            tickers = [ticker.replace('.', '-') for ticker in tickers if isinstance(ticker, str)]
            log_info(f"Successfully fetched {len(tickers)} S&P 500 tickers from Wikipedia")
            return tickers
    except Exception as e:
        log_info(f"Wikipedia fetch failed: {str(e)[:100]}")

    # Fallback: Try using pandas read_html directly (simpler approach)
    try:
        log_info("Trying alternative Wikipedia fetch method...")
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        tickers = [ticker.replace('.', '-') for ticker in tickers if isinstance(ticker, str)]
        log_info(f"Successfully fetched {len(tickers)} S&P 500 tickers (alternative method)")
        return tickers
    except Exception as e:
        log_info(f"Alternative Wikipedia fetch failed: {str(e)[:100]}")

    # All methods failed - raise exception
    raise RuntimeError(
        "Failed to fetch S&P 500 tickers from Wikipedia. "
        "Check your internet connection and ensure required dependencies are installed: pip install lxml requests"
    )

def get_nasdaq100_tickers():
    """Get NASDAQ-100 tickers from Wikipedia with improved error handling"""
    log_info("Fetching NASDAQ-100 ticker list from Wikipedia...")

    # Try NASDAQ-100 Wikipedia page with proper headers
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Try main NASDAQ-100 page first
        url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        nasdaq_table = None

        for table in tables:
            if 'Ticker' in table.columns or 'Symbol' in table.columns:
                nasdaq_table = table
                break

        if nasdaq_table is not None:
            col_name = 'Ticker' if 'Ticker' in nasdaq_table.columns else 'Symbol'
            tickers = nasdaq_table[col_name].tolist()
            tickers = [str(ticker).split()[0] for ticker in tickers if pd.notna(ticker)]
            log_info(f"Successfully fetched {len(tickers)} NASDAQ-100 tickers from Wikipedia")
            return tickers
    except Exception as e:
        log_info(f"NASDAQ-100 Wikipedia fetch failed: {str(e)[:100]}")

    # Try alternative NASDAQ-100 companies list page
    try:
        log_info("Trying alternative NASDAQ-100 Wikipedia page...")
        url = 'https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies'
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        nasdaq_table = tables[0]

        col_name = 'Ticker' if 'Ticker' in nasdaq_table.columns else 'Symbol'
        tickers = nasdaq_table[col_name].tolist()
        tickers = [str(ticker).split()[0] for ticker in tickers if pd.notna(ticker)]
        log_info(f"Successfully fetched {len(tickers)} NASDAQ-100 tickers (alternative method)")
        return tickers
    except Exception as e:
        log_info(f"Alternative NASDAQ-100 fetch failed: {str(e)[:100]}")

    # Fallback: Try using pandas read_html directly (simpler approach)
    try:
        log_info("Trying direct pandas read_html method...")
        url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        tables = pd.read_html(url)

        for table in tables:
            if 'Ticker' in table.columns or 'Symbol' in table.columns:
                col_name = 'Ticker' if 'Ticker' in table.columns else 'Symbol'
                tickers = table[col_name].tolist()
                tickers = [str(ticker).split()[0] for ticker in tickers if pd.notna(ticker)]
                log_info(f"Successfully fetched {len(tickers)} NASDAQ-100 tickers (direct method)")
                return tickers
    except Exception as e:
        log_info(f"Direct pandas fetch failed: {str(e)[:100]}")

    # All methods failed - raise exception
    raise RuntimeError(
        "Failed to fetch NASDAQ-100 tickers from Wikipedia. "
        "Check your internet connection and ensure required dependencies are installed: pip install lxml requests"
    )

def get_dow_tickers():
    """Get Dow Jones Industrial Average tickers from Wikipedia with improved error handling"""
    log_info("Fetching Dow Jones ticker list from Wikipedia...")

    # Try Wikipedia with proper headers
    try:
        url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))

        # Look for the table with company information (usually has 'Symbol' or 'Ticker' column)
        for table in tables:
            if 'Symbol' in table.columns or 'Ticker' in table.columns:
                col_name = 'Symbol' if 'Symbol' in table.columns else 'Ticker'
                tickers = table[col_name].tolist()
                tickers = [ticker.replace('.', '-') for ticker in tickers if isinstance(ticker, str) and ticker.strip()]
                if len(tickers) >= 25:  # DJIA should have 30 components
                    log_info(f"Successfully fetched {len(tickers)} Dow Jones tickers from Wikipedia")
                    return tickers
    except Exception as e:
        log_info(f"Dow Jones Wikipedia fetch failed: {str(e)[:100]}")

    # Fallback: Try using pandas read_html directly
    try:
        log_info("Trying alternative Dow Jones Wikipedia fetch method...")
        url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
        tables = pd.read_html(url)

        for table in tables:
            if 'Symbol' in table.columns or 'Ticker' in table.columns:
                col_name = 'Symbol' if 'Symbol' in table.columns else 'Ticker'
                tickers = table[col_name].tolist()
                tickers = [ticker.replace('.', '-') for ticker in tickers if isinstance(ticker, str) and ticker.strip()]
                if len(tickers) >= 25:
                    log_info(f"Successfully fetched {len(tickers)} Dow Jones tickers (alternative method)")
                    return tickers
    except Exception as e:
        log_info(f"Alternative Dow Jones fetch failed: {str(e)[:100]}")

    # All methods failed - raise exception
    raise RuntimeError(
        "Failed to fetch Dow Jones tickers from Wikipedia. "
        "Check your internet connection and ensure required dependencies are installed: pip install lxml requests"
    )

def get_sector_tickers_from_sp500():
    """
    Fetch S&P 500 companies and group them by sector using yfinance.
    This provides the most current sector classifications directly from market data.

    Returns:
        Dictionary mapping sector names to lists of ticker symbols
    """
    log_info("Fetching sector classifications from S&P 500 companies (this may take a few minutes)...")

    try:
        # Get S&P 500 tickers
        sp500_tickers = get_sp500_tickers()
        log_info(f"Retrieved {len(sp500_tickers)} S&P 500 tickers, now fetching sector data...")

        sector_mapping = {}
        failed_tickers = []

        for i, ticker in enumerate(sp500_tickers):
            try:
                ticker_obj = yf.Ticker(ticker)
                info = ticker_obj.info

                sector = info.get('sector', None)
                if sector:
                    if sector not in sector_mapping:
                        sector_mapping[sector] = []
                    sector_mapping[sector].append(ticker)
                else:
                    failed_tickers.append(ticker)

                if (i + 1) % 50 == 0:
                    log_info(f"  Processed {i + 1}/{len(sp500_tickers)} tickers...")

                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                failed_tickers.append(ticker)
                continue

        if len(sector_mapping) == 0:
            raise RuntimeError("Failed to fetch any sector data from S&P 500 companies")

        log_info(f"Successfully grouped {len(sp500_tickers) - len(failed_tickers)} companies into {len(sector_mapping)} sectors")
        if failed_tickers:
            log_info(f"  Failed to get sector data for {len(failed_tickers)} tickers")

        return sector_mapping

    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch sector data from S&P 500 companies: {str(e)}\n"
            "Check your internet connection and yfinance installation."
        )

def get_sector_tickers(sector_name):
    """
    Get tickers for a specific sector by fetching current data from S&P 500 companies.

    Args:
        sector_name: Name of the sector (e.g., 'Technology', 'Healthcare')

    Returns:
        List of ticker symbols in the specified sector

    Raises:
        RuntimeError: If unable to fetch sector data from the internet
    """
    sector_name = sector_name.title()

    # Fetch live sector data
    sector_mapping = get_sector_tickers_from_sp500()

    if sector_name in sector_mapping:
        return sector_mapping[sector_name]
    else:
        available_sectors = ', '.join(sorted(sector_mapping.keys()))
        raise ValueError(
            f"Unknown sector: '{sector_name}'\n"
            f"Available sectors: {available_sectors}"
        )

def get_top_stocks_by_market_cap(tickers, top_n=10, period='1y'):
    """
    Get top N stocks by market cap from a list of tickers.
    
    Args:
        tickers: List of ticker symbols
        top_n: Number of top stocks to return
        period: Time period for data (used for validation)
    
    Returns:
        List of top N tickers sorted by market cap
    """
    print(f"Fetching market cap data for {len(tickers)} tickers...")
    
    market_caps = {}
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d') if period == '1y' else None
    
    for i, ticker in enumerate(tickers):
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            
            # Try to get market cap
            market_cap = info.get('marketCap', 0)
            if market_cap == 0:
                # Try alternative keys
                market_cap = info.get('totalMarketCap', 0)
            
            if market_cap > 0:
                market_caps[ticker] = market_cap
            
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(tickers)}...")
            
            time.sleep(0.2)  # Rate limiting
        except Exception as e:
            continue
    
    # Sort by market cap and return top N
    sorted_tickers = sorted(market_caps.items(), key=lambda x: x[1], reverse=True)
    top_tickers = [ticker for ticker, _ in sorted_tickers[:top_n]]
    
    print(f"Found {len(market_caps)} stocks with market cap data")
    return top_tickers

def get_top_stocks_by_performance(tickers, top_n=10, period='1y', metric='return'):
    """
    Get top N stocks by performance (return or volatility) from a list of tickers.
    
    Args:
        tickers: List of ticker symbols
        top_n: Number of top stocks to return
        period: Time period for analysis
        metric: 'return' or 'volatility'
    
    Returns:
        List of top N tickers sorted by the specified metric
    """
    print(f"Fetching performance data for {len(tickers)} tickers...")
    
    # Calculate start date
    if period.endswith('y'):
        years = int(period[:-1])
        start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
    elif period.endswith('m'):
        months = int(period[:-1])
        start_date = (datetime.now() - timedelta(days=months*30)).strftime('%Y-%m-%d')
    else:
        start_date = period
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    performance_data = {}
    
    for i, ticker in enumerate(tickers):
        try:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(start=start_date, end=end_date)
            
            if hist.empty or len(hist) < 10:  # Need at least 10 data points
                continue
            
            if "Adj Close" in hist.columns:
                prices = hist["Adj Close"]
            elif "Close" in hist.columns:
                prices = hist["Close"]
            else:
                continue
            
            returns = prices.pct_change().dropna()
            
            if metric == 'return':
                # Calculate total return
                total_return = ((prices.iloc[-1] / prices.iloc[0]) - 1) * 100
                performance_data[ticker] = total_return
            elif metric == 'volatility':
                # Calculate annualized volatility
                volatility = returns.std() * (252 ** 0.5) * 100
                performance_data[ticker] = volatility
            
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(tickers)}...")
            
            time.sleep(0.2)  # Rate limiting
        except Exception as e:
            continue
    
    # Sort by performance metric
    if metric == 'return':
        sorted_tickers = sorted(performance_data.items(), key=lambda x: x[1], reverse=True)
    else:  # volatility - lower is better for "top" performers
        sorted_tickers = sorted(performance_data.items(), key=lambda x: x[1])
    
    top_tickers = [ticker for ticker, _ in sorted_tickers[:top_n]]
    
    print(f"Found {len(performance_data)} stocks with performance data")
    return top_tickers

def get_assets_from_file(filepath):
    """Read tickers from a text file (one per line)"""
    import os
    assets = []
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Assets file not found: {filepath}")
    
    with open(filepath, 'r') as f:
        for line in f:
            ticker = line.strip()
            if ticker and not ticker.startswith('#'):  # Ignore empty lines and comments
                assets.append(ticker)
    
    return assets

def get_stocks_from_source(source, top_n=None, sector=None, period='1y', metric='market_cap'):
    """
    Get stocks from various sources with optional filtering.
    
    Args:
        source: 'sp500', 'nasdaq', 'dow', 'sector', 'file', or 'default'
        top_n: If specified, return only top N stocks
        sector: Sector name (required if source='sector')
        period: Time period for performance-based filtering
        metric: 'market_cap', 'return', or 'volatility' (used when top_n is specified)
    
    Returns:
        List of ticker symbols
    """
    if source == 'sp500':
        tickers = get_sp500_tickers()
    elif source == 'nasdaq':
        tickers = get_nasdaq100_tickers()
    elif source == 'dow':
        tickers = get_dow_tickers()
    elif source == 'sector':
        if not sector:
            raise ValueError("Sector name required when source='sector'")
        tickers = get_sector_tickers(sector)
    else:
        return []  # 'file' and 'default' should be handled by caller
    
    # If top_n is specified, filter to top N stocks
    if top_n and len(tickers) > top_n:
        if metric == 'market_cap':
            tickers = get_top_stocks_by_market_cap(tickers, top_n, period)
        elif metric in ['return', 'volatility']:
            tickers = get_top_stocks_by_performance(tickers, top_n, period, metric)
        else:
            # Just take first N
            tickers = tickers[:top_n]
    
    return tickers
