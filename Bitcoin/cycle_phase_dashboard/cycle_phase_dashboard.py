#!/usr/bin/env python3
"""Bitcoin cycle phase dashboard."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import (
    bitcoin_data_dir,
    currency_label,
    current_halving_epoch,
    load_market_frame,
    style_dark_axis,
)


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_market_frame(data_dir)
data = data[data["Price"] > 0].copy()
data["ATH"] = data["Price"].cummax()
data["Drawdown_Pct"] = (data["Price"] / data["ATH"] - 1) * 100
data["Return"] = np.log(data["Price"]).diff()
data["Vol_30D"] = data["Return"].rolling(30, min_periods=20).std() * np.sqrt(365) * 100
data["Vol_Percentile"] = data["Vol_30D"].rank(pct=True) * 100
data["Revenue_365D_MA"] = data["Miner_Revenue_USD"].rolling(365, min_periods=180).mean()
data["Puell_30D"] = (data["Miner_Revenue_USD"] / data["Revenue_365D_MA"]).rolling(30, min_periods=10).mean()
data["Fee_Share_30D"] = data["Fee_Share_Pct"].rolling(30, min_periods=7).mean()
data["DMA_200"] = data["Price"].rolling(200, min_periods=100).mean()
data["Price_vs_200D"] = (data["Price"] / data["DMA_200"] - 1) * 100

current = data.iloc[-1]
epoch, next_halving_block, halving_progress = current_halving_epoch(current["Block_Height"])
recent = data[data["Date"] >= data["Date"].max() - pd.DateOffset(years=4)].copy()

fig = plt.figure(figsize=(18, 12))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(3, 4, height_ratios=[0.72, 1.1, 1.0], hspace=0.33, wspace=0.24)

card_axes = [fig.add_subplot(gs[0, i]) for i in range(4)]
for ax in card_axes:
    ax.set_facecolor("#101010")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#333333")

cards = [
    ("Price", currency_label(current["Price"]), f"vs 200D: {current['Price_vs_200D']:+.1f}%", "#FFD166"),
    ("ATH Drawdown", f"{current['Drawdown_Pct']:.1f}%", f"ATH: {currency_label(current['ATH'])}", "#FF6B6B" if current["Drawdown_Pct"] < -20 else "#00D26A"),
    ("Halving Progress", f"{halving_progress * 100:.1f}%", f"Epoch E{int(epoch['epoch'])} -> {next_halving_block:,}", "#00D1FF"),
    ("Puell / Fees", f"{current['Puell_30D']:.2f}", f"Fee share: {current['Fee_Share_30D']:.2f}%", "#FF8C00"),
]

for ax, (title, value, subtitle, color) in zip(card_axes, cards):
    ax.text(0.05, 0.78, title, transform=ax.transAxes, color="#9E9E9E", fontsize=11, fontweight="bold")
    ax.text(0.05, 0.38, value, transform=ax.transAxes, color=color, fontsize=24, fontweight="bold")
    ax.text(0.05, 0.12, subtitle, transform=ax.transAxes, color="#D8D8D8", fontsize=10)

ax_price = fig.add_subplot(gs[1, :2])
ax_drawdown = fig.add_subplot(gs[1, 2:])
ax_metrics = fig.add_subplot(gs[2, :2])
ax_progress = fig.add_subplot(gs[2, 2:])
for ax in [ax_price, ax_drawdown, ax_metrics, ax_progress]:
    style_dark_axis(ax)

ax_price.plot(recent["Date"], recent["Price"], color="white", linewidth=1.6, label="BTC")
ax_price.plot(recent["Date"], recent["DMA_200"], color="#FF8C00", linewidth=1.6, label="200D MA")
ax_price.set_yscale("log")
ax_price.set_title("Price vs 200D Trend", color="white", fontsize=13, fontweight="bold")
ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: currency_label(x)))
ax_price.legend(loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white")

ax_drawdown.fill_between(recent["Date"], recent["Drawdown_Pct"], 0, color="#B51D1A", alpha=0.35)
ax_drawdown.plot(recent["Date"], recent["Drawdown_Pct"], color="#FF6B6B", linewidth=1.6)
ax_drawdown.set_title("Drawdown From ATH", color="white", fontsize=13, fontweight="bold")
ax_drawdown.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))

ax_metrics.plot(recent["Date"], recent["Puell_30D"], color="#FFD166", linewidth=1.8, label="Puell 30D")
ax_metrics.axhline(1, color="#CCCCCC", linestyle="--", linewidth=1, alpha=0.6)
ax_metrics_twin = ax_metrics.twinx()
style_dark_axis(ax_metrics_twin, grid=False)
ax_metrics_twin.plot(recent["Date"], recent["Vol_Percentile"], color="#00D1FF", linewidth=1.4, alpha=0.85, label="Vol percentile")
ax_metrics.set_title("Cycle Temperature", color="white", fontsize=13, fontweight="bold")
ax_metrics.set_ylabel("Puell", color="#FFD166")
ax_metrics_twin.set_ylabel("Vol percentile", color="#00D1FF")
ax_metrics_twin.set_ylim(0, 100)

progress_labels = ["Halving", "Volatility", "Drawdown", "Puell", "Fee Share"]
progress_values = [
    halving_progress * 100,
    current["Vol_Percentile"],
    min(abs(current["Drawdown_Pct"]), 100),
    min(current["Puell_30D"] / 4 * 100, 100),
    min(current["Fee_Share_30D"] / 10 * 100, 100),
]
progress_colors = ["#00D1FF", "#FFD166", "#FF6B6B", "#FF8C00", "#7ED957"]
y = np.arange(len(progress_labels))
ax_progress.barh(y, progress_values, color=progress_colors, alpha=0.85)
ax_progress.set_yticks(y)
ax_progress.set_yticklabels(progress_labels, color="#D8D8D8")
ax_progress.set_xlim(0, 100)
ax_progress.set_title("Normalized Phase Gauges", color="white", fontsize=13, fontweight="bold")
ax_progress.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax_progress.invert_yaxis()
for idx, value in enumerate(progress_values):
    ax_progress.text(min(value + 2, 96), idx, f"{value:.0f}%", color="white", va="center", fontsize=9)

for ax in [ax_price, ax_drawdown, ax_metrics]:
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

fig.text(0.055, 0.965, "Bitcoin Cycle Phase Dashboard", color="white", fontsize=24, fontweight="bold")
fig.text(0.055, 0.938, "Repo-local snapshot combining price trend, drawdown, halving progress, Puell, fees, and volatility", color="#C8C8C8", fontsize=11)

output_path = script_dir / "cycle_phase_dashboard.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
