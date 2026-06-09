#!/usr/bin/env python3
"""Bitcoin volatility regimes chart."""

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
data["Return"] = np.log(data["Price"]).diff()
data["Vol_30D"] = data["Return"].rolling(30, min_periods=20).std() * np.sqrt(365) * 100
data["Vol_90D"] = data["Return"].rolling(90, min_periods=45).std() * np.sqrt(365) * 100
data["Vol_365D"] = data["Return"].rolling(365, min_periods=180).std() * np.sqrt(365) * 100
data["Vol_Percentile"] = data["Vol_30D"].rank(pct=True) * 100
data = data.dropna(subset=["Vol_30D"])
current = data.iloc[-1]

fig, (ax_price, ax_vol) = plt.subplots(2, 1, figsize=(18, 11), sharex=True, gridspec_kw={"height_ratios": [1, 1.2]})
fig.patch.set_facecolor("black")
style_dark_axis(ax_price)
style_dark_axis(ax_vol)

ax_price.plot(data["Date"], data["Price"], color="white", linewidth=1.4)
ax_price.set_yscale("log")
ax_price.set_ylabel("BTC Price (USD)", color="white", fontsize=11, fontweight="bold")
ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: currency_label(x)))

low = np.nanpercentile(data["Vol_30D"], 25)
high = np.nanpercentile(data["Vol_30D"], 75)
extreme = np.nanpercentile(data["Vol_30D"], 90)
ax_vol.axhspan(0, low, color="#0B7A3B", alpha=0.18, label="Low-volatility regime")
ax_vol.axhspan(high, extreme, color="#FF8C00", alpha=0.16, label="High-volatility regime")
ax_vol.axhspan(extreme, max(data["Vol_30D"].max() * 1.05, extreme + 1), color="#B51D1A", alpha=0.16, label="Extreme regime")
ax_vol.plot(data["Date"], data["Vol_30D"], color="#00D1FF", linewidth=1.7, label="30D annualized")
ax_vol.plot(data["Date"], data["Vol_90D"], color="#FFD166", linewidth=1.5, label="90D annualized")
ax_vol.plot(data["Date"], data["Vol_365D"], color="#FF6B6B", linewidth=1.4, label="365D annualized")
ax_vol.axhline(low, color="#00D26A", linestyle="--", linewidth=1)
ax_vol.axhline(high, color="#FF8C00", linestyle="--", linewidth=1)
ax_vol.set_ylim(0, min(max(data["Vol_30D"].max() * 1.05, 120), 260))
ax_vol.set_ylabel("Annualized Volatility", color="white", fontsize=11, fontweight="bold")
ax_vol.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax_vol.xaxis.set_major_locator(mdates.YearLocator(2))
ax_vol.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax_vol.legend(loc="upper right", facecolor="black", edgecolor="#555555", labelcolor="white", ncol=2)

fig.text(0.055, 0.955, "Bitcoin Volatility Regimes", color="white", fontsize=24, fontweight="bold")
fig.text(0.055, 0.928, "Rolling realized volatility with percentile-based regime bands", color="#C8C8C8", fontsize=11)
fig.text(0.77, 0.955, f"30D vol: {current['Vol_30D']:.1f}%", color="#00D1FF", fontsize=16, fontweight="bold")
fig.text(0.77, 0.928, f"Historical percentile: {current['Vol_Percentile']:.0f}%", color="#C8C8C8", fontsize=11)

output_path = script_dir / "volatility_regimes.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
