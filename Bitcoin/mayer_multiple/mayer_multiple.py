#!/usr/bin/env python3
"""Bitcoin Mayer Multiple chart."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, currency_label, load_daily_price, style_dark_axis


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
data["DMA_200"] = data["Price"].rolling(200, min_periods=180).mean()
data["Mayer_Multiple"] = data["Price"] / data["DMA_200"]
plot_data = data.dropna(subset=["Mayer_Multiple"]).copy()
current = plot_data.iloc[-1]

fig, (ax_price, ax_mayer) = plt.subplots(
    2,
    1,
    figsize=(18, 11),
    sharex=True,
    gridspec_kw={"height_ratios": [1.0, 1.25], "hspace": 0.08},
)
fig.patch.set_facecolor("black")
style_dark_axis(ax_price)
style_dark_axis(ax_mayer)

ax_price.plot(plot_data["Date"], plot_data["Price"], color="white", linewidth=1.35, label="BTC price")
ax_price.plot(plot_data["Date"], plot_data["DMA_200"], color="#FF8C00", linewidth=1.55, label="200D MA")
ax_price.set_yscale("log")
ax_price.set_ylabel("BTC Price (USD)", color="white", fontsize=11, fontweight="bold")
ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: currency_label(x)))
ax_price.legend(loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white")

upper_limit = max(3.2, min(np.nanpercentile(plot_data["Mayer_Multiple"], 99.5) * 1.15, 8.0))
ax_mayer.axhspan(0, 0.8, color="#0B7A3B", alpha=0.28, label="Historically cold (<0.8)")
ax_mayer.axhspan(0.8, 1.0, color="#2E86C1", alpha=0.13, label="Below trend")
ax_mayer.axhspan(2.4, upper_limit, color="#B51D1A", alpha=0.22, label="Historically overheated (>2.4)")
ax_mayer.axhline(1.0, color="#D8D8D8", linestyle="--", linewidth=1.1, alpha=0.7)
ax_mayer.axhline(2.4, color="#FF4D4D", linestyle="--", linewidth=1.1, alpha=0.8)
ax_mayer.axhline(0.8, color="#00D26A", linestyle="--", linewidth=1.1, alpha=0.8)
ax_mayer.plot(
    plot_data["Date"],
    plot_data["Mayer_Multiple"],
    color="#FFD166",
    linewidth=1.75,
    label="Mayer Multiple",
)
ax_mayer.fill_between(
    plot_data["Date"],
    1,
    plot_data["Mayer_Multiple"],
    where=plot_data["Mayer_Multiple"] >= 1,
    color="#FF8C00",
    alpha=0.18,
    interpolate=True,
)
ax_mayer.fill_between(
    plot_data["Date"],
    plot_data["Mayer_Multiple"],
    1,
    where=plot_data["Mayer_Multiple"] < 1,
    color="#00D26A",
    alpha=0.18,
    interpolate=True,
)
ax_mayer.set_ylim(0, upper_limit)
ax_mayer.set_ylabel("Price / 200D MA", color="white", fontsize=11, fontweight="bold")
ax_mayer.xaxis.set_major_locator(mdates.YearLocator(2))
ax_mayer.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax_mayer.legend(loc="upper right", facecolor="black", edgecolor="#555555", labelcolor="white", ncol=2)

status_color = "#00D26A" if current["Mayer_Multiple"] < 0.8 else "#FF4D4D" if current["Mayer_Multiple"] > 2.4 else "#FFD166"
days_below_trend = int((plot_data["Mayer_Multiple"] < 1).tail(365).sum())
current_price = currency_label(current["Price"]).replace("$", "USD ")
current_200d = currency_label(current["DMA_200"]).replace("$", "USD ")
fig.text(0.055, 0.955, "Bitcoin Mayer Multiple", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.928,
    "BTC price divided by the 200-day moving average; classic cycle zones at 0.8, 1.0, and 2.4",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(0.77, 0.955, f"Current: {current['Mayer_Multiple']:.2f}", color=status_color, fontsize=18, fontweight="bold")
fig.text(
    0.77,
    0.928,
    f"Price: {current_price} | 200D: {current_200d}",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.055,
    0.045,
    f"Days below 200D trend in trailing year: {days_below_trend} of 365",
    color="#9E9E9E",
    fontsize=9,
)

output_path = script_dir / "mayer_multiple.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
