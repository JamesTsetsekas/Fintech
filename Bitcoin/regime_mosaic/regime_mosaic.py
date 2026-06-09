#!/usr/bin/env python3
"""Bitcoin regime mosaic chart."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, currency_label, load_market_frame, style_dark_axis


def encode_states(values, bins):
    """Return integer state codes using right-open bins."""
    return np.digitize(values, bins[1:-1], right=False)


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_market_frame(data_dir)
data = data[data["Price"] > 0].copy()
data["ATH"] = data["Price"].cummax()
data["Drawdown_Pct"] = (data["Price"] / data["ATH"] - 1) * 100
data["DMA_200"] = data["Price"].rolling(200, min_periods=120).mean()
data["Price_vs_200D"] = (data["Price"] / data["DMA_200"] - 1) * 100
data["Mayer_Multiple"] = data["Price"] / data["DMA_200"]
data["Log_Return"] = np.log(data["Price"]).diff()
data["Vol_30D"] = data["Log_Return"].rolling(30, min_periods=20).std() * np.sqrt(365) * 100
data["Vol_Percentile"] = data["Vol_30D"].rank(pct=True) * 100
data["Revenue_365D_MA"] = data["Miner_Revenue_USD"].rolling(365, min_periods=180).mean()
data["Puell_30D"] = (data["Miner_Revenue_USD"] / data["Revenue_365D_MA"]).rolling(30, min_periods=10).mean()

monthly = (
    data.set_index("Date")
    .resample("MS")
    .last()
    .dropna(subset=["DMA_200", "Mayer_Multiple", "Puell_30D", "Vol_Percentile", "Drawdown_Pct"])
)
monthly = monthly[monthly.index >= pd.Timestamp("2011-01-01")].copy()
positions = np.arange(len(monthly))

rows = [
    {
        "name": "Trend vs 200D",
        "values": monthly["Price_vs_200D"],
        "bins": [-np.inf, -20, 0, 50, np.inf],
        "labels": ["Deep discount", "Below trend", "Above trend", "Euphoric"],
        "colors": ["#5A0002", "#FF8C00", "#00A878", "#00D26A"],
    },
    {
        "name": "Mayer Multiple",
        "values": monthly["Mayer_Multiple"],
        "bins": [-np.inf, 0.8, 1.0, 2.4, np.inf],
        "labels": ["Historically cold", "Discount", "Fair value", "Overheated"],
        "colors": ["#0B7A3B", "#2E86C1", "#FFD166", "#B51D1A"],
    },
    {
        "name": "Puell Multiple",
        "values": monthly["Puell_30D"],
        "bins": [-np.inf, 0.5, 1.0, 2.5, np.inf],
        "labels": ["Miner stress", "Suppressed", "Balanced", "Hot"],
        "colors": ["#0B7A3B", "#2E86C1", "#FFD166", "#B51D1A"],
    },
    {
        "name": "Drawdown",
        "values": monthly["Drawdown_Pct"],
        "bins": [-np.inf, -60, -30, -10, np.inf],
        "labels": ["Deep bear", "Bear market", "Correction", "Near ATH"],
        "colors": ["#5A0002", "#B51D1A", "#FF8C00", "#00D26A"],
    },
    {
        "name": "Volatility",
        "values": monthly["Vol_Percentile"],
        "bins": [-np.inf, 25, 50, 75, np.inf],
        "labels": ["Quiet", "Balanced", "Active", "Extreme"],
        "colors": ["#0B7A3B", "#2E86C1", "#FF8C00", "#B51D1A"],
    },
]

rgba = np.zeros((len(rows), len(monthly), 4))
current_labels = []
for row_index, row in enumerate(rows):
    codes = encode_states(row["values"], row["bins"])
    row["codes"] = codes
    current_labels.append(row["labels"][int(codes[-1])])
    for code, color in enumerate(row["colors"]):
        rgba[row_index, codes == code] = mcolors.to_rgba(color)

fig = plt.figure(figsize=(19, 10))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(2, 1, height_ratios=[1.1, 0.82], hspace=0.08)
ax_price = fig.add_subplot(gs[0])
ax_mosaic = fig.add_subplot(gs[1], sharex=ax_price)
style_dark_axis(ax_price)
ax_mosaic.set_facecolor("black")

ax_price.plot(positions, monthly["Price"], color="white", linewidth=1.7)
ax_price.set_yscale("log")
ax_price.set_ylabel("BTC Price (USD)", color="white", fontsize=11, fontweight="bold")
ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: currency_label(x)))
ax_price.fill_between(positions, monthly["Price"].min(), monthly["Price"], color="#FFD166", alpha=0.08)
ax_price.axvline(len(monthly) - 1, color="#FFFFFF", alpha=0.25, linewidth=1)

ax_mosaic.imshow(rgba, aspect="auto", interpolation="nearest", origin="upper")
ax_mosaic.set_yticks(np.arange(len(rows)))
ax_mosaic.set_yticklabels([row["name"] for row in rows], color="#D8D8D8", fontsize=11, fontweight="bold")
ax_mosaic.set_xticks([i for i, dt in enumerate(monthly.index) if dt.month == 1 and dt.year % 2 == 0])
ax_mosaic.set_xticklabels(
    [str(dt.year) for dt in monthly.index if dt.month == 1 and dt.year % 2 == 0],
    color="#D8D8D8",
    fontsize=10,
)
ax_mosaic.axvline(len(monthly) - 1, color="#FFFFFF", alpha=0.35, linewidth=1)
for spine in ax_mosaic.spines.values():
    spine.set_color("#555555")

for idx, current_label in enumerate(current_labels):
    ax_mosaic.text(
        1.01,
        1 - ((idx + 0.5) / len(rows)),
        current_label,
        transform=ax_mosaic.transAxes,
        color="white",
        fontsize=10,
        va="center",
        ha="left",
    )

legend_handles = [
    mpatches.Patch(color="#0B7A3B", label="Cold / quiet"),
    mpatches.Patch(color="#2E86C1", label="Below trend / balanced"),
    mpatches.Patch(color="#FFD166", label="Fair / active"),
    mpatches.Patch(color="#B51D1A", label="Hot / bear stress"),
]
legend = fig.legend(
    handles=legend_handles,
    loc="lower center",
    bbox_to_anchor=(0.5, 0.015),
    ncol=4,
    framealpha=0.35,
    facecolor="black",
    edgecolor="#555555",
    fontsize=10,
)
for text in legend.get_texts():
    text.set_color("white")

current_price_label = currency_label(monthly["Price"].iloc[-1]).replace("$", "USD ")
fig.text(0.055, 0.965, "Bitcoin Regime Mosaic", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Monthly state map for trend, Mayer, Puell, drawdown, and realized volatility",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(0.78, 0.965, f"Current price: {current_price_label}", color="#FFD166", fontsize=15, fontweight="bold")
fig.text(
    0.78,
    0.938,
    " | ".join(f"{row['name'].split()[0]}: {label}" for row, label in zip(rows, current_labels)),
    color="#C8C8C8",
    fontsize=9.5,
)
plt.subplots_adjust(left=0.12, right=0.88, top=0.88, bottom=0.09)

output_path = script_dir / "regime_mosaic.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
