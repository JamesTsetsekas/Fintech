#!/usr/bin/env python3
"""Bitcoin intraday volatility heatmap."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, dark_red_colormap, load_intraday_price


def annualized_volatility(series):
    """Return annualized volatility from 10-minute log returns."""
    return series.std() * np.sqrt(365 * 24 * 6) * 100


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

intraday = load_intraday_price(data_dir)
intraday = intraday.dropna(subset=["Log_Return"]).copy()
intraday["Hour"] = intraday["DateTime"].dt.hour
intraday["Weekday"] = intraday["DateTime"].dt.weekday
intraday["Month"] = intraday["DateTime"].dt.month

weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

weekday_hour = (
    intraday.groupby(["Hour", "Weekday"])["Log_Return"]
    .apply(annualized_volatility)
    .unstack()
    .reindex(index=np.arange(24), columns=np.arange(7))
)
month_hour = (
    intraday.groupby(["Hour", "Month"])["Log_Return"]
    .apply(annualized_volatility)
    .unstack()
    .reindex(index=np.arange(24), columns=np.arange(1, 13))
)

all_values = np.concatenate([weekday_hour.to_numpy().ravel(), month_hour.to_numpy().ravel()])
finite_values = all_values[np.isfinite(all_values)]
norm = mcolors.PowerNorm(gamma=0.8, vmin=float(np.nanmin(finite_values)), vmax=float(np.nanpercentile(finite_values, 99)))

fig, axes = plt.subplots(2, 1, figsize=(18, 13), gridspec_kw={"height_ratios": [1.0, 1.2], "hspace": 0.2})
fig.patch.set_facecolor("black")

for ax in axes:
    ax.set_facecolor("black")
    ax.tick_params(colors="#D8D8D8")
    for spine in ax.spines.values():
        spine.set_color("#555555")

heatmap_cmap = dark_red_colormap()
im_top = axes[0].imshow(weekday_hour.to_numpy(), aspect="auto", origin="lower", cmap=heatmap_cmap, norm=norm)
axes[0].set_xticks(np.arange(7))
axes[0].set_xticklabels(weekday_names, color="#D8D8D8", fontsize=11, fontweight="bold")
axes[0].set_yticks(np.arange(0, 24, 3))
axes[0].set_yticklabels([f"{hour:02d}:00" for hour in range(0, 24, 3)], color="#D8D8D8", fontsize=10)
axes[0].set_ylabel("UTC Hour", color="white", fontsize=11, fontweight="bold")
axes[0].set_title("Annualized realized volatility by weekday and hour", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

im_bottom = axes[1].imshow(month_hour.to_numpy(), aspect="auto", origin="lower", cmap=heatmap_cmap, norm=norm)
axes[1].set_xticks(np.arange(12))
axes[1].set_xticklabels(month_names, color="#D8D8D8", fontsize=10)
axes[1].set_yticks(np.arange(0, 24, 3))
axes[1].set_yticklabels([f"{hour:02d}:00" for hour in range(0, 24, 3)], color="#D8D8D8", fontsize=10)
axes[1].set_ylabel("UTC Hour", color="white", fontsize=11, fontweight="bold")
axes[1].set_title("Annualized realized volatility by month and hour", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

cbar = fig.colorbar(im_bottom, ax=axes, pad=0.014, fraction=0.028)
cbar.ax.tick_params(colors="#D8D8D8")
cbar.set_label("Annualized volatility (%) from 10-minute log returns", color="#D8D8D8", fontsize=10)

weekday_peak_hour, weekday_peak_day = np.unravel_index(np.nanargmax(weekday_hour.to_numpy()), weekday_hour.shape)
month_peak_hour, month_peak = np.unravel_index(np.nanargmax(month_hour.to_numpy()), month_hour.shape)
weekday_trough_hour, weekday_trough_day = np.unravel_index(np.nanargmin(weekday_hour.to_numpy()), weekday_hour.shape)

fig.text(0.055, 0.965, "Bitcoin Intraday Volatility Heatmap", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "24/7 realized volatility map from repo-local 10-minute BTC/USD prices",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.7,
    0.965,
    f"Hottest weekday-hour: {weekday_names[weekday_peak_day]} {weekday_peak_hour:02d}:00",
    color="#FFD166",
    fontsize=14,
    fontweight="bold",
)
fig.text(
    0.7,
    0.938,
    f"Hottest month-hour: {month_names[month_peak]} {month_peak_hour:02d}:00 | Quietest weekday-hour: {weekday_names[weekday_trough_day]} {weekday_trough_hour:02d}:00",
    color="#C8C8C8",
    fontsize=10,
)

output_path = script_dir / "intraday_volatility_heatmap.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
