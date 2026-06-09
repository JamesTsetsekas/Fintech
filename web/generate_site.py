#!/usr/bin/env python3
"""Generate static website data for the Fintech chart library."""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DATA_DIR = REPO_ROOT / "web" / "data"
BITCOIN_DATA_DIR = REPO_ROOT / "Bitcoin" / "data" / "bitcoin_csv_data"
BITCOIN_SITE_DATA_DIR = WEB_DATA_DIR / "bitcoin"
STOCK_SITE_DATA_DIR = WEB_DATA_DIR / "stocks"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "Bitcoin"))
sys.path.insert(0, str(REPO_ROOT / "Bitcoin" / "model_price_prediction"))

from Bitcoin.bitcoin_chart_utils import (  # noqa: E402
    load_daily_price,
    load_intraday_price,
    load_market_frame,
    power_law_band_prices,
    power_law_price,
)
from Bitcoin.run_all_reports import REPORTS as BITCOIN_REPORTS  # noqa: E402
from model_projection import apply_price_models, build_projection_frame, load_daily_fees, load_price_history  # noqa: E402
from Stock.run_all_reports import REPORTS as STOCK_REPORTS  # noqa: E402


SECTION_ORDER = [
    ("cycle-models", "Cycle Models"),
    ("technical", "Technical"),
    ("returns", "Returns"),
    ("drawdowns", "Drawdowns"),
    ("halving", "Halving"),
    ("onchain", "On-Chain"),
    ("heatmaps", "Heatmaps"),
    ("machine-learning", "Machine Learning"),
]

STOCK_SECTION_ORDER = [
    ("performance", "Performance"),
    ("volatility", "Volatility"),
    ("technical", "Technical"),
    ("correlation", "Correlation"),
    ("sector", "Sector"),
    ("individual", "Individual"),
]

POPULAR_STOCKS_TOP20 = [
    "NVDA",
    "MSFT",
    "AAPL",
    "AMZN",
    "GOOGL",
    "META",
    "AVGO",
    "TSLA",
    "BRK-B",
    "LLY",
    "JPM",
    "WMT",
    "V",
    "ORCL",
    "MA",
    "XOM",
    "NFLX",
    "COST",
    "JNJ",
    "HD",
]

DOW_30_TICKERS = [
    "AAPL",
    "AMGN",
    "AMZN",
    "AXP",
    "BA",
    "CAT",
    "CRM",
    "CSCO",
    "CVX",
    "DIS",
    "GS",
    "HD",
    "HON",
    "IBM",
    "JNJ",
    "JPM",
    "KO",
    "MCD",
    "MMM",
    "MRK",
    "MSFT",
    "NKE",
    "NVDA",
    "PG",
    "SHW",
    "TRV",
    "UNH",
    "V",
    "VZ",
    "WMT",
]

SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
}

SECTION_BY_NAME = {
    "200 DMA & 200 WMA": "technical",
    "Mayer Multiple": "technical",
    "Days at a Loss": "drawdowns",
    "Days Since ATH": "drawdowns",
    "Regime Mosaic": "heatmaps",
    "Price Acceptance Heatmap": "heatmaps",
    "Bollinger Bands": "technical",
    "Volatility Regimes": "technical",
    "Intraday Volatility Heatmap": "heatmaps",
    "Distance From 200DMA Heatmap": "heatmaps",
    "Monthly & Yearly Returns": "returns",
    "Quarterly & Yearly Returns": "returns",
    "Yearly Windows": "returns",
    "CAGR": "returns",
    "Risk-Adjusted Returns": "returns",
    "Return-Volatility Map": "returns",
    "Seasonality Heatmap": "heatmaps",
    "Pi Cycle Top": "cycle-models",
    "Pi Cycle Top Estimate": "cycle-models",
    "Power Law": "cycle-models",
    "Power Law 2": "cycle-models",
    "Power Law 3": "cycle-models",
    "Power Law Oscillator": "cycle-models",
    "Unit of Account (BTC/USD)": "technical",
    "Rainbow Chart": "cycle-models",
    "Never Look Back Price": "drawdowns",
    "Epoch Candles": "halving",
    "Monthly Candles": "technical",
    "Yearly Candles": "technical",
    "DCA Cost Basis": "returns",
    "Node Count": "onchain",
    "HODL Waves Price": "onchain",
    "Price Distribution": "technical",
    "Epoch-Over-Epoch (EOE) Growth": "halving",
    "Halving Cycles": "halving",
    "Halving Phase Compass": "halving",
    "Halving Era ROI Heatmap": "heatmaps",
    "Cycle High Drawdown": "drawdowns",
    "Drawdown Recovery Map": "drawdowns",
    "Drawdown Duration Heatmap": "heatmaps",
    "Price Prediction Models": "cycle-models",
    "Cycle Phase Dashboard": "cycle-models",
    "Price Prediction (ML)": "machine-learning",
    "Puell Multiple": "onchain",
    "Fee Pressure": "onchain",
    "Fee Pressure Heatmap": "heatmaps",
    "Miner Hashprice": "onchain",
}

DESCRIPTIONS = {
    "200 DMA & 200 WMA": "BTC price with long-term daily and weekly moving-average trend lines.",
    "Mayer Multiple": "Price divided by the 200-day moving average, with classic cycle zones.",
    "Days at a Loss": "How long historical purchase prices spent underwater.",
    "Days Since ATH": "Days since Bitcoin last made an all-time high.",
    "Regime Mosaic": "Monthly state map across trend, Mayer, Puell, drawdown, and volatility regimes.",
    "Price Acceptance Heatmap": "Where BTC spent the most time by price bucket across years and halving epochs.",
    "Bollinger Bands": "20-day moving average with volatility bands around recent price action.",
    "Volatility Regimes": "Rolling realized volatility with percentile bands.",
    "Intraday Volatility Heatmap": "24/7 volatility by weekday, month, and UTC hour.",
    "Distance From 200DMA Heatmap": "Monthly distribution of daily distance above or below the 200-day average.",
    "Monthly & Yearly Returns": "Monthly return table with yearly totals.",
    "Quarterly & Yearly Returns": "Quarterly return table with yearly totals.",
    "Yearly Windows": "One-, two-, three-, and four-year price windows.",
    "CAGR": "Compound annual growth rate through Bitcoin's network age.",
    "Risk-Adjusted Returns": "Rolling Sharpe and Sortino proxies with realized return and volatility.",
    "Return-Volatility Map": "Monthly return and volatility phase map grouped by halving epoch.",
    "Seasonality Heatmap": "Intraday and calendar return seasonality.",
    "Pi Cycle Top": "111-day and 350-day moving average crossover indicator.",
    "Pi Cycle Top Estimate": "Projection of a possible future Pi Cycle crossover.",
    "Power Law": "Long-term log-log Bitcoin price model.",
    "Power Law 2": "Power-law model with support and resistance bands.",
    "Power Law 3": "Alternative power-law band view.",
    "Power Law Oscillator": "Deviation from the power-law trend.",
    "Unit of Account (BTC/USD)": "BTC price in dollars and the reciprocal USD price in satoshis.",
    "Rainbow Chart": "Halving Price Regression bands for cycle context.",
    "Never Look Back Price": "Highest price Bitcoin reached and never traded below again.",
    "Epoch Candles": "Candles grouped by halving epoch.",
    "Monthly Candles": "Monthly OHLC candles on a log price scale.",
    "Yearly Candles": "Yearly OHLC candles on a log price scale.",
    "DCA Cost Basis": "Daily dollar-cost-averaging cost basis across time windows.",
    "Node Count": "Bitcoin node count and software version distribution.",
    "HODL Waves Price": "Holding-duration supply bands with price overlay.",
    "Price Distribution": "Historical price distribution across price ranges.",
    "Epoch-Over-Epoch (EOE) Growth": "Growth comparison across halving epochs.",
    "Halving Cycles": "Cycle performance normalized from halving starts.",
    "Halving Phase Compass": "Polar view of price multiple through the current halving epoch.",
    "Halving Era ROI Heatmap": "Month-by-month ROI since each halving.",
    "Cycle High Drawdown": "Drawdowns from cycle highs overlaid across market cycles.",
    "Drawdown Recovery Map": "Major drawdowns and recovery durations.",
    "Drawdown Duration Heatmap": "Time spent at each drawdown depth during major underwater periods.",
    "Price Prediction Models": "Spot price, Stock-to-Flow, and Power Law on one overview chart.",
    "Cycle Phase Dashboard": "Compact cycle summary combining trend, drawdown, halving progress, fees, and volatility.",
    "Price Prediction (ML)": "Random Forest next-day direction model using price-derived features.",
    "Puell Multiple": "Miner revenue divided by its 365-day moving average.",
    "Fee Pressure": "Fees, miner revenue share, and block-space fee-rate pressure.",
    "Fee Pressure Heatmap": "Monthly block fee-rate percentile distribution.",
    "Miner Hashprice": "Miner revenue per PH/s/day from difficulty-implied hashrate.",
}

INTERACTIVE_IDS = {
    "200-dma-200-wma",
    "mayer-multiple",
    "days-at-a-loss",
    "drawdown-recovery-map",
    "price-prediction-models",
    "fee-pressure",
    "fee-pressure-heatmap",
    "unit-of-account-btc-usd",
    "bollinger-bands",
    "days-since-ath",
    "regime-mosaic",
    "price-acceptance-heatmap",
    "intraday-volatility-heatmap",
    "distance-from-200dma-heatmap",
    "monthly-yearly-returns",
    "quarterly-yearly-returns",
    "yearly-windows",
    "return-volatility-map",
    "seasonality-heatmap",
    "pi-cycle-top",
    "pi-cycle-top-estimate",
    "power-law",
    "power-law-2",
    "power-law-3",
    "rainbow-chart",
    "never-look-back-price",
    "epoch-candles",
    "monthly-candles",
    "yearly-candles",
    "dca-cost-basis",
    "node-count",
    "hodl-waves-price",
    "epoch-over-epoch-eoe-growth",
    "halving-cycles",
    "halving-phase-compass",
    "halving-era-roi-heatmap",
    "cycle-high-drawdown",
    "drawdown-duration-heatmap",
    "price-distribution",
    "cycle-phase-dashboard",
    "price-prediction-ml",
    "puell-multiple",
    "power-law-oscillator",
    "volatility-regimes",
    "risk-adjusted-returns",
    "cagr",
    "miner-hashprice",
}

HALVING_INFO = [
    {"block": 0, "date": datetime(2009, 1, 3), "reward": 50},
    {"block": 210000, "date": datetime(2012, 11, 28), "reward": 25},
    {"block": 420000, "date": datetime(2016, 7, 9), "reward": 12.5},
    {"block": 630000, "date": datetime(2020, 5, 11), "reward": 6.25},
    {"block": 840000, "date": datetime(2024, 4, 19), "reward": 3.125},
    {"block": 1050000, "date": datetime(2028, 4, 19), "reward": 1.5625},
    {"block": 1260000, "date": datetime(2032, 4, 19), "reward": 0.78125},
    {"block": 1470000, "date": datetime(2036, 4, 19), "reward": 0.390625},
]

DARK_RED_COLORSCALE = [
    [0.0, "#050608"],
    [0.22, "#180708"],
    [0.48, "#3a0b0d"],
    [0.72, "#7f1d1d"],
    [0.9, "#b51d1a"],
    [1.0, "#ff5f63"],
]

DARK_DIVERGING_COLORSCALE = [
    [0.0, "#7f1d1d"],
    [0.38, "#2b0b0d"],
    [0.5, "#050608"],
    [0.62, "#0b1f17"],
    [1.0, "#166534"],
]


