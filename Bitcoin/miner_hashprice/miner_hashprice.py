#!/usr/bin/env python3
"""Bitcoin miner revenue per hashrate chart."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, currency_label, load_market_frame, style_dark_axis


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_market_frame(data_dir)
data = data[(data["Price"] > 0) & (data["Estimated_Hashrate_EH_S"] > 0)].copy()
data["Hashprice_USD_PH_Day"] = data["Miner_Revenue_USD"] / (data["Estimated_Hashrate_EH_S"] * 1000)
data["Hashprice_30D"] = data["Hashprice_USD_PH_Day"].rolling(30, min_periods=7).mean()
data["Hashrate_30D"] = data["Estimated_Hashrate_EH_S"].rolling(30, min_periods=7).mean()
data["Revenue_30D"] = data["Miner_Revenue_USD"].rolling(30, min_periods=7).mean()
plot_data = data[data["Date"] >= data["Date"].max() - pd.DateOffset(years=8)].copy()
current = data.iloc[-1]

fig, axes = plt.subplots(3, 1, figsize=(18, 12), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1.15]})
fig.patch.set_facecolor("black")
for ax in axes:
    style_dark_axis(ax)

axes[0].plot(plot_data["Date"], plot_data["Hashrate_30D"], color="#00D1FF", linewidth=2)
axes[0].set_ylabel("Hashrate (EH/s)", color="white", fontsize=11, fontweight="bold")

axes[1].plot(plot_data["Date"], plot_data["Revenue_30D"], color="#FFD166", linewidth=2)
axes[1].set_ylabel("Miner Revenue / Day", color="white", fontsize=11, fontweight="bold")
axes[1].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: currency_label(x)))

axes[2].plot(plot_data["Date"], plot_data["Hashprice_USD_PH_Day"], color="#FF8C00", alpha=0.28, linewidth=1, label="Daily")
axes[2].plot(plot_data["Date"], plot_data["Hashprice_30D"], color="#FFB000", linewidth=2.4, label="30D avg")
axes[2].set_yscale("log")
axes[2].set_ylabel("USD / PH/s / day", color="white", fontsize=11, fontweight="bold")
axes[2].set_xlabel("Date", color="white", fontsize=11, fontweight="bold")
axes[2].legend(loc="upper right", facecolor="black", edgecolor="#555555", labelcolor="white")
axes[2].xaxis.set_major_locator(mdates.YearLocator())
axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

fig.text(0.055, 0.965, "Bitcoin Miner Hashprice", color="white", fontsize=24, fontweight="bold")
fig.text(0.055, 0.938, "Repo-local miner revenue divided by difficulty-implied network hashrate", color="#C8C8C8", fontsize=11)
fig.text(0.76, 0.965, f"Hashprice: USD {current['Hashprice_30D']:.2f}/PH/day", color="#FFB000", fontsize=15, fontweight="bold")
fig.text(0.76, 0.938, f"Hashrate: {current['Estimated_Hashrate_EH_S']:.0f} EH/s", color="#C8C8C8", fontsize=10)

output_path = script_dir / "miner_hashprice.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
