#!/usr/bin/env python3
"""Bitcoin return-volatility regime map."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, load_daily_price, style_dark_axis


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
data["Log_Return"] = np.log(data["Price"]).diff()
data["Annual_Return_1Y"] = data["Log_Return"].rolling(365, min_periods=180).mean() * 365 * 100
data["Vol_1Y"] = data["Log_Return"].rolling(365, min_periods=180).std() * np.sqrt(365) * 100
data["Sharpe_Proxy_1Y"] = (data["Annual_Return_1Y"] / data["Vol_1Y"]).replace([np.inf, -np.inf], np.nan)

monthly = (
    data.set_index("Date")
    .resample("MS")
    .last()
    .dropna(subset=["Annual_Return_1Y", "Vol_1Y", "Sharpe_Proxy_1Y", "Epoch"])
    .copy()
)
monthly = monthly[monthly.index >= pd.Timestamp("2011-01-01")]
current = monthly.iloc[-1]

epoch_colors = {
    2: "#5DADE2",
    3: "#7ED957",
    4: "#FFD166",
    5: "#FF8C00",
}
y_limit = min(max(np.nanpercentile(np.abs(monthly["Annual_Return_1Y"]), 98) * 1.18, 250), 1200)
x_limit = min(max(np.nanpercentile(monthly["Vol_1Y"], 99) * 1.15, 120), 260)

fig, ax = plt.subplots(figsize=(16, 10))
fig.patch.set_facecolor("black")
style_dark_axis(ax)

zone_split = 50
for x0, y0, width, height, color, alpha in [
    (0, 0, zone_split, y_limit, "#0B7A3B", 0.12),
    (zone_split, 0, x_limit - zone_split, y_limit, "#FF8C00", 0.08),
    (0, -y_limit, zone_split, y_limit, "#4F1D1D", 0.12),
    (zone_split, -y_limit, x_limit - zone_split, y_limit, "#7A1F1F", 0.18),
]:
    ax.add_patch(
        mpatches.Rectangle(
            (x0, y0),
            width,
            height,
            facecolor=color,
            edgecolor="none",
            alpha=alpha,
            zorder=0,
        )
    )
ax.axhline(0, color="#D8D8D8", linestyle="--", linewidth=1.0, alpha=0.7)
ax.axvline(zone_split, color="#D8D8D8", linestyle=":", linewidth=1.0, alpha=0.5)

for sharpe in [0.5, 1.0, 2.0]:
    x_values = np.linspace(0, x_limit, 400)
    y_values = sharpe * x_values
    ax.plot(x_values, y_values, color="white", alpha=0.18, linewidth=1, linestyle="--")
    ax.text(x_limit * 0.98, sharpe * x_limit * 0.98, f"Sharpe {sharpe:.1f}", color="#8F8F8F", fontsize=8, ha="right", va="bottom")

for epoch in sorted(monthly["Epoch"].dropna().astype(int).unique()):
    epoch_slice = monthly[monthly["Epoch"] == epoch]
    color = epoch_colors.get(epoch, "#AAAAAA")
    ax.plot(epoch_slice["Vol_1Y"], epoch_slice["Annual_Return_1Y"], color=color, alpha=0.35, linewidth=1.2)
    ax.scatter(
        epoch_slice["Vol_1Y"],
        epoch_slice["Annual_Return_1Y"],
        s=28,
        color=color,
        alpha=0.55,
        edgecolors="none",
        label=f"E{epoch}",
    )

recent = monthly.tail(24)
ax.plot(recent["Vol_1Y"], recent["Annual_Return_1Y"], color="white", linewidth=2.2, alpha=0.85, zorder=8)
ax.scatter(recent["Vol_1Y"], recent["Annual_Return_1Y"], color="white", s=22, alpha=0.9, zorder=9)
ax.scatter(
    [current["Vol_1Y"]],
    [current["Annual_Return_1Y"]],
    color="#FF4D4D",
    edgecolors="white",
    linewidths=1.3,
    s=150,
    marker="*",
    zorder=10,
)
ax.annotate(
    f"Current\nVol {current['Vol_1Y']:.1f}%\nReturn {current['Annual_Return_1Y']:.1f}%",
    xy=(current["Vol_1Y"], current["Annual_Return_1Y"]),
    xytext=(current["Vol_1Y"] + 12, current["Annual_Return_1Y"] + 60),
    color="white",
    fontsize=10,
    ha="left",
    va="bottom",
    arrowprops={"arrowstyle": "->", "color": "white", "lw": 1.0},
)

ax.set_xlim(0, x_limit)
ax.set_ylim(-y_limit, y_limit)
ax.set_xlabel("1Y Realized Volatility", color="white", fontsize=12, fontweight="bold")
ax.set_ylabel("1Y Annualized Return", color="white", fontsize=12, fontweight="bold")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0f}%"))

legend = ax.legend(loc="upper right", framealpha=0.35, facecolor="black", edgecolor="#555555", labelcolor="white", ncol=4)
for text in legend.get_texts():
    text.set_color("white")

fig.text(0.055, 0.965, "Bitcoin Return-Volatility Map", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Monthly 1Y risk/return positions by halving epoch, with recent trajectory and Sharpe-proxy guide lines",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(0.77, 0.965, f"Sharpe proxy: {current['Sharpe_Proxy_1Y']:.2f}", color="#00D1FF", fontsize=16, fontweight="bold")
fig.text(
    0.77,
    0.938,
    f"Epoch E{int(current['Epoch'])} | last 24 months shown in white",
    color="#C8C8C8",
    fontsize=10,
)

output_path = script_dir / "return_volatility_map.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