def slugify(value: str) -> str:
    """Return a stable URL-friendly chart id."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def section_name(section_id: str, section_order=SECTION_ORDER) -> str:
    return dict(section_order).get(section_id, "Other")


def finite_or_none(value):
    if value is None:
        return None
    try:
        if not math.isfinite(float(value)):
            return None
    except (TypeError, ValueError):
        return None
    return round(float(value), 6)


def date_values(values) -> list[str]:
    converted = pd.to_datetime(values)
    if hasattr(converted, "dt"):
        return converted.dt.strftime("%Y-%m-%d").tolist()
    return converted.strftime("%Y-%m-%d").tolist()


def numeric_values(values) -> list[float | None]:
    return [finite_or_none(value) for value in values]


def matrix_values(matrix) -> list[list[float | None]]:
    return [[finite_or_none(value) for value in row] for row in matrix]


def trace(name, x_values, y_values, color, *, axis="y", width=2.2, dash=None, hovertemplate=None):
    line = {"color": color, "width": width}
    if dash:
        line["dash"] = dash
    return {
        "name": name,
        "type": "scatter",
        "mode": "lines",
        "x": date_values(x_values),
        "y": numeric_values(y_values),
        "axis": axis,
        "line": line,
        "hovertemplate": hovertemplate,
    }


def numeric_trace(name, x_values, y_values, color, *, axis="y", width=2.2, dash=None, hovertemplate=None):
    line = {"color": color, "width": width}
    if dash:
        line["dash"] = dash
    return {
        "name": name,
        "type": "scatter",
        "mode": "lines",
        "x": numeric_values(x_values),
        "y": numeric_values(y_values),
        "axis": axis,
        "line": line,
        "hovertemplate": hovertemplate,
    }


def usd_label(value: float) -> str:
    if not math.isfinite(value):
        return "n/a"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}k"
    return f"${value:,.0f}"


def pct_label(value: float) -> str:
    return f"{value:+.1f}%"


def add_power_law_columns(data):
    """Add Bitbo-style power-law price and oscillator columns."""
    modeled = data[data["Price"] > 0].copy()
    modeled["Days_Since_Genesis"] = (modeled["Date"] - pd.Timestamp("2009-01-03")).dt.days
    modeled["Power_Law"] = power_law_price(modeled["Days_Since_Genesis"])
    modeled["Power_Law_Oscillator"] = np.log(modeled["Price"] / modeled["Power_Law"]) * 100
    return modeled[modeled["Days_Since_Genesis"] > 0].copy()


def power_law_frame(data, dates):
    frame = pd.DataFrame({"Date": pd.to_datetime(dates)})
    frame["Days_Since_Genesis"] = (frame["Date"] - pd.Timestamp("2009-01-03")).dt.days
    frame = frame[frame["Days_Since_Genesis"] > 0].copy()
    frame["Power_Law"], frame["Support"], frame["Resistance"] = power_law_band_prices(frame["Days_Since_Genesis"])
    return frame


def hpr_price(days):
    days_array = np.asarray(days, dtype=float)
    result = np.full(days_array.shape, np.nan, dtype=float)
    mask = days_array > 0
    result[mask] = 10 ** (2.6521 * np.log(days_array[mask]) - 18.163)
    return result


def add_hpr_columns(data):
    modeled = data[data["Price"] > 0].copy()
    modeled["Days_Since_Genesis"] = (modeled["Date"] - pd.Timestamp("2009-01-03")).dt.days
    modeled["HPR"] = hpr_price(modeled["Days_Since_Genesis"])
    for name, offset in {
        "Deep_Value": -730,
        "Low": -365,
        "Blue": 0,
        "Green": 365,
        "Yellow": 730,
        "Orange": 1095,
        "Red": 1460,
    }.items():
        modeled[f"{name}_Band"] = hpr_price(modeled["Days_Since_Genesis"] + offset)
    return modeled


def add_days_since_ath_columns(data):
    modeled = data[data["Price"] > 0].copy().sort_values("Date").reset_index(drop=True)
    modeled["ATH"] = modeled["Price"].cummax()
    modeled["Is_ATH"] = modeled["Price"] >= modeled["ATH"]
    modeled["Last_ATH_Date"] = modeled["Date"].where(modeled["Is_ATH"]).ffill()
    modeled["Days_Since_ATH"] = (modeled["Date"] - modeled["Last_ATH_Date"]).dt.days
    modeled["Drawdown"] = (modeled["Price"] / modeled["ATH"] - 1) * 100
    return modeled


def add_never_look_back_columns(data):
    modeled = data[data["Price"] > 0].copy().sort_values("Date").reset_index(drop=True)
    prices = modeled["Price"].to_numpy(dtype=float)
    min_ahead = np.minimum.accumulate(prices[::-1])[::-1]
    valid_levels = np.where(prices <= min_ahead + 1e-9, prices, np.nan)
    modeled["Never_Look_Back_Price"] = pd.Series(valid_levels).cummax().fillna(0).to_numpy()
    return modeled


def ohlc_frame(data, period):
    source = data[(data["Price"] > 0) & (data["Daily_High"] > 0)].copy()
    source["Period"] = source["Date"].dt.to_period(period)
    grouped = (
        source.groupby("Period", as_index=False)
        .agg(
            Open=("Price", "first"),
            High=("Daily_High", "max"),
            Low=("Price", "min"),
            Close=("Price", "last"),
        )
        .sort_values("Period")
        .reset_index(drop=True)
    )
    grouped["Date"] = grouped["Period"].dt.to_timestamp()
    grouped = grouped[["Date", "Open", "High", "Low", "Close"]]
    return grouped


def base_payload(
    chart_id: str,
    title: str,
    summary_text: str,
    series,
    layout,
    *,
    allow_scale_toggle=False,
    default_scale="linear",
    axis_guards=None,
    scale_axes=None,
    x_value_type="date",
    show_range_selector=True,
):
    return {
        "id": chart_id,
        "title": title,
        "summary_text": summary_text,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "allow_scale_toggle": allow_scale_toggle,
        "default_scale": default_scale,
        "axis_guards": axis_guards or {},
        "scale_axes": scale_axes or ["y"],
        "x_value_type": x_value_type,
        "show_range_selector": show_range_selector,
        "series": series,
        "layout": layout,
    }


def build_price_trend():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["DMA_200"] = data["Price"].rolling(200, min_periods=180).mean()
    data["WMA_200"] = data["Price"].rolling(1400, min_periods=1000).mean()
    latest = data.iloc[-1]
    summary = f"Latest close {usd_label(latest['Price'])}; 200D {usd_label(latest['DMA_200'])}; 200W {usd_label(latest['WMA_200'])}."
    return base_payload(
        "200-dma-200-wma",
        "BTC Price Trend",
        summary,
        [
            trace("BTC price", data["Date"], data["Price"], "#f5c84b", width=2.6, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            trace("200D MA", data["Date"], data["DMA_200"], "#55d6ff", hovertemplate="%{x}<br>$%{y:,.0f}<extra>200D MA</extra>"),
            trace("200W MA", data["Date"], data["WMA_200"], "#3ce38a", hovertemplate="%{x}<br>$%{y:,.0f}<extra>200W MA</extra>"),
        ],
        {
            "yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"},
        },
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_mayer_multiple():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["DMA_200"] = data["Price"].rolling(200, min_periods=180).mean()
    data["Mayer"] = data["Price"] / data["DMA_200"]
    data = data.dropna(subset=["Mayer"])
    latest = data.iloc[-1]
    return base_payload(
        "mayer-multiple",
        "Mayer Multiple",
        f"Current Mayer Multiple {latest['Mayer']:.2f}; price is {pct_label((latest['Mayer'] - 1) * 100)} versus the 200D average.",
        [
            trace("Mayer Multiple", data["Date"], data["Mayer"], "#f5c84b", width=2.4, hovertemplate="%{x}<br>%{y:.2f}<extra>Mayer</extra>"),
        ],
        {
            "yaxis": {"title": "Price / 200D MA", "range": [0, max(3.0, float(data["Mayer"].quantile(0.995)))]},
            "shapes": [
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 0.8, "y1": 0.8, "line": {"color": "#3ce38a", "dash": "dash", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 1.0, "y1": 1.0, "line": {"color": "#eef3f8", "dash": "dot", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 2.4, "y1": 2.4, "line": {"color": "#ff5f63", "dash": "dash", "width": 1}},
            ],
        },
        axis_guards={"y": {"include": [0.8, 1.0, 2.4], "floor": 0}},
    )


def build_drawdown():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["ATH"] = data["Price"].cummax()
    data["Drawdown"] = (data["Price"] / data["ATH"] - 1) * 100
    latest = data.iloc[-1]
    return base_payload(
        "drawdown-recovery-map",
        "BTC Drawdown From ATH",
        f"Current drawdown {pct_label(latest['Drawdown'])} from the running all-time high.",
        [
            {
                **trace("Drawdown", data["Date"], data["Drawdown"], "#ff5f63", width=1.8, hovertemplate="%{x}<br>%{y:.1f}%<extra>Drawdown</extra>"),
                "fill": "tozeroy",
                "fillcolor": "rgba(255,95,99,0.24)",
            }
        ],
        {
            "yaxis": {"title": "Drawdown from ATH (%)", "range": [min(-90, float(data["Drawdown"].min()) * 1.05), 5]},
            "shapes": [
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": -20, "y1": -20, "line": {"color": "#f5c84b", "dash": "dot", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": -50, "y1": -50, "line": {"color": "#ff9f43", "dash": "dot", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": -80, "y1": -80, "line": {"color": "#ff5f63", "dash": "dot", "width": 1}},
            ],
        },
        axis_guards={"y": {"ceiling": 0}},
    )


def build_model_overview():
    price_history = load_price_history(BITCOIN_DATA_DIR / "daily_price.csv")
    daily_fees = load_daily_fees(BITCOIN_DATA_DIR)
    projection = build_projection_frame(price_history, daily_fees, datetime(2035, 1, 1), HALVING_INFO)
    projection, _coefficients = apply_price_models(projection)
    historical = projection[projection["Price"].notna() & (projection["Price"] > 0)]
    latest = historical.iloc[-1]
    return base_payload(
        "price-prediction-models",
        "Model Price Overview",
        f"Spot {usd_label(latest['Price'])}; chart compares one scarcity model and one time-based model through 2035.",
        [
            trace("BTC price", historical["Date"], historical["Price"], "#f5c84b", width=2.6, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            trace("Stock-to-Flow", projection["Date"], projection["S2F"], "#55d6ff", hovertemplate="%{x}<br>$%{y:,.0f}<extra>S2F</extra>"),
            trace("Power Law", projection["Date"], projection["Power_Law"], "#3ce38a", hovertemplate="%{x}<br>$%{y:,.0f}<extra>Power Law</extra>"),
        ],
        {
            "yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"},
        },
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_fee_pressure():
    data = load_market_frame(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["Fee_Rate_30D"] = data["Fee_Rate_Sats_VByte"].rolling(30, min_periods=7).mean()
    data["Fee_Share_30D"] = data["Fee_Share_Pct"].rolling(30, min_periods=7).mean()
    data = data.dropna(subset=["Fee_Rate_30D", "Fee_Share_30D"])
    latest = data.iloc[-1]
    return base_payload(
        "fee-pressure",
        "Fee Pressure",
        f"Latest 30D fee rate {latest['Fee_Rate_30D']:.2f} sat/vB; fees are {latest['Fee_Share_30D']:.2f}% of miner revenue.",
        [
            trace("30D fee rate", data["Date"], data["Fee_Rate_30D"], "#f5c84b", hovertemplate="%{x}<br>%{y:.2f} sat/vB<extra>Fee rate</extra>"),
            trace("30D fee share", data["Date"], data["Fee_Share_30D"], "#55d6ff", axis="y2", hovertemplate="%{x}<br>%{y:.2f}%<extra>Fee share</extra>"),
        ],
        {
            "yaxis": {"title": "Fee rate (sat/vB)", "type": "log"},
            "yaxis2": {"title": "Fees / miner revenue (%)", "overlaying": "y", "side": "right", "showgrid": False},
        },
        default_scale="log",
        axis_guards={"y2": {"floor": 0}},
    )


def build_uoa():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["USD_in_Sats"] = 100_000_000 / data["Price"]
    latest = data.iloc[-1]
    return base_payload(
        "unit-of-account-btc-usd",
        "Unit of Account",
        f"1 BTC is {usd_label(latest['Price'])}; 1 USD is {latest['USD_in_Sats']:.0f} sats.",
        [
            trace("BTC/USD", data["Date"], data["Price"], "#3ce38a", hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC/USD</extra>"),
            trace("Sats per USD", data["Date"], data["USD_in_Sats"], "#f5c84b", axis="y2", hovertemplate="%{x}<br>%{y:,.0f} sats<extra>Sats/USD</extra>"),
        ],
        {
            "yaxis": {"title": "BTC/USD", "type": "log", "tickprefix": "$"},
            "yaxis2": {"title": "Sats per USD", "type": "log", "overlaying": "y", "side": "right", "showgrid": False},
        },
        default_scale="log",
        scale_axes=["y", "y2"],
    )


def build_bollinger_bands():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["SMA_20"] = data["Price"].rolling(20, min_periods=20).mean()
    data["Std_20"] = data["Price"].rolling(20, min_periods=20).std()
    data["Upper_Band"] = data["SMA_20"] + (data["Std_20"] * 2)
    data["Lower_Band"] = data["SMA_20"] - (data["Std_20"] * 2)
    data = data.dropna(subset=["SMA_20", "Upper_Band", "Lower_Band"])
    latest = data.iloc[-1]
    lower = trace("Lower band", data["Date"], data["Lower_Band"], "rgba(148,163,184,0.72)", width=1.0, hovertemplate="%{x}<br>$%{y:,.0f}<extra>Lower band</extra>")
    upper = {
        **trace("Upper band", data["Date"], data["Upper_Band"], "rgba(148,163,184,0.72)", width=1.0, hovertemplate="%{x}<br>$%{y:,.0f}<extra>Upper band</extra>"),
        "fill": "tonexty",
        "fillcolor": "rgba(148,163,184,0.16)",
    }
    return base_payload(
        "bollinger-bands",
        "Bollinger Bands",
        f"Latest close {usd_label(latest['Price'])}; 20D band range {usd_label(latest['Lower_Band'])} to {usd_label(latest['Upper_Band'])}.",
        [
            lower,
            upper,
            trace("BTC price", data["Date"], data["Price"], "#f5c84b", width=2.4, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            trace("20D average", data["Date"], data["SMA_20"], "#3ce38a", width=1.8, hovertemplate="%{x}<br>$%{y:,.0f}<extra>20D average</extra>"),
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_days_since_ath():
    data = add_days_since_ath_columns(load_daily_price(BITCOIN_DATA_DIR))
    latest = data.iloc[-1]
    return base_payload(
        "days-since-ath",
        "Days Since ATH",
        f"Current streak {int(latest['Days_Since_ATH']):,} days since ATH; drawdown {pct_label(latest['Drawdown'])}.",
        [
            trace("BTC price", data["Date"], data["Price"], "#f5c84b", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            {
                **trace("Days since ATH", data["Date"], data["Days_Since_ATH"], "#55d6ff", axis="y2", width=1.9, hovertemplate="%{x}<br>%{y:,.0f} days<extra>Days since ATH</extra>"),
                "fill": "tozeroy",
                "fillcolor": "rgba(85,214,255,0.14)",
            },
        ],
        {
            "yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"},
            "yaxis2": {"title": "Days since ATH", "overlaying": "y", "side": "right", "showgrid": False},
        },
        axis_guards={"y2": {"floor": 0}},
    )


def build_pi_cycle_top():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["SMA111D"] = data["Price"].rolling(111, min_periods=90).mean()
    data["SMA350D_X2"] = data["Price"].rolling(350, min_periods=300).mean() * 2
    data = data.dropna(subset=["SMA111D", "SMA350D_X2"])
    latest = data.iloc[-1]
    return base_payload(
        "pi-cycle-top",
        "Pi Cycle Top",
        f"Latest 111D average {usd_label(latest['SMA111D'])}; 350D x2 average {usd_label(latest['SMA350D_X2'])}.",
        [
            trace("BTC price", data["Date"], data["Price"], "#f5c84b", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            trace("111D MA", data["Date"], data["SMA111D"], "#55d6ff", width=1.8, hovertemplate="%{x}<br>$%{y:,.0f}<extra>111D MA</extra>"),
            trace("350D MA x2", data["Date"], data["SMA350D_X2"], "#ff5f63", width=1.8, hovertemplate="%{x}<br>$%{y:,.0f}<extra>350D MA x2</extra>"),
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_pi_cycle_top_estimate():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["SMA111D"] = data["Price"].rolling(111, min_periods=90).mean()
    data["SMA350D_X2"] = data["Price"].rolling(350, min_periods=300).mean() * 2
    data = data[data["Date"] >= pd.Timestamp("2020-01-01")].dropna(subset=["SMA111D", "SMA350D_X2"])

    lookback = data.tail(10).copy()
    day_index = np.arange(len(lookback))
    sma111_slope = np.polyfit(day_index, lookback["SMA111D"], 1)[0]
    sma350_slope = np.polyfit(day_index, lookback["SMA350D_X2"], 1)[0]
    future_dates = pd.date_range(data["Date"].iloc[-1] + pd.Timedelta(days=1), periods=365, freq="D")
    days_forward = np.arange(1, len(future_dates) + 1)
    projection = pd.DataFrame(
        {
            "Date": future_dates,
            "SMA111D": data["SMA111D"].iloc[-1] + sma111_slope * days_forward,
            "SMA350D_X2": data["SMA350D_X2"].iloc[-1] + sma350_slope * days_forward,
        }
    )
    projection = projection[(projection["SMA111D"] > 0) & (projection["SMA350D_X2"] > 0)]
    cross_date = None
    spread = projection["SMA111D"] - projection["SMA350D_X2"]
    crossed = spread.shift(1).notna() & (np.sign(spread.shift(1)) != np.sign(spread))
    if crossed.any():
        cross_date = projection.loc[crossed, "Date"].iloc[0]
    cross_text = f"Projected cross around {cross_date:%b %Y}." if cross_date is not None else "No projected cross inside the next year."
    return base_payload(
        "pi-cycle-top-estimate",
        "Pi Cycle Top Estimate",
        cross_text,
        [
            trace("BTC price", data["Date"], data["Price"], "#f5c84b", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            trace("111D MA", data["Date"], data["SMA111D"], "#55d6ff", width=1.8, hovertemplate="%{x}<br>$%{y:,.0f}<extra>111D MA</extra>"),
            trace("350D MA x2", data["Date"], data["SMA350D_X2"], "#ff5f63", width=1.8, hovertemplate="%{x}<br>$%{y:,.0f}<extra>350D MA x2</extra>"),
            trace("111D projection", projection["Date"], projection["SMA111D"], "#55d6ff", width=1.8, dash="dash", hovertemplate="%{x}<br>$%{y:,.0f}<extra>111D projection</extra>"),
            trace("350D x2 projection", projection["Date"], projection["SMA350D_X2"], "#ff5f63", width=1.8, dash="dash", hovertemplate="%{x}<br>$%{y:,.0f}<extra>350D x2 projection</extra>"),
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_power_law():
    data = add_power_law_columns(load_daily_price(BITCOIN_DATA_DIR))
    latest = data.iloc[-1]
    return base_payload(
        "power-law",
        "Power Law",
        f"Latest close {usd_label(latest['Price'])}; fitted power-law trend {usd_label(latest['Power_Law'])}.",
        [
            trace("BTC price", data["Date"], data["Price"], "#f5c84b", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            trace("Power-law trend", data["Date"], data["Power_Law"], "#3ce38a", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>Power-law trend</extra>"),
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_power_law_2():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    bands = power_law_frame(data, data["Date"])
    merged = data[["Date", "Price"]].merge(bands, on="Date", how="inner")
    latest = merged.iloc[-1]
    return base_payload(
        "power-law-2",
        "Power Law 2",
        f"Spot {usd_label(latest['Price'])}; support {usd_label(latest['Support'])}; resistance {usd_label(latest['Resistance'])}.",
        [
            trace("Support", merged["Date"], merged["Support"], "#3ce38a", width=1.5, dash="dash", hovertemplate="%{x}<br>$%{y:,.0f}<extra>Support</extra>"),
            {
                **trace("Resistance", merged["Date"], merged["Resistance"], "#ff5f63", width=1.5, dash="dash", hovertemplate="%{x}<br>$%{y:,.0f}<extra>Resistance</extra>"),
                "fill": "tonexty",
                "fillcolor": "rgba(85,214,255,0.08)",
            },
            trace("Power-law trend", merged["Date"], merged["Power_Law"], "#55d6ff", width=2.0, hovertemplate="%{x}<br>$%{y:,.0f}<extra>Power-law trend</extra>"),
            trace("BTC price", merged["Date"], merged["Price"], "#f5c84b", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_power_law_3():
    historical = load_daily_price(BITCOIN_DATA_DIR)
    historical = historical[historical["Price"] > 0].copy()
    model_dates = pd.date_range(historical["Date"].min(), pd.Timestamp("2040-01-01"), freq="7D")
    if historical["Date"].max() not in set(model_dates):
        model_dates = model_dates.union(pd.DatetimeIndex([historical["Date"].max()])).sort_values()
    bands = power_law_frame(historical, model_dates)
    latest = historical.iloc[-1]
    latest_model = power_law_frame(historical, [latest["Date"]]).iloc[-1]
    return base_payload(
        "power-law-3",
        "Power Law 3",
        f"Projected power-law bands through 2040; current trend estimate {usd_label(latest_model['Power_Law'])}.",
        [
            trace("Support projection", bands["Date"], bands["Support"], "#3ce38a", width=1.5, dash="dash", hovertemplate="%{x}<br>$%{y:,.0f}<extra>Support</extra>"),
            {
                **trace("Resistance projection", bands["Date"], bands["Resistance"], "#ff5f63", width=1.5, dash="dash", hovertemplate="%{x}<br>$%{y:,.0f}<extra>Resistance</extra>"),
                "fill": "tonexty",
                "fillcolor": "rgba(245,200,75,0.07)",
            },
            trace("Power-law projection", bands["Date"], bands["Power_Law"], "#55d6ff", width=2.0, hovertemplate="%{x}<br>$%{y:,.0f}<extra>Power-law projection</extra>"),
            trace("BTC price", historical["Date"], historical["Price"], "#f5c84b", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_rainbow_chart():
    data = add_hpr_columns(load_daily_price(BITCOIN_DATA_DIR))
    latest = data.iloc[-1]
    floor = trace("Floor", data["Date"], pd.Series(0.1, index=data.index), "rgba(0,0,0,0)", width=0)
    floor["showlegend"] = False
    floor["hoverinfo"] = "skip"
    band_specs = [
        ("Deep Value", "Deep_Value_Band", "#14213d", "rgba(20,33,61,0.28)"),
        ("Low", "Low_Band", "#1d4ed8", "rgba(29,78,216,0.25)"),
        ("Trend", "Blue_Band", "#0ea5e9", "rgba(14,165,233,0.22)"),
        ("Warm", "Green_Band", "#22c55e", "rgba(34,197,94,0.19)"),
        ("Hot", "Yellow_Band", "#eab308", "rgba(234,179,8,0.18)"),
        ("Very Hot", "Orange_Band", "#f97316", "rgba(249,115,22,0.17)"),
        ("Extreme", "Red_Band", "#ef4444", "rgba(239,68,68,0.18)"),
    ]
    traces = [floor]
    for name, column, color, fillcolor in band_specs:
        band_trace = trace(name, data["Date"], data[column], color, width=1.0, hovertemplate=f"%{{x}}<br>$%{{y:,.0f}}<extra>{name}</extra>")
        band_trace["fill"] = "tonexty"
        band_trace["fillcolor"] = fillcolor
        traces.append(band_trace)
    traces.extend(
        [
            trace("HPR trend", data["Date"], data["HPR"], "#c084fc", width=1.9, hovertemplate="%{x}<br>$%{y:,.0f}<extra>HPR trend</extra>"),
            trace("BTC price", data["Date"], data["Price"], "#eef3f8", width=2.4, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
        ]
    )
    return base_payload(
        "rainbow-chart",
        "Rainbow Chart",
        f"Spot {usd_label(latest['Price'])}; HPR trend {usd_label(latest['HPR'])}.",
        traces,
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_never_look_back():
    data = add_never_look_back_columns(load_daily_price(BITCOIN_DATA_DIR))
    latest = data.iloc[-1]
    nlb = trace("Never Look Back price", data["Date"], data["Never_Look_Back_Price"], "#f5c84b", width=2.4, hovertemplate="%{x}<br>$%{y:,.0f}<extra>Never Look Back</extra>")
    nlb["line"]["shape"] = "hv"
    return base_payload(
        "never-look-back-price",
        "Never Look Back Price",
        f"Current never-look-back level {usd_label(latest['Never_Look_Back_Price'])}; spot {usd_label(latest['Price'])}.",
        [
            trace("BTC price", data["Date"], data["Price"], "rgba(238,243,248,0.62)", width=1.8, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            nlb,
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_monthly_candles():
    data = ohlc_frame(load_daily_price(BITCOIN_DATA_DIR), "M")
    latest = data.iloc[-1]
    change_pct = (latest["Close"] / latest["Open"] - 1) * 100
    return base_payload(
        "monthly-candles",
        "Monthly Candles",
        f"Latest monthly candle close {usd_label(latest['Close'])}; month change {pct_label(change_pct)}.",
        [
            {
                "name": "Monthly OHLC",
                "type": "candlestick",
                "x": date_values(data["Date"]),
                "open": numeric_values(data["Open"]),
                "high": numeric_values(data["High"]),
                "low": numeric_values(data["Low"]),
                "close": numeric_values(data["Close"]),
                "increasing": {"line": {"color": "#3ce38a"}, "fillcolor": "rgba(60,227,138,0.58)"},
                "decreasing": {"line": {"color": "#ff5f63"}, "fillcolor": "rgba(255,95,99,0.58)"},
                "hovertemplate": "%{x}<br>O $%{open:,.0f}<br>H $%{high:,.0f}<br>L $%{low:,.0f}<br>C $%{close:,.0f}<extra>Monthly OHLC</extra>",
            }
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_yearly_candles():
    data = ohlc_frame(load_daily_price(BITCOIN_DATA_DIR), "Y")
    latest = data.iloc[-1]
    change_pct = (latest["Close"] / latest["Open"] - 1) * 100
    return base_payload(
        "yearly-candles",
        "Yearly Candles",
        f"Latest yearly candle close {usd_label(latest['Close'])}; year change {pct_label(change_pct)}.",
        [
            {
                "name": "Yearly OHLC",
                "type": "candlestick",
                "x": date_values(data["Date"]),
                "open": numeric_values(data["Open"]),
                "high": numeric_values(data["High"]),
                "low": numeric_values(data["Low"]),
                "close": numeric_values(data["Close"]),
                "increasing": {"line": {"color": "#3ce38a"}, "fillcolor": "rgba(60,227,138,0.58)"},
                "decreasing": {"line": {"color": "#ff5f63"}, "fillcolor": "rgba(255,95,99,0.58)"},
                "hovertemplate": "%{x}<br>O $%{open:,.0f}<br>H $%{high:,.0f}<br>L $%{low:,.0f}<br>C $%{close:,.0f}<extra>Yearly OHLC</extra>",
            }
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
    )


def build_days_at_loss():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy().reset_index(drop=True)
    prices = data["Price"].to_numpy(dtype=float)
    data["Days_At_Loss"] = [int((prices[: index + 1] > price).sum()) for index, price in enumerate(prices)]
    data["Pct_History_At_Loss"] = data["Days_At_Loss"] / np.arange(1, len(data) + 1) * 100
    latest = data.iloc[-1]
    return base_payload(
        "days-at-a-loss",
        "Days at a Loss",
        f"{int(latest['Days_At_Loss']):,} historical daily closes are above current spot, {latest['Pct_History_At_Loss']:.1f}% of valued history.",
        [
            trace("Days at a loss", data["Date"], data["Days_At_Loss"], "#ff5f63", width=2.0, hovertemplate="%{x}<br>%{y:,.0f} days<extra>Days at loss</extra>"),
            trace("Share of history", data["Date"], data["Pct_History_At_Loss"], "#55d6ff", axis="y2", width=1.6, hovertemplate="%{x}<br>%{y:.1f}%<extra>History share</extra>"),
        ],
        {
            "yaxis": {"title": "Daily closes above spot"},
            "yaxis2": {"title": "Share of history (%)", "overlaying": "y", "side": "right", "showgrid": False, "range": [0, 100]},
        },
        axis_guards={"y": {"floor": 0}, "y2": {"include": [0, 100]}},
    )


def build_regime_mosaic():
    data = load_market_frame(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["DMA_200"] = data["Price"].rolling(200, min_periods=120).mean()
    data["Mayer"] = data["Price"] / data["DMA_200"]
    data["Drawdown"] = data["Price"] / data["Price"].cummax() - 1
    data["Return"] = np.log(data["Price"]).diff()
    data["Vol_30D"] = data["Return"].rolling(30, min_periods=20).std() * np.sqrt(365) * 100
    data["Revenue_365D_MA"] = data["Miner_Revenue_USD"].rolling(365, min_periods=180).mean()
    data["Puell"] = data["Miner_Revenue_USD"] / data["Revenue_365D_MA"]
    monthly = data.set_index("Date").resample("MS").last().dropna(subset=["Mayer", "Puell", "Drawdown", "Vol_30D"])
    vol_hi = monthly["Vol_30D"].quantile(0.75)
    z = [
        np.select([monthly["Mayer"] < 0.9, monthly["Mayer"] > 1.25], [-1, 1], default=0),
        np.select([monthly["Puell"] < 0.8, monthly["Puell"] > 2.0], [-1, 1], default=0),
        np.select([monthly["Drawdown"] < -0.5, monthly["Drawdown"] > -0.1], [-1, 1], default=0),
        np.select([monthly["Vol_30D"] < monthly["Vol_30D"].median(), monthly["Vol_30D"] > vol_hi], [-1, 1], default=0),
    ]
    return base_payload(
        "regime-mosaic",
        "Regime Mosaic",
        "Monthly cold, neutral, and hot regime states across trend, miner revenue, drawdown, and volatility.",
        [
            {
                "name": "Regime",
                "type": "heatmap",
                "x": date_values(monthly.index),
                "y": ["Trend", "Puell", "Drawdown", "Volatility"],
                "z": matrix_values(z),
                "zmin": -1,
                "zmax": 1,
                "colorscale": [[0, "#0b7a3b"], [0.5, "#27313b"], [1, "#b51d1a"]],
                "hovertemplate": "%{x}<br>%{y}: %{z}<extra>Regime</extra>",
            }
        ],
        {"yaxis": {"title": ""}},
    )


def build_price_acceptance_heatmap():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["Year"] = data["Date"].dt.year
    edges = np.logspace(np.log10(max(0.05, data["Price"].min())), np.log10(data["Price"].max() * 1.15), 26)
    labels = [f"${edges[i]:,.0f}-${edges[i + 1]:,.0f}" if edges[i] >= 1 else f"${edges[i]:.2f}-${edges[i + 1]:.2f}" for i in range(len(edges) - 1)]
    data["Bucket"] = pd.cut(data["Price"], bins=edges, labels=labels, include_lowest=True)
    table = data.groupby(["Bucket", "Year"], observed=False).size().unstack(fill_value=0).reindex(index=labels)
    return base_payload(
        "price-acceptance-heatmap",
        "Price Acceptance Heatmap",
        "Daily closes by price bucket and calendar year, showing where BTC spent the most time.",
        [
            {
                "name": "Days",
                "type": "heatmap",
                "x": [str(col) for col in table.columns],
                "y": list(table.index),
                "z": matrix_values(table.to_numpy()),
                "colorscale": DARK_RED_COLORSCALE,
                "hovertemplate": "%{x}<br>%{y}<br>%{z:,} days<extra>Acceptance</extra>",
            }
        ],
        {"xaxis": {"title": "Year"}, "yaxis": {"title": "Price bucket", "automargin": True}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_intraday_volatility_heatmap():
    data = load_intraday_price(BITCOIN_DATA_DIR)
    data["Weekday"] = data["DateTime"].dt.day_name()
    data["Hour"] = data["DateTime"].dt.hour
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    table = data.groupby(["Weekday", "Hour"])["Log_Return"].std().unstack(fill_value=np.nan).reindex(order) * np.sqrt(6 * 24 * 365) * 100
    return base_payload(
        "intraday-volatility-heatmap",
        "Intraday Volatility Heatmap",
        "Annualized 10-minute realized volatility by weekday and UTC hour.",
        [
            {
                "name": "Volatility",
                "type": "heatmap",
                "x": [f"{hour:02d}:00" for hour in table.columns],
                "y": list(table.index),
                "z": matrix_values(table.to_numpy()),
                "colorscale": DARK_RED_COLORSCALE,
                "hovertemplate": "%{y} %{x} UTC<br>%{z:.1f}% annualized<extra>Volatility</extra>",
            }
        ],
        {"xaxis": {"title": "UTC hour"}, "yaxis": {"title": "Weekday"}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_distance_from_200dma_heatmap():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["DMA_200"] = data["Price"].rolling(200, min_periods=180).mean()
    data["Distance"] = (data["Price"] / data["DMA_200"] - 1) * 100
    data = data.dropna(subset=["Distance"])
    data["Month"] = data["Date"].dt.to_period("M").dt.to_timestamp()
    edges = np.array([-80, -60, -40, -30, -20, -10, 0, 10, 20, 40, 60, 80, 120, 160, 220, 320], dtype=float)
    centers = (edges[:-1] + edges[1:]) / 2
    data["Bucket"] = pd.cut(data["Distance"].clip(edges[0], edges[-1] - 1e-9), bins=edges, labels=centers, include_lowest=True, right=False)
    table = data.groupby(["Bucket", "Month"], observed=False).size().unstack(fill_value=0).reindex(index=centers)
    share = table.div(table.sum(axis=0).replace(0, np.nan), axis=1) * 100
    return base_payload(
        "distance-from-200dma-heatmap",
        "Distance From 200DMA Heatmap",
        "Monthly distribution of daily distance from Bitcoin's 200-day moving average.",
        [
            {
                "name": "Share",
                "type": "heatmap",
                "x": date_values(share.columns),
                "y": [f"{center:.0f}%" for center in share.index],
                "z": matrix_values(share.to_numpy()),
                "colorscale": DARK_RED_COLORSCALE,
                "hovertemplate": "%{x}<br>%{y} bucket<br>%{z:.1f}% of days<extra>Distance</extra>",
            }
        ],
        {"yaxis": {"title": "Distance bucket"}},
    )


def monthly_returns_frame():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy().set_index("Date")
    monthly = data["Price"].resample("ME").last().pct_change() * 100
    frame = monthly.to_frame("Return")
    frame["Year"] = frame.index.year
    frame["Month"] = frame.index.month
    return frame.dropna()


def build_monthly_yearly_returns():
    frame = monthly_returns_frame()
    pivot = frame.pivot(index="Year", columns="Month", values="Return").tail(14)
    yearly = load_daily_price(BITCOIN_DATA_DIR)
    yearly = yearly[yearly["Price"] > 0].set_index("Date")["Price"].resample("YE").last().pct_change() * 100
    pivot[13] = yearly.reindex(pd.to_datetime([f"{year}-12-31" for year in pivot.index])).to_numpy()
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Year"]
    return base_payload(
        "monthly-yearly-returns",
        "Monthly & Yearly Returns",
        "Monthly BTC returns with yearly total column.",
        [
            {
                "name": "Return",
                "type": "heatmap",
                "x": labels,
                "y": [str(year) for year in pivot.index],
                "z": matrix_values(pivot.to_numpy()),
                "zmid": 0,
                "colorscale": DARK_DIVERGING_COLORSCALE,
                "hovertemplate": "%{y} %{x}<br>%{z:+.1f}%<extra>Return</extra>",
            }
        ],
        {"xaxis": {"title": ""}, "yaxis": {"title": "Year"}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_quarterly_yearly_returns():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy().set_index("Date")
    quarterly = data["Price"].resample("QE").last().pct_change() * 100
    frame = quarterly.to_frame("Return").dropna()
    frame["Year"] = frame.index.year
    frame["Quarter"] = frame.index.quarter
    pivot = frame.pivot(index="Year", columns="Quarter", values="Return").tail(14)
    yearly = data["Price"].resample("YE").last().pct_change() * 100
    pivot[5] = yearly.reindex(pd.to_datetime([f"{year}-12-31" for year in pivot.index])).to_numpy()
    return base_payload(
        "quarterly-yearly-returns",
        "Quarterly & Yearly Returns",
        "Quarterly BTC returns with yearly total column.",
        [
            {
                "name": "Return",
                "type": "heatmap",
                "x": ["Q1", "Q2", "Q3", "Q4", "Year"],
                "y": [str(year) for year in pivot.index],
                "z": matrix_values(pivot.to_numpy()),
                "zmid": 0,
                "colorscale": DARK_DIVERGING_COLORSCALE,
                "hovertemplate": "%{y} %{x}<br>%{z:+.1f}%<extra>Return</extra>",
            }
        ],
        {"xaxis": {"title": ""}, "yaxis": {"title": "Year"}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_yearly_windows():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    latest = data["Date"].max()
    traces = []
    for years, color in [(1, "#f5c84b"), (2, "#55d6ff"), (3, "#3ce38a"), (4, "#ff5f63")]:
        window = data[data["Date"] >= latest - pd.DateOffset(years=years)].copy()
        window["Days"] = (window["Date"] - window["Date"].iloc[0]).dt.days
        traces.append(numeric_trace(f"{years}Y window", window["Days"], window["Price"], color, hovertemplate=f"%{{x:.0f}} days<br>$%{{y:,.0f}}<extra>{years}Y</extra>"))
    return base_payload(
        "yearly-windows",
        "Yearly Windows",
        "Latest 1-, 2-, 3-, and 4-year BTC price windows aligned by elapsed days.",
        traces,
        {"xaxis": {"title": "Days from window start"}, "yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        allow_scale_toggle=True,
        default_scale="log",
        x_value_type="number",
        show_range_selector=False,
    )


def build_return_volatility_map():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy().set_index("Date")
    monthly_price = data["Price"].resample("ME").last()
    monthly_returns = monthly_price.pct_change() * 100
    daily_returns = np.log(data["Price"]).diff()
    monthly_vol = daily_returns.resample("ME").std() * np.sqrt(365) * 100
    frame = pd.DataFrame({"Return": monthly_returns, "Volatility": monthly_vol}).dropna()
    return base_payload(
        "return-volatility-map",
        "Return-Volatility Map",
        "Monthly BTC return versus realized volatility.",
        [
            {
                "name": "Months",
                "type": "scatter",
                "mode": "markers",
                "x": numeric_values(frame["Volatility"]),
                "y": numeric_values(frame["Return"]),
                "marker": {"color": numeric_values(frame.index.year), "colorscale": "Turbo", "size": 9, "opacity": 0.78, "colorbar": {"title": "Year"}},
                "hovertemplate": "%{text}<br>Vol %{x:.1f}%<br>Return %{y:+.1f}%<extra>Month</extra>",
                "text": frame.index.strftime("%Y-%m").tolist(),
            }
        ],
        {"xaxis": {"title": "Annualized volatility (%)"}, "yaxis": {"title": "Monthly return (%)"}},
        axis_guards={"y": {"include": [0]}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_seasonality_heatmap():
    data = monthly_returns_frame()
    pivot = data.pivot(index="Year", columns="Month", values="Return").tail(16)
    return base_payload(
        "seasonality-heatmap",
        "Seasonality Heatmap",
        "Calendar month BTC return seasonality by year.",
        [
            {
                "name": "Return",
                "type": "heatmap",
                "x": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                "y": [str(year) for year in pivot.index],
                "z": matrix_values(pivot.to_numpy()),
                "zmid": 0,
                "colorscale": DARK_DIVERGING_COLORSCALE,
                "hovertemplate": "%{y} %{x}<br>%{z:+.1f}%<extra>Seasonality</extra>",
            }
        ],
        {"xaxis": {"title": "Month"}, "yaxis": {"title": "Year"}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_epoch_candles():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[(data["Price"] > 0) & data["Epoch"].notna()].copy()
    grouped = data.groupby("Epoch", as_index=False).agg(Open=("Price", "first"), High=("Daily_High", "max"), Low=("Price", "min"), Close=("Price", "last"))
    labels = [f"E{int(epoch)}" for epoch in grouped["Epoch"]]
    return base_payload(
        "epoch-candles",
        "Epoch Candles",
        "OHLC candles aggregated by Bitcoin halving epoch.",
        [
            {
                "name": "Epoch OHLC",
                "type": "candlestick",
                "x": labels,
                "open": numeric_values(grouped["Open"]),
                "high": numeric_values(grouped["High"]),
                "low": numeric_values(grouped["Low"]),
                "close": numeric_values(grouped["Close"]),
                "increasing": {"line": {"color": "#3ce38a"}, "fillcolor": "rgba(60,227,138,0.58)"},
                "decreasing": {"line": {"color": "#ff5f63"}, "fillcolor": "rgba(255,95,99,0.58)"},
                "hovertemplate": "%{x}<br>O $%{open:,.0f}<br>H $%{high:,.0f}<br>L $%{low:,.0f}<br>C $%{close:,.0f}<extra>Epoch</extra>",
            }
        ],
        {"yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"}},
        default_scale="log",
        x_value_type="category",
        show_range_selector=False,
    )


def build_node_count():
    counts_path = BITCOIN_DATA_DIR / "node_software_counts_grouped.csv"
    history_path = BITCOIN_DATA_DIR / "bitcoin_node_history.csv"
    counts = pd.read_csv(counts_path)
    history = pd.read_csv(history_path)
    latest_time = pd.to_datetime(history.iloc[-1]["datetime"])
    grouped = counts.groupby("software", as_index=False)["total_count"].sum().sort_values("total_count")
    return base_payload(
        "node-count",
        "Node Count",
        f"Latest node software snapshot from {latest_time:%Y-%m-%d}.",
        [
            {
                "name": "Nodes",
                "type": "bar",
                "orientation": "h",
                "x": numeric_values(grouped["total_count"]),
                "y": grouped["software"].tolist(),
                "marker": {"color": "#f5c84b"},
                "hovertemplate": "%{y}<br>%{x:,} nodes<extra>Nodes</extra>",
            }
        ],
        {"xaxis": {"title": "Reachable nodes"}, "yaxis": {"automargin": True}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_hodl_waves_price():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    returns = np.log(data["Price"]).diff()
    vol = returns.rolling(30, min_periods=10).std().fillna(returns.std()).clip(lower=0)
    age_years = ((data["Date"] - pd.Timestamp("2009-01-03")).dt.days / 365.25).clip(lower=0)
    short = (38 + vol.rank(pct=True) * 12 - age_years.clip(upper=8) * 1.4).clip(18, 55)
    long = (12 + age_years.clip(upper=14) * 3.0 - vol.rank(pct=True) * 5).clip(4, 58)
    medium = (100 - short - long).clip(10, 55)
    total = short + medium + long
    short = short / total * 100
    medium = medium / total * 100
    long = long / total * 100
    return base_payload(
        "hodl-waves-price",
        "HODL Waves Price",
        "Repo-local proxy for short-, medium-, and long-term holder supply bands with BTC price overlay.",
        [
            {**trace("Short term proxy", data["Date"], short, "#55d6ff", width=0.8, hovertemplate="%{x}<br>%{y:.1f}%<extra>Short term</extra>"), "stackgroup": "one", "fillcolor": "rgba(85,214,255,0.45)"},
            {**trace("Medium term proxy", data["Date"], medium, "#f5c84b", width=0.8, hovertemplate="%{x}<br>%{y:.1f}%<extra>Medium term</extra>"), "stackgroup": "one", "fillcolor": "rgba(245,200,75,0.38)"},
            {**trace("Long term proxy", data["Date"], long, "#3ce38a", width=0.8, hovertemplate="%{x}<br>%{y:.1f}%<extra>Long term</extra>"), "stackgroup": "one", "fillcolor": "rgba(60,227,138,0.38)"},
            trace("BTC price", data["Date"], data["Price"], "#eef3f8", axis="y2", width=2.0, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
        ],
        {
            "yaxis": {"title": "Supply band proxy (%)", "range": [0, 100]},
            "yaxis2": {"title": "BTC price (USD)", "type": "log", "overlaying": "y", "side": "right", "showgrid": False, "tickprefix": "$"},
        },
        scale_axes=["y2"],
        axis_guards={"y": {"include": [0, 100]}},
    )


def build_epoch_over_epoch_growth():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[(data["Price"] > 0) & data["Epoch"].notna()].copy()
    colors = ["#55d6ff", "#3ce38a", "#f5c84b", "#ff5f63", "#c084fc", "#ff9f43"]
    traces = []
    summary_parts = []
    for index, epoch in enumerate(sorted(data["Epoch"].dropna().unique())):
        cycle = data[data["Epoch"] == epoch].copy()
        if len(cycle) < 30:
            continue
        start_price = float(cycle["Price"].iloc[0])
        if start_price <= 0:
            continue
        cycle["Days"] = (cycle["Date"] - cycle["Date"].iloc[0]).dt.days
        cycle["Multiple"] = cycle["Price"] / start_price
        latest_multiple = float(cycle["Multiple"].iloc[-1])
        summary_parts.append(f"E{int(epoch)} {latest_multiple:.1f}x")
        traces.append(
            numeric_trace(
                f"E{int(epoch)} ({latest_multiple:.1f}x)",
                cycle["Days"],
                cycle["Multiple"],
                colors[index % len(colors)],
                width=2.2,
                hovertemplate="%{x:.0f} days<br>%{y:.2f}x<extra>%{fullData.name}</extra>",
            )
        )
    return base_payload(
        "epoch-over-epoch-eoe-growth",
        "Epoch-Over-Epoch Growth",
        "Price multiples since each halving epoch start: " + "; ".join(summary_parts[-4:]) + ".",
        traces,
        {
            "xaxis": {"title": "Days since epoch start"},
            "yaxis": {"title": "Price multiple from epoch start", "type": "log"},
        },
        default_scale="log",
        axis_guards={"y": {"include": [1]}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_halving_phase_compass():
    market = load_market_frame(BITCOIN_DATA_DIR)
    data = market[market["Price"] > 0].copy()
    data["DMA_200"] = data["Price"].rolling(200, min_periods=180).mean()
    data["ATH"] = data["Price"].cummax()
    data["Drawdown"] = (data["Price"] / data["ATH"] - 1) * 100
    data["Fee_Rate_Pctile"] = data["Fee_Rate_Sats_VByte"].rank(pct=True) * 100
    latest = data.dropna(subset=["DMA_200", "Drawdown", "Fee_Rate_Pctile"]).iloc[-1]
    epoch_height = float(latest.get("Epoch_Height", 0) or 0)
    halving_progress = np.clip(epoch_height / 210_000 * 100, 0, 100)
    trend_distance = (latest["Price"] / latest["DMA_200"] - 1) * 100
    trend_score = np.clip((trend_distance + 50) / 2, 0, 100)
    drawdown_recovery = np.clip(100 + latest["Drawdown"], 0, 100)
    fee_score = np.clip(float(latest["Fee_Rate_Pctile"]), 0, 100)
    vol = np.log(data["Price"]).diff().rolling(30, min_periods=20).std() * np.sqrt(365) * 100
    vol_score = float(vol.rank(pct=True).iloc[-1] * 100)
    metrics = pd.DataFrame(
        {
            "Metric": ["Halving progress", "Trend strength", "Drawdown recovery", "Fee pressure", "Volatility"],
            "Score": [halving_progress, trend_score, drawdown_recovery, fee_score, vol_score],
            "Label": [
                f"{halving_progress:.1f}% through epoch",
                f"{trend_distance:+.1f}% vs 200D MA",
                f"{latest['Drawdown']:+.1f}% from ATH",
                f"{latest['Fee_Rate_Sats_VByte']:.1f} sat/vB",
                f"{vol.iloc[-1]:.1f}% 30D annualized",
            ],
        }
    )
    return base_payload(
        "halving-phase-compass",
        "Halving Phase Compass",
        f"Current epoch is {halving_progress:.1f}% complete; trend is {trend_distance:+.1f}% versus the 200D average.",
        [
            {
                "name": "Phase score",
                "type": "bar",
                "orientation": "h",
                "x": numeric_values(metrics["Score"]),
                "y": metrics["Metric"].tolist(),
                "text": metrics["Label"].tolist(),
                "marker": {"color": ["#f5c84b", "#3ce38a", "#55d6ff", "#ff9f43", "#ff5f63"]},
                "hovertemplate": "%{y}<br>%{text}<br>Score %{x:.1f}/100<extra>Phase</extra>",
            }
        ],
        {"xaxis": {"title": "Normalized cycle score", "range": [0, 100]}, "yaxis": {"automargin": True}},
        axis_guards={"x": {"include": [0, 100]}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_halving_era_roi_heatmap():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy().set_index("Date")
    monthly = data["Price"].resample("ME").last().dropna()
    era_rows = []
    labels = []
    for index, halving in enumerate(HALVING_INFO[1:5]):
        start = pd.Timestamp(halving["date"])
        end = pd.Timestamp(HALVING_INFO[index + 2]["date"]) if index + 2 < len(HALVING_INFO) else monthly.index.max()
        era = monthly[(monthly.index >= start) & (monthly.index < end)]
        if era.empty:
            continue
        start_price = float(era.iloc[0])
        roi = (era / start_price - 1) * 100
        era_rows.append(roi.reset_index(drop=True).tolist())
        labels.append(f"{halving['date'].year} halving")
    max_months = max(len(row) for row in era_rows)
    values = [row + [np.nan] * (max_months - len(row)) for row in era_rows]
    return base_payload(
        "halving-era-roi-heatmap",
        "Halving Era ROI Heatmap",
        "Month-by-month BTC return from each halving-era starting price.",
        [
            {
                "name": "ROI",
                "type": "heatmap",
                "x": [f"M{month}" for month in range(max_months)],
                "y": labels,
                "z": matrix_values(values),
                "zmid": 0,
                "colorscale": DARK_DIVERGING_COLORSCALE,
                "hovertemplate": "%{y}<br>%{x}<br>%{z:+.1f}%<extra>Halving ROI</extra>",
            }
        ],
        {"xaxis": {"title": "Months since halving"}, "yaxis": {"title": "Era"}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_drawdown_duration_heatmap():
    data = add_days_since_ath_columns(load_daily_price(BITCOIN_DATA_DIR))
    data["Underwater"] = data["Drawdown"] < -1
    data["Episode_ID"] = (data["Underwater"] & ~data["Underwater"].shift(fill_value=False)).cumsum()
    underwater = data[data["Underwater"]].copy()
    edges = np.array([-95, -85, -75, -65, -55, -45, -35, -25, -15, -5, 0], dtype=float)
    bucket_labels = [f"{int(edges[i])}% to {int(edges[i + 1])}%" for i in range(len(edges) - 1)]
    episodes = []
    for _, group in underwater.groupby("Episode_ID"):
        if group.empty:
            continue
        duration = len(group)
        max_drawdown = float(group["Drawdown"].min())
        if duration < 45 and max_drawdown > -20:
            continue
        clipped = group["Drawdown"].clip(edges[0] + 1e-6, edges[-1] - 1e-6)
        buckets = pd.cut(clipped, bins=edges, labels=bucket_labels, include_lowest=True, right=False)
        counts = buckets.value_counts().reindex(bucket_labels, fill_value=0)
        episodes.append(
            {
                "label": f"{group['Date'].iloc[0].year} ({duration}d)",
                "start": group["Date"].iloc[0],
                "duration": duration,
                "max_drawdown": max_drawdown,
                "counts": counts,
            }
        )
    episodes = sorted(episodes, key=lambda item: (item["duration"], abs(item["max_drawdown"])), reverse=True)[:14]
    episodes = sorted(episodes, key=lambda item: item["start"])
    values = np.array([episode["counts"].to_numpy(dtype=float) for episode in episodes]).T
    return base_payload(
        "drawdown-duration-heatmap",
        "Drawdown Duration Heatmap",
        "Days spent at each drawdown depth during the largest underwater periods.",
        [
            {
                "name": "Days",
                "type": "heatmap",
                "x": [episode["label"] for episode in episodes],
                "y": bucket_labels,
                "z": matrix_values(values),
                "colorscale": DARK_RED_COLORSCALE,
                "hovertemplate": "%{x}<br>%{y}<br>%{z:,} days<extra>Drawdown</extra>",
            }
        ],
        {"xaxis": {"title": "Underwater episode"}, "yaxis": {"title": "Drawdown bucket", "automargin": True}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_cycle_phase_dashboard():
    data = load_market_frame(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["DMA_200"] = data["Price"].rolling(200, min_periods=180).mean()
    data["ATH"] = data["Price"].cummax()
    data["Drawdown"] = (data["Price"] / data["ATH"] - 1) * 100
    data["Revenue_365D_MA"] = data["Miner_Revenue_USD"].rolling(365, min_periods=180).mean()
    data["Puell"] = data["Miner_Revenue_USD"] / data["Revenue_365D_MA"]
    data["Vol_30D"] = np.log(data["Price"]).diff().rolling(30, min_periods=20).std() * np.sqrt(365) * 100
    data = data.dropna(subset=["DMA_200", "Drawdown", "Puell", "Fee_Share_Pct", "Vol_30D"])
    latest = data.iloc[-1]
    metrics = pd.DataFrame(
        {
            "Metric": ["Spot / 200D", "Drawdown", "Puell", "Fee share", "Volatility"],
            "Value": [
                latest["Price"] / latest["DMA_200"],
                latest["Drawdown"],
                latest["Puell"],
                latest["Fee_Share_Pct"],
                latest["Vol_30D"],
            ],
            "Score": [
                np.clip((latest["Price"] / latest["DMA_200"]) / 2.0 * 100, 0, 100),
                np.clip(100 + latest["Drawdown"], 0, 100),
                np.clip(latest["Puell"] / 4.0 * 100, 0, 100),
                np.clip(latest["Fee_Share_Pct"] / 20.0 * 100, 0, 100),
                np.clip(latest["Vol_30D"] / data["Vol_30D"].quantile(0.95) * 100, 0, 100),
            ],
            "Label": [
                f"{latest['Price'] / latest['DMA_200']:.2f}x",
                f"{latest['Drawdown']:+.1f}%",
                f"{latest['Puell']:.2f}",
                f"{latest['Fee_Share_Pct']:.2f}%",
                f"{latest['Vol_30D']:.1f}%",
            ],
        }
    )
    return base_payload(
        "cycle-phase-dashboard",
        "Cycle Phase Dashboard",
        f"Spot is {latest['Price'] / latest['DMA_200']:.2f}x the 200D average; drawdown is {latest['Drawdown']:+.1f}%.",
        [
            {
                "name": "Cycle state",
                "type": "bar",
                "orientation": "h",
                "x": numeric_values(metrics["Score"]),
                "y": metrics["Metric"].tolist(),
                "text": metrics["Label"].tolist(),
                "marker": {"color": ["#3ce38a", "#55d6ff", "#f5c84b", "#ff9f43", "#ff5f63"]},
                "hovertemplate": "%{y}<br>%{text}<br>Normalized score %{x:.1f}<extra>Cycle</extra>",
            }
        ],
        {"xaxis": {"title": "Normalized score", "range": [0, 100]}, "yaxis": {"automargin": True}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_price_prediction_ml():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score

    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["Daily_Return"] = data["Price"].pct_change() * 100
    data["MA_7"] = data["Price"].rolling(7, min_periods=7).mean()
    data["MA_21"] = data["Price"].rolling(21, min_periods=21).mean()
    data["MA_200"] = data["Price"].rolling(200, min_periods=180).mean()
    data["Volatility_7"] = data["Daily_Return"].rolling(7, min_periods=7).std()
    data["Volatility_21"] = data["Daily_Return"].rolling(21, min_periods=21).std()
    data["Price_to_MA7"] = (data["Price"] / data["MA_7"] - 1) * 100
    data["Price_to_MA21"] = (data["Price"] / data["MA_21"] - 1) * 100
    data["Price_to_MA200"] = (data["Price"] / data["MA_200"] - 1) * 100
    data["Target"] = (data["Price"].shift(-1) > data["Price"]).astype(int)
    features = [
        "Daily_Return",
        "MA_7",
        "MA_21",
        "MA_200",
        "Volatility_7",
        "Volatility_21",
        "Price_to_MA7",
        "Price_to_MA21",
        "Price_to_MA200",
    ]
    clean = data.dropna(subset=features + ["Target"]).copy()
    split_idx = int(len(clean) * 0.8)
    x_train = clean[features].iloc[:split_idx]
    y_train = clean["Target"].iloc[:split_idx]
    x_test = clean[features].iloc[split_idx:]
    y_test = clean["Target"].iloc[split_idx:]
    model = RandomForestClassifier(n_estimators=120, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=-1)
    model.fit(x_train, y_train)
    prediction = model.predict(clean[features])
    probabilities = model.predict_proba(clean[features])
    clean["Confidence"] = probabilities.max(axis=1) * 100
    clean["Direction"] = np.where(prediction == 1, "Up", "Down")
    test_accuracy = accuracy_score(y_test, prediction[split_idx:])
    latest = clean.iloc[-1]
    return base_payload(
        "price-prediction-ml",
        "Price Prediction ML",
        f"Random Forest next-day direction: {latest['Direction']} with {latest['Confidence']:.1f}% model confidence; test accuracy {test_accuracy:.1%}.",
        [
            trace("BTC price", clean["Date"], clean["Price"], "#f5c84b", width=2.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>BTC price</extra>"),
            trace("7D MA", clean["Date"], clean["MA_7"], "#55d6ff", width=1.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>7D MA</extra>"),
            trace("21D MA", clean["Date"], clean["MA_21"], "#3ce38a", width=1.2, hovertemplate="%{x}<br>$%{y:,.0f}<extra>21D MA</extra>"),
            trace("200D MA", clean["Date"], clean["MA_200"], "#ff9f43", width=1.5, hovertemplate="%{x}<br>$%{y:,.0f}<extra>200D MA</extra>"),
            trace("Prediction confidence", clean["Date"], clean["Confidence"], "#ff5f63", axis="y2", width=1.4, hovertemplate="%{x}<br>%{y:.1f}%<extra>Confidence</extra>"),
        ],
        {
            "yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"},
            "yaxis2": {"title": "Prediction confidence (%)", "overlaying": "y", "side": "right", "showgrid": False, "range": [45, 100]},
        },
        allow_scale_toggle=True,
        default_scale="log",
        axis_guards={"y2": {"include": [50, 100]}},
    )


def build_fee_pressure_heatmap():
    data = load_market_frame(BITCOIN_DATA_DIR)
    data = data.dropna(subset=["Date", "Fee_Rate_Sats_VByte"]).copy()
    data = data[data["Fee_Rate_Sats_VByte"] >= 0]
    data["Month"] = data["Date"].dt.to_period("M").dt.to_timestamp()
    max_fee = max(1.0, float(data["Fee_Rate_Sats_VByte"].quantile(0.995)))
    edges = np.array([0, 1, 2, 5, 10, 20, 50, 100, 200, 500, max(max_fee * 1.1, 501)], dtype=float)
    edges = np.unique(edges)
    labels = [f"{edges[i]:.0f}-{edges[i + 1]:.0f}" for i in range(len(edges) - 1)]
    clipped = data["Fee_Rate_Sats_VByte"].clip(edges[0], edges[-1] - 1e-9)
    data["Bucket"] = pd.cut(clipped, bins=edges, labels=labels, include_lowest=True, right=False)
    table = data.groupby(["Bucket", "Month"], observed=False).size().unstack(fill_value=0).reindex(index=labels)
    share = table.div(table.sum(axis=0).replace(0, np.nan), axis=1) * 100
    return base_payload(
        "fee-pressure-heatmap",
        "Fee Pressure Heatmap",
        "Monthly distribution of estimated daily fee rates in sat/vB buckets.",
        [
            {
                "name": "Share",
                "type": "heatmap",
                "x": date_values(share.columns),
                "y": [f"{label} sat/vB" for label in share.index],
                "z": matrix_values(share.to_numpy()),
                "colorscale": DARK_RED_COLORSCALE,
                "hovertemplate": "%{x}<br>%{y}<br>%{z:.1f}% of days<extra>Fee pressure</extra>",
            }
        ],
        {"yaxis": {"title": "Fee-rate bucket", "automargin": True}},
    )


def build_dca_cost_basis():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy().reset_index(drop=True)
    current_date = data["Date"].iloc[-1]
    max_duration_days = int((current_date - data["Date"].iloc[0]).days)
    durations = set(range(1, min(730, max_duration_days) + 1))
    durations.update(range(730, min(1825, max_duration_days) + 1, 7))
    durations.update(range(1825, max_duration_days + 1, 30))
    for years in [1, 2, 4, 6, 8, 10, 12, 14]:
        days = int(years * 365.25)
        if days <= max_duration_days:
            durations.add(days)

    dates = data["Date"].to_numpy()
    prices = data["Price"].to_numpy(dtype=float)
    cumulative_btc = np.cumsum(1.0 / prices)
    rows = []
    for duration_days in sorted(durations):
        start_date = current_date - pd.Timedelta(days=duration_days)
        start_idx = int(np.searchsorted(dates, np.datetime64(start_date), side="left"))
        if start_idx >= len(data):
            continue
        btc_bought = cumulative_btc[-1] - (cumulative_btc[start_idx - 1] if start_idx > 0 else 0)
        days_in_period = len(data) - start_idx
        if btc_bought <= 0 or days_in_period <= 0:
            continue
        rows.append(
            {
                "Years": duration_days / 365.25,
                "DCA_Cost_Basis": days_in_period / btc_bought,
                "Start_Price": prices[start_idx],
            }
        )
    frame = pd.DataFrame(rows).sort_values("Years")
    latest = frame.iloc[0]
    return base_payload(
        "dca-cost-basis",
        "DCA Cost Basis",
        f"One-day DCA basis {usd_label(latest['DCA_Cost_Basis'])}; longer durations show the weighted average entry price.",
        [
            numeric_trace("DCA cost basis", frame["Years"], frame["DCA_Cost_Basis"], "#f5c84b", width=2.4, hovertemplate="%{x:.2f} years<br>$%{y:,.0f}<extra>DCA basis</extra>"),
            numeric_trace("Starting price", frame["Years"], frame["Start_Price"], "#55d6ff", width=1.8, hovertemplate="%{x:.2f} years<br>$%{y:,.0f}<extra>Start price</extra>"),
        ],
        {
            "xaxis": {"title": "Daily DCA duration (years)", "autorange": "reversed"},
            "yaxis": {"title": "BTC price (USD)", "type": "log", "tickprefix": "$"},
        },
        allow_scale_toggle=True,
        default_scale="log",
        x_value_type="number",
        show_range_selector=False,
    )


def build_halving_cycles():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[(data["Price"] > 0) & data["Block_Height"].notna()].copy()
    cycles = {
        2: {"start": 210_000, "end": 420_000, "color": "#90ee90"},
        3: {"start": 420_000, "end": 630_000, "color": "#ff69b4"},
        4: {"start": 630_000, "end": 840_000, "color": "#55d6ff"},
        5: {"start": 840_000, "end": 1_050_000, "color": "#f5c84b"},
    }
    traces = []
    summary_parts = []
    for cycle, info in cycles.items():
        cycle_data = data[(data["Block_Height"] >= info["start"]) & (data["Block_Height"] <= info["end"])].copy()
        if cycle_data.empty:
            continue
        start_price = cycle_data["Price"].iloc[0]
        cycle_data["Progress"] = (cycle_data["Block_Height"] - info["start"]) / 210_000 * 100
        cycle_data["Multiple"] = cycle_data["Price"] / start_price
        latest_multiple = cycle_data["Multiple"].iloc[-1]
        summary_parts.append(f"E{cycle} {latest_multiple:.1f}x")
        traces.append(
            numeric_trace(
                f"E{cycle} ({latest_multiple:.1f}x)",
                cycle_data["Progress"],
                cycle_data["Multiple"],
                info["color"],
                width=2.4,
                hovertemplate="%{x:.1f}% through cycle<br>%{y:.2f}x<extra>%{fullData.name}</extra>",
            )
        )
    return base_payload(
        "halving-cycles",
        "Halving Cycles",
        "Current cycle multiples: " + "; ".join(summary_parts) + ".",
        traces,
        {
            "xaxis": {"title": "Halving progress (%)", "range": [0, 100]},
            "yaxis": {"title": "Price multiple from halving", "type": "log"},
        },
        default_scale="log",
        axis_guards={"y": {"include": [1]}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_cycle_high_drawdown():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy().reset_index(drop=True)
    target_dates = [
        pd.Timestamp("2011-06-08"),
        pd.Timestamp("2013-11-30"),
        pd.Timestamp("2017-12-17"),
        pd.Timestamp("2021-11-10"),
    ]
    recent = data[data["Date"] >= data["Date"].iloc[-1] - pd.Timedelta(days=365)]
    if not recent.empty:
        target_dates.append(recent.loc[recent["Price"].idxmax(), "Date"])
    colors = ["#f5c84b", "#90ee90", "#ff69b4", "#55d6ff", "#ff8c00"]
    traces = []
    for index, target_date in enumerate(target_dates):
        closest_idx = (data["Date"] - target_date).abs().idxmin()
        high_date = data.loc[closest_idx, "Date"]
        high_price = data.loc[closest_idx, "Price"]
        cycle = data[data["Date"] >= high_date].copy()
        if index < len(target_dates) - 1:
            cycle = cycle[cycle["Date"] < target_dates[index + 1]]
        cycle["Days_After_High"] = (cycle["Date"] - high_date).dt.days
        cycle = cycle[cycle["Days_After_High"] <= 400]
        cycle["Drawdown"] = (cycle["Price"] / high_price - 1) * 100
        if cycle.empty:
            continue
        traces.append(
            numeric_trace(
                high_date.strftime("%Y high"),
                cycle["Days_After_High"],
                cycle["Drawdown"],
                colors[index % len(colors)],
                width=2.3,
                dash="dash" if index == len(target_dates) - 1 else None,
                hovertemplate="%{x:.0f} days<br>%{y:.1f}%<extra>%{fullData.name}</extra>",
            )
        )
    return base_payload(
        "cycle-high-drawdown",
        "Cycle High Drawdown",
        "Drawdown paths for major cycle highs over the first 400 days after each peak.",
        traces,
        {
            "xaxis": {"title": "Days after cycle high", "range": [0, 400]},
            "yaxis": {"title": "Drawdown from high (%)", "range": [-90, 5]},
        },
        axis_guards={"y": {"ceiling": 0}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_price_distribution():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data.copy()
    ranges = [
        (100_000, 1_000_000, "$100k - $1M"),
        (10_000, 100_000, "$10k - $100k"),
        (1_000, 10_000, "$1k - $10k"),
        (100, 1_000, "$100 - $1k"),
        (10, 100, "$10 - $100"),
        (1, 10, "$1 - $10"),
        (0.1, 1, "$0.10 - $1"),
        (0.01, 0.1, "$0.01 - $0.10"),
        (0, 0.01, "Not valued"),
    ]
    labels = []
    counts = []
    for low, high, label in ranges:
        labels.append(label)
        if low == 0:
            counts.append(int((data["Price"] <= high).sum()))
        else:
            counts.append(int(((data["Price"] >= low) & (data["Price"] < high)).sum()))
    return base_payload(
        "price-distribution",
        "Price Distribution",
        "Count of daily closes by long-term BTC/USD price bucket.",
        [
            {
                "name": "Trading days",
                "type": "bar",
                "orientation": "h",
                "x": counts[::-1],
                "y": labels[::-1],
                "marker": {"color": "#f5c84b"},
                "hovertemplate": "%{y}<br>%{x:,} days<extra>Price bucket</extra>",
            }
        ],
        {
            "xaxis": {"title": "Daily closes"},
            "yaxis": {"title": "BTC/USD bucket", "automargin": True},
            "hovermode": "closest",
        },
        x_value_type="number",
        show_range_selector=False,
    )


def build_puell_multiple():
    data = load_market_frame(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["Revenue_365D_MA"] = data["Miner_Revenue_USD"].rolling(365, min_periods=180).mean()
    data["Puell"] = data["Miner_Revenue_USD"] / data["Revenue_365D_MA"]
    data["Puell_30D"] = data["Puell"].rolling(30, min_periods=10).mean()
    data = data.dropna(subset=["Puell", "Puell_30D"])
    latest = data.iloc[-1]
    return base_payload(
        "puell-multiple",
        "Puell Multiple",
        f"Current 30D Puell Multiple {latest['Puell_30D']:.2f}; miner revenue versus its 365D baseline.",
        [
            trace("Daily Puell", data["Date"], data["Puell"], "#55d6ff", width=1.3, hovertemplate="%{x}<br>%{y:.2f}<extra>Daily Puell</extra>"),
            trace("30D average", data["Date"], data["Puell_30D"], "#f5c84b", width=2.4, hovertemplate="%{x}<br>%{y:.2f}<extra>30D Puell</extra>"),
        ],
        {
            "yaxis": {"title": "Puell Multiple", "range": [0, max(4.0, float(data["Puell"].quantile(0.995)))]},
            "shapes": [
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 0.5, "y1": 0.5, "line": {"color": "#3ce38a", "dash": "dash", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 1.0, "y1": 1.0, "line": {"color": "#eef3f8", "dash": "dot", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 2.5, "y1": 2.5, "line": {"color": "#ff5f63", "dash": "dash", "width": 1}},
            ],
        },
        axis_guards={"y": {"include": [0.5, 1.0, 2.5], "floor": 0}},
    )


def build_power_law_oscillator():
    data = add_power_law_columns(load_daily_price(BITCOIN_DATA_DIR))
    latest = data.iloc[-1]
    return base_payload(
        "power-law-oscillator",
        "Power Law Oscillator",
        f"Current oscillator {latest['Power_Law_Oscillator']:+.1f}; positive values trade above the fitted power-law trend.",
        [
            {
                **trace("Oscillator", data["Date"], data["Power_Law_Oscillator"], "#f5c84b", width=1.9, hovertemplate="%{x}<br>%{y:+.1f}<extra>Oscillator</extra>"),
                "fill": "tozeroy",
                "fillcolor": "rgba(245,200,75,0.14)",
            }
        ],
        {
            "yaxis": {"title": "Log deviation from power law"},
            "shapes": [
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 0, "y1": 0, "line": {"color": "#eef3f8", "dash": "dot", "width": 1}},
            ],
        },
        axis_guards={"y": {"include": [0]}},
    )


def build_volatility_regimes():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["Log_Return"] = np.log(data["Price"]).diff()
    data["Vol_30D"] = data["Log_Return"].rolling(30, min_periods=20).std() * np.sqrt(365) * 100
    data["Vol_90D"] = data["Log_Return"].rolling(90, min_periods=45).std() * np.sqrt(365) * 100
    data = data.dropna(subset=["Vol_30D", "Vol_90D"])
    latest = data.iloc[-1]
    return base_payload(
        "volatility-regimes",
        "Volatility Regimes",
        f"Current 30D realized volatility {latest['Vol_30D']:.1f}%; 90D volatility {latest['Vol_90D']:.1f}%.",
        [
            trace("30D realized volatility", data["Date"], data["Vol_30D"], "#f5c84b", hovertemplate="%{x}<br>%{y:.1f}%<extra>30D volatility</extra>"),
            trace("90D realized volatility", data["Date"], data["Vol_90D"], "#55d6ff", hovertemplate="%{x}<br>%{y:.1f}%<extra>90D volatility</extra>"),
        ],
        {"yaxis": {"title": "Annualized realized volatility (%)", "range": [0, float(data["Vol_30D"].quantile(0.995)) * 1.15]}},
        axis_guards={"y": {"floor": 0}},
    )


def build_risk_adjusted_returns():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    returns = np.log(data["Price"]).diff()
    downside = returns.where(returns < 0, 0)
    data["Sharpe_365D"] = returns.rolling(365, min_periods=180).mean() / returns.rolling(365, min_periods=180).std() * np.sqrt(365)
    data["Sortino_365D"] = returns.rolling(365, min_periods=180).mean() / downside.rolling(365, min_periods=180).std() * np.sqrt(365)
    data["Return_365D"] = data["Price"].pct_change(365) * 100
    data["Vol_365D"] = returns.rolling(365, min_periods=180).std() * np.sqrt(365) * 100
    data = data.dropna(subset=["Sharpe_365D", "Sortino_365D", "Return_365D", "Vol_365D"])
    latest = data.iloc[-1]
    return base_payload(
        "risk-adjusted-returns",
        "Risk-Adjusted Returns",
        f"Current 1Y Sharpe proxy {latest['Sharpe_365D']:.2f}; 1Y return {latest['Return_365D']:+.1f}%.",
        [
            trace("1Y Sharpe proxy", data["Date"], data["Sharpe_365D"], "#f5c84b", hovertemplate="%{x}<br>%{y:.2f}<extra>Sharpe</extra>"),
            trace("1Y Sortino proxy", data["Date"], data["Sortino_365D"], "#55d6ff", hovertemplate="%{x}<br>%{y:.2f}<extra>Sortino</extra>"),
            trace("1Y return", data["Date"], data["Return_365D"], "#3ce38a", axis="y2", hovertemplate="%{x}<br>%{y:+.1f}%<extra>1Y return</extra>"),
            trace("1Y volatility", data["Date"], data["Vol_365D"], "#ff5f63", axis="y2", hovertemplate="%{x}<br>%{y:.1f}%<extra>1Y volatility</extra>"),
        ],
        {
            "yaxis": {"title": "Sharpe / Sortino proxy"},
            "yaxis2": {"title": "Return / volatility (%)", "overlaying": "y", "side": "right", "showgrid": False},
        },
        axis_guards={"y": {"include": [0]}, "y2": {"include": [0]}},
    )


def build_cagr():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    first = data.iloc[0]
    years = (data["Date"] - first["Date"]).dt.days / 365.25
    data["CAGR"] = ((data["Price"] / first["Price"]) ** (1 / years.replace(0, np.nan)) - 1) * 100
    data["Trailing_4Y_CAGR"] = ((data["Price"] / data["Price"].shift(1460)) ** (365.25 / 1460) - 1) * 100
    data = data.dropna(subset=["CAGR", "Trailing_4Y_CAGR"])
    latest = data.iloc[-1]
    return base_payload(
        "cagr",
        "Bitcoin CAGR",
        f"Network-age CAGR {latest['CAGR']:.1f}%; trailing 4Y CAGR {latest['Trailing_4Y_CAGR']:.1f}%.",
        [
            trace("Network-age CAGR", data["Date"], data["CAGR"], "#f5c84b", hovertemplate="%{x}<br>%{y:.1f}%<extra>Network CAGR</extra>"),
            trace("Trailing 4Y CAGR", data["Date"], data["Trailing_4Y_CAGR"], "#55d6ff", hovertemplate="%{x}<br>%{y:.1f}%<extra>4Y CAGR</extra>"),
        ],
        {"yaxis": {"title": "CAGR (%)"}},
        axis_guards={"y": {"include": [0]}},
    )


def build_miner_hashprice():
    data = load_market_frame(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data = data.dropna(subset=["Estimated_Hashrate_EH_S", "Miner_Revenue_USD"])
    data = data[data["Estimated_Hashrate_EH_S"] > 0].copy()
    data["Hashprice_USD_PH_Day"] = data["Miner_Revenue_USD"] / (data["Estimated_Hashrate_EH_S"] * 1_000_000)
    data["Hashprice_30D"] = data["Hashprice_USD_PH_Day"].rolling(30, min_periods=10).mean()
    data = data.dropna(subset=["Hashprice_USD_PH_Day", "Hashprice_30D"])
    latest = data.iloc[-1]
    return base_payload(
        "miner-hashprice",
        "Miner Hashprice",
        f"Current 30D hashprice {usd_label(latest['Hashprice_30D'])} per PH/s/day.",
        [
            trace("Daily hashprice", data["Date"], data["Hashprice_USD_PH_Day"], "#55d6ff", width=1.2, hovertemplate="%{x}<br>$%{y:.2f}<extra>Daily hashprice</extra>"),
            trace("30D average", data["Date"], data["Hashprice_30D"], "#f5c84b", width=2.4, hovertemplate="%{x}<br>$%{y:.2f}<extra>30D hashprice</extra>"),
        ],
        {"yaxis": {"title": "USD per PH/s/day", "type": "log", "tickprefix": "$"}},
        default_scale="log",
    )


INTERACTIVE_BUILDERS = {
    "200-dma-200-wma": build_price_trend,
    "mayer-multiple": build_mayer_multiple,
    "days-at-a-loss": build_days_at_loss,
    "drawdown-recovery-map": build_drawdown,
    "price-prediction-models": build_model_overview,
    "fee-pressure": build_fee_pressure,
    "fee-pressure-heatmap": build_fee_pressure_heatmap,
    "unit-of-account-btc-usd": build_uoa,
    "bollinger-bands": build_bollinger_bands,
    "days-since-ath": build_days_since_ath,
    "regime-mosaic": build_regime_mosaic,
    "price-acceptance-heatmap": build_price_acceptance_heatmap,
    "intraday-volatility-heatmap": build_intraday_volatility_heatmap,
    "distance-from-200dma-heatmap": build_distance_from_200dma_heatmap,
    "monthly-yearly-returns": build_monthly_yearly_returns,
    "quarterly-yearly-returns": build_quarterly_yearly_returns,
    "yearly-windows": build_yearly_windows,
    "return-volatility-map": build_return_volatility_map,
    "seasonality-heatmap": build_seasonality_heatmap,
    "pi-cycle-top": build_pi_cycle_top,
    "pi-cycle-top-estimate": build_pi_cycle_top_estimate,
    "power-law": build_power_law,
    "power-law-2": build_power_law_2,
    "power-law-3": build_power_law_3,
    "rainbow-chart": build_rainbow_chart,
    "never-look-back-price": build_never_look_back,
    "epoch-candles": build_epoch_candles,
    "monthly-candles": build_monthly_candles,
    "yearly-candles": build_yearly_candles,
    "dca-cost-basis": build_dca_cost_basis,
    "node-count": build_node_count,
    "hodl-waves-price": build_hodl_waves_price,
    "epoch-over-epoch-eoe-growth": build_epoch_over_epoch_growth,
    "halving-cycles": build_halving_cycles,
    "halving-phase-compass": build_halving_phase_compass,
    "halving-era-roi-heatmap": build_halving_era_roi_heatmap,
    "cycle-high-drawdown": build_cycle_high_drawdown,
    "drawdown-duration-heatmap": build_drawdown_duration_heatmap,
    "price-distribution": build_price_distribution,
    "cycle-phase-dashboard": build_cycle_phase_dashboard,
    "price-prediction-ml": build_price_prediction_ml,
    "puell-multiple": build_puell_multiple,
    "power-law-oscillator": build_power_law_oscillator,
    "volatility-regimes": build_volatility_regimes,
    "risk-adjusted-returns": build_risk_adjusted_returns,
    "cagr": build_cagr,
    "miner-hashprice": build_miner_hashprice,
}


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, separators=(",", ": ")) + "\n", encoding="utf-8")


STOCK_PRICE_CACHE = {}


def clean_tickers(tickers) -> list[str]:
    seen = set()
    cleaned = []
    for ticker in tickers:
        ticker = str(ticker).strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        cleaned.append(ticker)
    return cleaned


def stock_universe_for_title(title: str) -> list[str]:
    title_lower = title.lower()
    if "sector" in title_lower or "jellybean" in title_lower:
        return list(SECTOR_ETFS.values())
    if "dow jones" in title_lower or "dow" in title_lower:
        return DOW_30_TICKERS
    if "nasdaq" in title_lower:
        return [
            "NVDA",
            "MSFT",
            "AAPL",
            "AMZN",
            "GOOGL",
            "META",
            "AVGO",
            "TSLA",
            "COST",
            "NFLX",
            "AMD",
            "ADBE",
            "CSCO",
            "PEP",
            "INTU",
            "QCOM",
            "TXN",
            "AMAT",
            "AMGN",
            "CMCSA",
        ]
    return POPULAR_STOCKS_TOP20


def stock_tickers_for_chart(chart: dict) -> list[str]:
    title = chart["title"]
    ticker_match = re.search(r"\(([^)]+)\)$", title)
    if ("Technical Indicators" in title or "Individual Stock Analysis" in title) and ticker_match:
        return clean_tickers([ticker_match.group(1)])
    return clean_tickers(stock_universe_for_title(title))


def stock_period_for_chart(chart: dict) -> str:
    title = chart["title"].lower()
    if "individual" in title or "technical" in title:
        return "2y"
    if "jellybean" in title or "sector" in title:
        return "10y"
    return "1y"


def fetch_stock_prices(tickers: list[str], period: str = "1y") -> pd.DataFrame:
    tickers = clean_tickers(tickers)
    cache_key = (tuple(tickers), period)
    if cache_key in STOCK_PRICE_CACHE:
        return STOCK_PRICE_CACHE[cache_key].copy()
    for (cached_tickers, cached_period), cached_prices in STOCK_PRICE_CACHE.items():
        if cached_period == period and all(ticker in cached_prices.columns for ticker in tickers):
            prices = cached_prices[tickers].copy()
            STOCK_PRICE_CACHE[cache_key] = prices
            return prices.copy()
    if not tickers:
        return pd.DataFrame()

    try:
        raw = yf.download(
            tickers=" ".join(tickers),
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
            timeout=12,
        )
    except Exception as exc:
        print(f"WARNING: yfinance download failed for {', '.join(tickers)}: {exc}")
        raw = pd.DataFrame()

    if raw.empty:
        prices = pd.DataFrame()
    elif isinstance(raw.columns, pd.MultiIndex):
        column_level = raw.columns.get_level_values(0)
        price_field = "Close" if "Close" in column_level else "Adj Close"
        prices = raw[price_field].copy()
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(tickers[0])
    else:
        price_field = "Close" if "Close" in raw.columns else "Adj Close"
        prices = raw[[price_field]].rename(columns={price_field: tickers[0]}).copy()

    if not prices.empty:
        prices.index = pd.to_datetime(prices.index).tz_localize(None)
        prices = prices.rename(columns={column: str(column).upper() for column in prices.columns})
        available = [ticker for ticker in tickers if ticker in prices.columns]
        prices = prices[available].apply(pd.to_numeric, errors="coerce").dropna(how="all")

    STOCK_PRICE_CACHE[cache_key] = prices
    return prices.copy()


def prime_stock_price_cache(charts) -> None:
    tickers_by_period = {}
    for chart in charts:
        if chart["kind"] != "interactive":
            continue
        period = "1y" if "Correlation" in chart["title"] else stock_period_for_chart(chart)
        tickers_by_period.setdefault(period, set()).update(stock_tickers_for_chart(chart))
    for period, tickers in sorted(tickers_by_period.items()):
        fetch_stock_prices(sorted(tickers), period=period)


def stock_empty_payload(chart: dict, reason: str):
    return base_payload(
        chart["id"],
        chart["title"],
        reason,
        [
            {
                "name": "No data",
                "type": "bar",
                "orientation": "h",
                "x": [0],
                "y": ["No data"],
                "marker": {"color": "#64748b"},
                "hovertemplate": "No stock data loaded<extra></extra>",
            }
        ],
        {"xaxis": {"title": ""}, "yaxis": {"automargin": True}},
        x_value_type="number",
        show_range_selector=False,
    )


def stock_name_for_ticker(ticker: str) -> str:
    for sector, sector_ticker in SECTOR_ETFS.items():
        if ticker == sector_ticker:
            return f"{sector} ({ticker})"
    return ticker


def build_stock_performance_payload(chart: dict):
    tickers = stock_tickers_for_chart(chart)
    period = stock_period_for_chart(chart)
    prices = fetch_stock_prices(tickers, period=period)
    if prices.empty:
        return stock_empty_payload(chart, "Stock price data was unavailable from yfinance during site generation.")
    prices = prices.ffill().dropna(how="all")
    bases = prices.apply(lambda series: series.dropna().iloc[0] if not series.dropna().empty else np.nan)
    normalized = prices.divide(bases).mul(100)
    latest_returns = normalized.iloc[-1].dropna().sort_values(ascending=False) - 100
    leader = latest_returns.index[0] if not latest_returns.empty else "n/a"
    summary = f"{len(normalized.columns)} tickers over {period}; leader {leader} at {latest_returns.iloc[0]:+.1f}%." if not latest_returns.empty else f"{len(normalized.columns)} tickers over {period}."
    colors = ["#f5c84b", "#55d6ff", "#3ce38a", "#ff5f63", "#c084fc", "#ff9f43", "#90ee90", "#ff69b4"]
    series = [
        trace(
            stock_name_for_ticker(ticker),
            normalized.index,
            normalized[ticker],
            colors[index % len(colors)],
            width=1.8,
            hovertemplate="%{x}<br>%{y:.1f}<extra>%{fullData.name}</extra>",
        )
        for index, ticker in enumerate(normalized.columns)
    ]
    return base_payload(
        chart["id"],
        chart["title"],
        summary,
        series,
        {"yaxis": {"title": "Index (first close = 100)"}},
        axis_guards={"y": {"include": [100]}},
    )


def build_stock_volatility_payload(chart: dict):
    tickers = stock_tickers_for_chart(chart)
    period = stock_period_for_chart(chart)
    prices = fetch_stock_prices(tickers, period=period)
    if prices.empty:
        return stock_empty_payload(chart, "Stock price data was unavailable from yfinance during site generation.")
    returns = prices.ffill().pct_change(fill_method=None)
    vol = returns.rolling(30, min_periods=15).std() * np.sqrt(252) * 100
    vol = vol.dropna(how="all")
    if vol.empty:
        return stock_empty_payload(chart, "Not enough stock history was available to calculate rolling volatility.")
    latest_vol = vol.iloc[-1].dropna().sort_values(ascending=False)
    leader = latest_vol.index[0] if not latest_vol.empty else "n/a"
    summary = f"30-trading-day annualized volatility over {period}; highest latest reading is {leader} at {latest_vol.iloc[0]:.1f}%." if not latest_vol.empty else "30-trading-day annualized volatility."
    colors = ["#ff5f63", "#f5c84b", "#55d6ff", "#3ce38a", "#c084fc", "#ff9f43", "#90ee90", "#ff69b4"]
    series = [
        trace(
            stock_name_for_ticker(ticker),
            vol.index,
            vol[ticker],
            colors[index % len(colors)],
            width=1.7,
            hovertemplate="%{x}<br>%{y:.1f}%<extra>%{fullData.name}</extra>",
        )
        for index, ticker in enumerate(vol.columns)
    ]
    return base_payload(
        chart["id"],
        chart["title"],
        summary,
        series,
        {"yaxis": {"title": "Annualized volatility (%)"}},
        axis_guards={"y": {"floor": 0}},
    )


def build_stock_correlation_payload(chart: dict):
    tickers = stock_tickers_for_chart(chart)
    prices = fetch_stock_prices(tickers, period="1y")
    if prices.empty:
        return stock_empty_payload(chart, "Stock price data was unavailable from yfinance during site generation.")
    returns = prices.ffill().pct_change(fill_method=None).dropna(how="all")
    corr = returns.corr().dropna(how="all").dropna(how="all", axis=1)
    if corr.empty:
        return stock_empty_payload(chart, "Not enough stock return history was available to calculate correlation.")
    avg_corr = corr.where(~np.eye(len(corr), dtype=bool)).stack().mean()
    return base_payload(
        chart["id"],
        chart["title"],
        f"One-year daily return correlation matrix; average pairwise correlation {avg_corr:.2f}.",
        [
            {
                "name": "Correlation",
                "type": "heatmap",
                "x": corr.columns.tolist(),
                "y": corr.index.tolist(),
                "z": matrix_values(corr.to_numpy()),
                "zmin": -1,
                "zmax": 1,
                "colorscale": DARK_DIVERGING_COLORSCALE,
                "hovertemplate": "%{y} vs %{x}<br>%{z:.2f}<extra>Correlation</extra>",
            }
        ],
        {"xaxis": {"title": ""}, "yaxis": {"title": "", "automargin": True}},
        x_value_type="category",
        show_range_selector=False,
    )


def build_stock_technical_payload(chart: dict):
    ticker = stock_tickers_for_chart(chart)[0]
    prices = fetch_stock_prices([ticker], period="2y")
    if prices.empty or ticker not in prices.columns:
        return stock_empty_payload(chart, f"{ticker} price data was unavailable from yfinance during site generation.")
    frame = prices[[ticker]].rename(columns={ticker: "Close"}).dropna().copy()
    frame["SMA20"] = frame["Close"].rolling(20, min_periods=10).mean()
    frame["SMA50"] = frame["Close"].rolling(50, min_periods=25).mean()
    frame["SMA200"] = frame["Close"].rolling(200, min_periods=120).mean()
    latest = frame.iloc[-1]
    return base_payload(
        chart["id"],
        chart["title"],
        f"{ticker} latest adjusted close {usd_label(latest['Close'])}; 50D average {usd_label(latest['SMA50'])}.",
        [
            trace(ticker, frame.index, frame["Close"], "#f5c84b", width=2.3, hovertemplate="%{x}<br>$%{y:,.2f}<extra>%{fullData.name}</extra>"),
            trace("20D average", frame.index, frame["SMA20"], "#55d6ff", width=1.4, hovertemplate="%{x}<br>$%{y:,.2f}<extra>20D</extra>"),
            trace("50D average", frame.index, frame["SMA50"], "#3ce38a", width=1.5, hovertemplate="%{x}<br>$%{y:,.2f}<extra>50D</extra>"),
            trace("200D average", frame.index, frame["SMA200"], "#ff5f63", width=1.7, hovertemplate="%{x}<br>$%{y:,.2f}<extra>200D</extra>"),
        ],
        {"yaxis": {"title": "Adjusted price (USD)", "tickprefix": "$"}},
    )


def build_stock_jellybean_payload(chart: dict):
    tickers = list(SECTOR_ETFS.values())
    prices = fetch_stock_prices(tickers, period="10y")
    if prices.empty:
        return stock_empty_payload(chart, "Sector ETF price data was unavailable from yfinance during site generation.")
    returns = (prices.ffill().iloc[-1] / prices.ffill().apply(lambda series: series.dropna().iloc[0]) - 1) * 100
    returns = returns.dropna().sort_values()
    labels = [stock_name_for_ticker(ticker) for ticker in returns.index]
    return base_payload(
        chart["id"],
        chart["title"],
        f"Ten-year sector ETF returns; strongest sector {labels[-1]} at {returns.iloc[-1]:+.1f}%.",
        [
            {
                "name": "10Y return",
                "type": "bar",
                "orientation": "h",
                "x": numeric_values(returns),
                "y": labels,
                "marker": {"color": ["#ff5f63" if value < 0 else "#3ce38a" for value in returns]},
                "hovertemplate": "%{y}<br>%{x:+.1f}%<extra>Sector return</extra>",
            }
        ],
        {"xaxis": {"title": "Total return (%)"}, "yaxis": {"automargin": True}},
        axis_guards={"x": {"include": [0]}},
        x_value_type="number",
        show_range_selector=False,
    )


def build_stock_payload(chart: dict):
    title = chart["title"]
    if "Correlation" in title:
        return build_stock_correlation_payload(chart)
    if "Volatility" in title:
        return build_stock_volatility_payload(chart)
    if "Technical Indicators" in title or "Individual Stock Analysis" in title:
        return build_stock_technical_payload(chart)
    if "Jellybean" in title:
        return build_stock_jellybean_payload(chart)
    return build_stock_performance_payload(chart)


def stock_section_id(title: str) -> str:
    if "Correlation" in title:
        return "correlation"
    if "Performance Comparison" in title:
        return "performance"
    if "Volatility" in title:
        return "volatility"
    if "Technical Indicators" in title:
        return "technical"
    if "Individual Stock Analysis" in title:
        return "individual"
    if "Sector" in title or "Jellybean" in title:
        return "sector"
    return "performance"


def stock_description(title: str, image_path: Path) -> str:
    if "Correlation" in title:
        return "Clustered correlation report for the selected stock universe."
    if "Performance Comparison" in title:
        return "Relative stock performance over the configured lookback window."
    if "Volatility" in title:
        return "Volatility, risk, and return comparison across the selected stock group."
    if "Technical Indicators" in title:
        ticker = image_path.stem.replace("_technical_indicators", "")
        return f"Technical indicator dashboard for {ticker}."
    if "Individual Stock Analysis" in title:
        ticker = image_path.stem.replace("_stock_analysis", "")
        return f"Individual price, return, and technical analysis for {ticker}."
    if "Jellybean" in title:
        return "Sector return ranking view across the configured historical period."
    if "Sector Performance" in title:
        return "Sector performance comparison for the configured market period."
    return "Generated stock market report."


def stock_chart_title(report_title: str, image_path: Path) -> str:
    if image_path.name.endswith("_technical_indicators.png"):
        ticker = image_path.stem.replace("_technical_indicators", "")
        return f"Stock Technical Indicators ({ticker})"
    if image_path.name.endswith("_stock_analysis.png"):
        ticker = image_path.stem.replace("_stock_analysis", "")
        return f"Individual Stock Analysis ({ticker})"
    return report_title


def build_chart_manifest():
    charts = []
    for index, report in enumerate(BITCOIN_REPORTS):
        title = report["name"]
        chart_id = slugify(title)
        section_id = SECTION_BY_NAME.get(title, "technical")
        image_path = (Path(report["path"]).parent / report["output"]).resolve()
        image_rel = image_path.relative_to(REPO_ROOT).as_posix()
        kind = "interactive" if chart_id in INTERACTIVE_IDS else "image"
        charts.append(
            {
                "id": chart_id,
                "title": title,
                "section_id": section_id,
                "section": section_name(section_id),
                "description": DESCRIPTIONS.get(title, "Generated Bitcoin chart report."),
                "image_path": image_rel,
                "kind": kind,
                "data_path": f"web/data/bitcoin/{chart_id}.json" if kind == "interactive" else None,
                "order": index,
                "image_exists": image_path.exists(),
            }
        )
    return charts


def build_stock_chart_manifest():
    charts = []
    seen_paths = set()
    order = 0
    for title, section_id, description in [
        (
            "Popular Stocks Top 20 Performance",
            "performance",
            "Interactive normalized performance view for a curated top-20 popular large-cap stock universe.",
        ),
        (
            "Popular Stocks Top 20 Volatility",
            "volatility",
            "Interactive rolling volatility view for a curated top-20 popular large-cap stock universe.",
        ),
        (
            "Popular Stocks Top 20 Correlation",
            "correlation",
            "Interactive one-year correlation heatmap for a curated top-20 popular large-cap stock universe.",
        ),
    ]:
        chart_id = slugify(title)
        charts.append(
            {
                "id": chart_id,
                "title": title,
                "section_id": section_id,
                "section": section_name(section_id, STOCK_SECTION_ORDER),
                "description": description,
                "image_path": None,
                "kind": "interactive",
                "data_path": f"web/data/stocks/{chart_id}.json",
                "order": order,
                "image_exists": False,
            }
        )
        order += 1

    for report in STOCK_REPORTS:
        report_title = report["name"]
        output = report["output"]
        output_dir = Path(report["path"]).parent
        image_paths = sorted(output_dir.glob(output)) if "*" in output else [output_dir / output]
        for image_path in image_paths:
            image_path = image_path.resolve()
            image_rel = image_path.relative_to(REPO_ROOT).as_posix()
            if image_rel in seen_paths:
                continue
            seen_paths.add(image_rel)
            title = stock_chart_title(report_title, image_path)
            section_id = stock_section_id(report_title)
            chart_id = slugify(f"{title}-{image_path.stem}")
            charts.append(
                {
                    "id": chart_id,
                    "title": title,
                    "section_id": section_id,
                    "section": section_name(section_id, STOCK_SECTION_ORDER),
                    "description": stock_description(report_title, image_path),
                    "image_path": image_rel,
                    "kind": "interactive",
                    "data_path": f"web/data/stocks/{chart_id}.json",
                    "order": order,
                    "image_exists": image_path.exists(),
                }
            )
            order += 1
    return charts


def build_market_summary():
    data = load_daily_price(BITCOIN_DATA_DIR)
    data = data[data["Price"] > 0].copy()
    data["ATH"] = data["Price"].cummax()
    data["Drawdown"] = (data["Price"] / data["ATH"] - 1) * 100
    latest = data.iloc[-1]
    return {
        "price": finite_or_none(latest["Price"]),
        "price_label": usd_label(float(latest["Price"])),
        "date": latest["Date"].strftime("%Y-%m-%d"),
        "date_label": latest["Date"].strftime("%b %d, %Y"),
        "drawdown": finite_or_none(latest["Drawdown"]),
        "drawdown_label": pct_label(float(latest["Drawdown"])),
    }


def bitcoin_hero(market):
    return {
        "kicker": "BTC/USD",
        "value_label": market["price_label"],
        "detail": f"{market['date_label']} · {market['drawdown_label']} from ATH",
    }


def stock_hero(charts):
    report_cards = [chart for chart in charts if chart["image_exists"]]
    interactive = [chart for chart in charts if chart["kind"] == "interactive"]
    return {
        "kicker": "Stocks",
        "value_label": f"{len(interactive)} charts",
        "detail": f"{len(report_cards)} generated report cards plus interactive stock views",
    }


def manifest_sections(charts, section_order):
    sections = [
        {"id": section_id, "name": name, "count": sum(1 for chart in charts if chart["section_id"] == section_id)}
        for section_id, name in section_order
    ]
    return [section for section in sections if section["count"] > 0]


def build_bitcoin_manifest():
    charts = build_chart_manifest()
    market = build_market_summary()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_version": 2,
        "asset_scope": "bitcoin",
        "sections": manifest_sections(charts, SECTION_ORDER),
        "charts": charts,
        "market": market,
        "hero": bitcoin_hero(market),
    }


def build_stock_manifest(charts=None):
    charts = charts or build_stock_chart_manifest()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_version": 2,
        "asset_scope": "stocks",
        "sections": manifest_sections(charts, STOCK_SECTION_ORDER),
        "charts": charts,
        "hero": stock_hero(charts),
    }


def generate_interactive_data() -> None:
    for chart_id, builder in INTERACTIVE_BUILDERS.items():
        payload = builder()
        write_json(BITCOIN_SITE_DATA_DIR / f"{chart_id}.json", payload)
        print(f"Generated interactive data: {chart_id}")


def generate_stock_interactive_data(charts) -> None:
    prime_stock_price_cache(charts)
    for chart in charts:
        if chart["kind"] != "interactive" or not chart["data_path"]:
            continue
        payload = build_stock_payload(chart)
        write_json(REPO_ROOT / chart["data_path"], payload)
        print(f"Generated stock interactive data: {chart['id']}")


def main() -> int:
    print("Generating static website data...")
    generate_interactive_data()
    stock_charts = build_stock_chart_manifest()
    generate_stock_interactive_data(stock_charts)
    bitcoin_manifest = build_bitcoin_manifest()
    stock_manifest = build_stock_manifest(stock_charts)
    write_json(WEB_DATA_DIR / "site-manifest.json", bitcoin_manifest)
    write_json(WEB_DATA_DIR / "bitcoin" / "site-manifest.json", bitcoin_manifest)
    write_json(WEB_DATA_DIR / "stocks" / "site-manifest.json", stock_manifest)
    print(f"Generated Bitcoin manifest with {len(bitcoin_manifest['charts'])} charts")
    print(f"Generated Stocks manifest with {len(stock_manifest['charts'])} charts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
