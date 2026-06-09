#!/usr/bin/env python3
"""Bitcoin Puell Multiple chart."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, currency_label, load_market_frame, style_dark_axis


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_market_frame(data_dir)
data = data[(data["Price"] > 0) & (data["Miner_Revenue_USD"] > 0)].copy()
data["Revenue_365D_MA"] = data["Miner_Revenue_USD"].rolling(365, min_periods=180).mean()
data["Puell_Multiple"] = data["Miner_Revenue_USD"] / data["Revenue_365D_MA"]
data["Puell_30D"] = data["Puell_Multiple"].rolling(30, min_periods=10).mean()
data = data.dropna(subset=["Puell_Multiple"])

current = data.iloc[-1]

fig, (ax_price, ax_puell) = plt.subplots(
    2, 1, figsize=(18, 11), sharex=True, gridspec_kw={"height_ratios": [1.0, 1.25]}
)
fig.patch.set_facecolor("black")
style_dark_axis(ax_price)
style_dark_axis(ax_puell)

ax_price.plot(data["Date"], data["Price"], color="white", linewidth=1.4, label="BTC Price")
ax_price.set_yscale("log")
ax_price.set_ylabel("BTC Price (USD)", color="white", fontsize=11, fontweight="bold")
ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: currency_label(x)))
ax_price.legend(loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white")

ax_puell.axhspan(0, 0.5, color="#0B7A3B", alpha=0.28, label="Accumulation Zone (<0.5)")
ax_puell.axhspan(4.0, max(6, data["Puell_Multiple"].max() * 1.05), color="#B51D1A", alpha=0.22, label="Overheated Zone (>4)")
ax_puell.axhline(1.0, color="#CCCCCC", linestyle="--", linewidth=1, alpha=0.65)
ax_puell.axhline(0.5, color="#00D26A", linestyle="--", linewidth=1, alpha=0.75)
ax_puell.axhline(4.0, color="#FF4D4D", linestyle="--", linewidth=1, alpha=0.75)
ax_puell.plot(data["Date"], data["Puell_Multiple"], color="#F5A623", linewidth=1.3, alpha=0.45, label="Daily Puell")
ax_puell.plot(data["Date"], data["Puell_30D"], color="#FFD166", linewidth=2.4, label="30D Average")

ax_puell.set_ylim(0, max(5.2, np.nanpercentile(data["Puell_Multiple"], 99.5) * 1.12))
ax_puell.set_ylabel("Puell Multiple", color="white", fontsize=11, fontweight="bold")
ax_puell.xaxis.set_major_locator(mdates.YearLocator(2))
ax_puell.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax_puell.legend(loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white", ncol=2)

status_color = "#00D26A" if current["Puell_30D"] < 0.5 else "#FF4D4D" if current["Puell_30D"] > 4 else "#FFD166"
fig.text(0.055, 0.955, "Bitcoin Puell Multiple", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.925,
    "Miner revenue in USD divided by its 365-day moving average",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(0.78, 0.955, f"Current 30D: {current['Puell_30D']:.2f}", color=status_color, fontsize=18, fontweight="bold")
fig.text(0.78, 0.925, f"Daily miner revenue: {currency_label(current['Miner_Revenue_USD'])}", color="#C8C8C8", fontsize=11)

output_path = script_dir / "puell_multiple.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
