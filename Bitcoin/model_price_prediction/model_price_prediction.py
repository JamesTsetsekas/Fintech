#!/usr/bin/env python3
"""
Bitcoin Price Prediction Models

Shows historical Bitcoin price with a concise overview of:
- Stock-to-Flow
- Power Law

Detailed Rainbow/HPR and Power Law band views live in their dedicated charts.
"""

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from model_projection import (
    apply_price_models,
    build_projection_frame,
    load_daily_fees,
    load_price_history,
)


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
HALVING_DATES = [item["date"] for item in HALVING_INFO]


def format_price(x, _position):
    """Format log-scale USD ticks compactly."""
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M" if x < 10_000_000 else f"{int(x / 1_000_000)}M"
    if x >= 1_000:
        return f"{x / 1_000:.0f}k"
    if x >= 1:
        return f"{int(x)}"
    return f"{x:.2f}"


def main():
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data" / "bitcoin_csv_data"
    dataset_path = data_dir / "daily_price.csv"
    end_date = datetime(2035, 1, 1)

    print(f"Loading price data from {dataset_path}")
    price_history = load_price_history(dataset_path)
    print(f"Loaded {len(price_history)} daily price/supply records")

    print("Aggregating block fees for Stock-to-Income...")
    daily_fees = load_daily_fees(data_dir)
    print(f"Aggregated fees for {len(daily_fees)} days")

    print("Building model projection frame...")
    projection_df = build_projection_frame(price_history, daily_fees, end_date, HALVING_INFO)
    projection_df, coefficients = apply_price_models(projection_df)

    for model_name, (slope, intercept) in coefficients.items():
        print(f"{model_name}: slope={slope:.4f}, intercept={intercept:.4f}")

    historical_data = projection_df[projection_df["Price"].notna() & (projection_df["Price"] > 0)]
    x_min = historical_data["Date"].min()
    valid_model_values = projection_df[["Price", "S2F", "Power_Law"]].to_numpy()
    y_max = np.nanmax(valid_model_values)
    y_upper = max(20_000_000, y_max * 1.15)

    print("Creating chart...")
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(16, 10))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")

    ax.plot(
        historical_data["Date"],
        historical_data["Price"],
        color="#FFA500",
        linewidth=2,
        label="Price",
        zorder=10,
    )
    ax.plot(
        projection_df["Date"],
        projection_df["S2F"],
        color="#00BFFF",
        linewidth=2,
        label="Stock-to-Flow (scarcity)",
        alpha=0.9,
        zorder=5,
    )
    ax.plot(
        projection_df["Date"],
        projection_df["Power_Law"],
        color="#00FF00",
        linewidth=2,
        label="Power Law (time)",
        alpha=0.9,
        zorder=5,
    )

    for halving_date in HALVING_DATES:
        if x_min <= halving_date <= end_date:
            ax.axvline(halving_date, color="white", linestyle="--", alpha=0.3, linewidth=1, zorder=1)

    ax.set_yscale("log")
    ax.set_ylim(1, y_upper)
    ax.set_yticks([1, 10, 100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000])
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_price))
    ax.tick_params(axis="y", colors="lightgray", labelsize=11)

    ax.set_xlim(x_min, end_date)
    ax.xaxis.set_major_locator(mdates.YearLocator(base=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", colors="gray", labelsize=10)

    ax.set_xlabel("", color="lightgray")
    ax.set_ylabel("Price (USD)", color="lightgray", fontsize=13, fontweight="bold")
    ax.set_title("Bitcoin Price Prediction Models", color="white", fontsize=18, fontweight="bold", pad=20)

    ax.grid(True, which="major", linestyle="-", alpha=0.15, color="gray")
    ax.grid(True, which="minor", linestyle="--", alpha=0.05, color="gray")

    legend = ax.legend(loc="upper left", framealpha=0.3, fontsize=11, facecolor="black", edgecolor="gray")
    for text in legend.get_texts():
        text.set_color("white")

    fig.text(
        0.5,
        0.018,
        "Overview chart intentionally shows one scarcity model and one time-based model. See Rainbow and Power Law charts for band detail.",
        ha="center",
        va="bottom",
        color="gray",
        fontsize=9,
    )
    plt.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.08)

    output_path = script_dir / "model_price_prediction.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="black", edgecolor="none", pad_inches=0.1)
    plt.close(fig)
    print(f"Chart saved to: {output_path}")


if __name__ == "__main__":
    main()
