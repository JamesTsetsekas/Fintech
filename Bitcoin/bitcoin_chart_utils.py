"""Shared helpers for repo-local Bitcoin chart scripts."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


SATOSHIS_PER_BTC = 100_000_000
GENESIS_DATE = pd.Timestamp("2009-01-03")
BLOCKS_PER_HALVING = 210_000
SECONDS_PER_BLOCK_TARGET = 600
DARK_RED_HEATMAP_COLORS = ["#050608", "#180708", "#3a0b0d", "#7f1d1d", "#b51d1a", "#ff5f63"]
DARK_DIVERGING_HEATMAP_COLORS = ["#7f1d1d", "#2b0b0d", "#050608", "#0b1f17", "#166534"]

HALVINGS = [
    {"epoch": 1, "block": 0, "date": pd.Timestamp("2009-01-03"), "subsidy": 50.0},
    {"epoch": 2, "block": 210_000, "date": pd.Timestamp("2012-11-28"), "subsidy": 25.0},
    {"epoch": 3, "block": 420_000, "date": pd.Timestamp("2016-07-09"), "subsidy": 12.5},
    {"epoch": 4, "block": 630_000, "date": pd.Timestamp("2020-05-11"), "subsidy": 6.25},
    {"epoch": 5, "block": 840_000, "date": pd.Timestamp("2024-04-20"), "subsidy": 3.125},
    {"epoch": 6, "block": 1_050_000, "date": pd.Timestamp("2028-04-20"), "subsidy": 1.5625},
]


def bitcoin_data_dir(script_file):
    """Return the repo Bitcoin CSV data directory for a chart script."""
    return Path(script_file).resolve().parents[1] / "data" / "bitcoin_csv_data"


def load_daily_price(data_dir):
    """Load daily Bitcoin price and supply history with derived issuance fields."""
    data = pd.read_csv(Path(data_dir) / "daily_price.csv")
    data["Date"] = pd.to_datetime(data["date"], format="%m/%d/%y")
    data["Price"] = pd.to_numeric(data["price"], errors="coerce")
    data["Daily_High"] = pd.to_numeric(data["daily_high"], errors="coerce")
    data["Block_Height"] = pd.to_numeric(data["block_height"], errors="coerce")
    data["Epoch"] = pd.to_numeric(data["epoch"], errors="coerce")
    data["Subsidy_BTC"] = pd.to_numeric(data["subsidy"], errors="coerce")
    data["Supply_BTC"] = pd.to_numeric(data["supply"], errors="coerce")
    data["Market_Cap"] = pd.to_numeric(data["market_cap"], errors="coerce")
    data = data.dropna(subset=["Date", "Price", "Block_Height", "Supply_BTC"])
    data = data.sort_values("Date").reset_index(drop=True)

    data["Blocks_Mined"] = data["Block_Height"].diff().fillna(0).clip(lower=0)
    data["Daily_Issuance_BTC"] = data["Supply_BTC"].diff().fillna(0).clip(lower=0)
    return data


def load_intraday_price(data_dir):
    """Load repo-local 10-minute BTC/USD history with log returns."""
    data = pd.read_csv(Path(data_dir) / "btcusd_10m_prices.csv")
    data["DateTime"] = pd.to_datetime(data["timestamp"], unit="s", utc=True)
    data["Price"] = pd.to_numeric(data["price"], errors="coerce")
    data = data.dropna(subset=["DateTime", "Price"])
    data = data[data["Price"] > 0].sort_values("DateTime").reset_index(drop=True)
    data["Date"] = data["DateTime"].dt.floor("D").dt.tz_localize(None)
    data["Log_Return"] = np.log(data["Price"]).diff()
    return data[["DateTime", "Date", "Price", "Log_Return"]]


def load_daily_block_metrics(data_dir):
    """Aggregate block CSVs into daily fee, revenue, difficulty, and activity metrics."""
    data_dir = Path(data_dir)
    cache_path = data_dir / "daily_block_metrics_cache.csv"
    block_csvs = sorted(data_dir.glob("block_data_*.csv"))
    if cache_path.exists() and block_csvs:
        cache_mtime = cache_path.stat().st_mtime
        if all(csv_path.stat().st_mtime <= cache_mtime for csv_path in block_csvs):
            cached = pd.read_csv(cache_path)
            cached["Date"] = pd.to_datetime(cached["Date"])
            return cached

    frames = []
    usecols = [
        "block_height",
        "timestamp",
        "difficulty",
        "size",
        "weight",
        "reward",
        "subsidy",
        "fees",
        "tx_count",
    ]

    for csv_path in block_csvs:
        block_data = pd.read_csv(csv_path, usecols=usecols)
        block_data["Date"] = (
            pd.to_datetime(block_data["timestamp"], unit="s", utc=True)
            .dt.floor("D")
            .dt.tz_localize(None)
        )
        for column in ["difficulty", "size", "weight", "reward", "subsidy", "fees", "tx_count"]:
            block_data[column] = pd.to_numeric(block_data[column], errors="coerce").fillna(0)
        frames.append(block_data)

    if not frames:
        return pd.DataFrame(
            columns=[
                "Date",
                "Fees_BTC",
                "Subsidy_BTC_Blocks",
                "Reward_BTC",
                "Tx_Count",
                "Block_Count",
                "Total_Weight",
                "Total_Size",
                "Avg_Difficulty",
                "Last_Block_Height",
                "Fee_Rate_Sats_VByte",
                "Avg_Block_Weight",
                "Estimated_Hashrate_EH_S",
            ]
        )

    combined = pd.concat(frames, ignore_index=True)
    grouped = (
        combined.groupby("Date", as_index=False)
        .agg(
            Fees_Sats=("fees", "sum"),
            Subsidy_Sats=("subsidy", "sum"),
            Reward_Sats=("reward", "sum"),
            Tx_Count=("tx_count", "sum"),
            Block_Count=("block_height", "count"),
            Total_Weight=("weight", "sum"),
            Total_Size=("size", "sum"),
            Avg_Difficulty=("difficulty", "mean"),
            Last_Block_Height=("block_height", "max"),
        )
        .sort_values("Date")
        .reset_index(drop=True)
    )
    grouped["Fees_BTC"] = grouped["Fees_Sats"] / SATOSHIS_PER_BTC
    grouped["Subsidy_BTC_Blocks"] = grouped["Subsidy_Sats"] / SATOSHIS_PER_BTC
    grouped["Reward_BTC"] = grouped["Reward_Sats"] / SATOSHIS_PER_BTC
    grouped["Fee_Rate_Sats_VByte"] = grouped["Fees_Sats"] / (grouped["Total_Weight"] / 4)
    grouped["Fee_Rate_Sats_VByte"] = grouped["Fee_Rate_Sats_VByte"].replace([np.inf, -np.inf], np.nan)
    grouped["Avg_Block_Weight"] = grouped["Total_Weight"] / grouped["Block_Count"]
    grouped["Estimated_Hashrate_EH_S"] = (
        grouped["Avg_Difficulty"] * (2**32) / SECONDS_PER_BLOCK_TARGET / 1e18
    )
    tmp_cache_path = cache_path.with_name(f"{cache_path.stem}.{os.getpid()}.tmp")
    grouped.to_csv(tmp_cache_path, index=False)
    tmp_cache_path.replace(cache_path)
    return grouped


def load_market_frame(data_dir, include_block_metrics=True):
    """Merge daily price history with optional daily block metrics."""
    price = load_daily_price(data_dir)
    if not include_block_metrics:
        return price

    block_metrics = load_daily_block_metrics(data_dir)
    data = price.merge(block_metrics, on="Date", how="left")
    data["Fees_BTC"] = data["Fees_BTC"].fillna(0)
    fallback_reward = data["Daily_Issuance_BTC"] + data["Fees_BTC"]
    data["Reward_BTC"] = data["Reward_BTC"].fillna(fallback_reward)
    data["Miner_Revenue_USD"] = data["Reward_BTC"] * data["Price"]
    data["Fee_Revenue_USD"] = data["Fees_BTC"] * data["Price"]
    data["Fee_Share_Pct"] = np.where(
        data["Reward_BTC"] > 0,
        data["Fees_BTC"] / data["Reward_BTC"] * 100,
        np.nan,
    )
    return data


def current_halving_epoch(block_height):
    """Return current halving metadata for a block height."""
    active = HALVINGS[0]
    for halving in HALVINGS:
        if block_height >= halving["block"]:
            active = halving
        else:
            break
    next_block = active["block"] + BLOCKS_PER_HALVING
    progress = (block_height - active["block"]) / BLOCKS_PER_HALVING
    return active, next_block, max(0.0, min(progress, 1.0))


def dark_figure(width=18, height=10):
    """Create a dark matplotlib figure."""
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(width, height))
    fig.patch.set_facecolor("black")
    return fig


def style_dark_axis(ax, grid=True):
    """Apply consistent dark-axis styling."""
    ax.set_facecolor("black")
    ax.tick_params(colors="#D8D8D8", labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#555555")
    if grid:
        ax.grid(True, which="major", color="white", alpha=0.12, linestyle="--", linewidth=0.7)
        ax.grid(True, which="minor", color="white", alpha=0.05, linestyle=":", linewidth=0.5)


def dark_red_colormap(name="dark_red_heatmap"):
    """Return a black-to-red heatmap colormap with no white/yellow high end."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(name, DARK_RED_HEATMAP_COLORS, N=256)


def dark_diverging_colormap(name="dark_diverging_heatmap"):
    """Return a red-black-green diverging colormap with a dark midpoint."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(name, DARK_DIVERGING_HEATMAP_COLORS, N=256)


def currency_label(value):
    """Compact USD label."""
    if not np.isfinite(value):
        return "n/a"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}k"
    if abs(value) >= 1:
        return f"${value:,.0f}"
    if abs(value) >= 0.01:
        return f"${value:.2f}"
    if abs(value) > 0:
        return f"${value:.4f}"
    return f"${value:,.0f}"
