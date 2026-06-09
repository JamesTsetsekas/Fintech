#!/usr/bin/env python3
"""Bitcoin fee pressure chart."""

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
data = data[data["Price"] > 0].copy()
data["Fees_BTC_30D"] = data["Fees_BTC"].rolling(30, min_periods=7).mean()
data["Fee_Share_30D"] = data["Fee_Share_Pct"].rolling(30, min_periods=7).mean()
data["Fee_Rate_30D"] = data["Fee_Rate_Sats_VByte"].rolling(30, min_periods=7).mean()
plot_data = data[data["Date"] >= data["Date"].max() - pd.DateOffset(years=6)].copy()
current = data.iloc[-1]

fig, axes = plt.subplots(3, 1, figsize=(18, 12), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1]})
fig.patch.set_facecolor("black")
for ax in axes:
    style_dark_axis(ax)

axes[0].plot(plot_data["Date"], plot_data["Fees_BTC"], color="#FF8C00", alpha=0.25, linewidth=1, label="Daily fees")
axes[0].plot(plot_data["Date"], plot_data["Fees_BTC_30D"], color="#FFD166", linewidth=2.2, label="30D avg")
axes[0].set_ylabel("Fees (BTC/day)", color="white", fontsize=11, fontweight="bold")
axes[0].legend(loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white")

axes[1].axhspan(0, 2, color="#0B7A3B", alpha=0.18)
axes[1].axhspan(10, max(12, np.nanpercentile(plot_data["Fee_Share_Pct"], 99) * 1.1), color="#B51D1A", alpha=0.16)
axes[1].plot(plot_data["Date"], plot_data["Fee_Share_Pct"], color="#5DADE2", alpha=0.25, linewidth=1, label="Daily")
axes[1].plot(plot_data["Date"], plot_data["Fee_Share_30D"], color="#00D1FF", linewidth=2.2, label="30D avg")
axes[1].set_ylabel("Fees / Miner Revenue (%)", color="white", fontsize=11, fontweight="bold")
axes[1].legend(loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white")

axes[2].plot(plot_data["Date"], plot_data["Fee_Rate_Sats_VByte"], color="#FF4D4D", alpha=0.20, linewidth=1, label="Daily")
axes[2].plot(plot_data["Date"], plot_data["Fee_Rate_30D"], color="#FF6B6B", linewidth=2.2, label="30D avg")
axes[2].set_ylabel("Fee Rate (sat/vB)", color="white", fontsize=11, fontweight="bold")
axes[2].set_xlabel("Date", color="white", fontsize=11, fontweight="bold")
axes[2].legend(loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white")
axes[2].xaxis.set_major_locator(mdates.YearLocator())
axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

fig.text(0.055, 0.965, "Bitcoin Fee Pressure", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Fees, fee share of miner revenue, and block-space fee rate from repo block CSVs",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.76,
    0.965,
    f"Fees: {current['Fees_BTC']:.2f} BTC ({currency_label(current['Fee_Revenue_USD'])})",
    color="#FFD166",
    fontsize=13,
    fontweight="bold",
)
fig.text(0.76, 0.938, f"Fee share: {current['Fee_Share_Pct']:.2f}% | Fee rate: {current['Fee_Rate_Sats_VByte']:.1f} sat/vB", color="#C8C8C8", fontsize=10)

output_path = script_dir / "fee_pressure.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
