#!/usr/bin/env python3
"""Bitcoin seasonality heatmap."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, dark_diverging_colormap, load_daily_price, load_intraday_price


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

intraday = load_intraday_price(data_dir)
intraday = intraday.dropna(subset=["Log_Return"]).copy()
intraday["Hour"] = intraday["DateTime"].dt.hour
intraday["Weekday"] = intraday["DateTime"].dt.weekday
intraday["Return_Bps"] = intraday["Log_Return"] * 10_000

daily = load_daily_price(data_dir)
daily = daily[daily["Price"] > 0].copy()
daily["Return_Pct"] = daily["Price"].pct_change() * 100
daily = daily.dropna(subset=["Return_Pct"]).copy()
daily["Month"] = daily["Date"].dt.month
daily["Weekday"] = daily["Date"].dt.weekday
daily["Up_Day"] = (daily["Return_Pct"] > 0).astype(float) * 100

weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

hourly_return = (
    intraday.groupby(["Hour", "Weekday"])["Return_Bps"]
    .mean()
    .unstack()
    .reindex(index=np.arange(24), columns=np.arange(7))
)
month_weekday_hit = (
    daily.groupby(["Month", "Weekday"])["Up_Day"]
    .mean()
    .unstack()
    .reindex(index=np.arange(1, 13), columns=np.arange(7))
)

return_values = hourly_return.to_numpy(dtype=float)
return_abs = np.nanpercentile(np.abs(return_values), 98)
return_norm = mcolors.TwoSlopeNorm(vmin=-return_abs, vcenter=0.0, vmax=return_abs)
hit_values = month_weekday_hit.to_numpy(dtype=float)
hit_abs = max(abs(50 - np.nanpercentile(hit_values, 2)), abs(np.nanpercentile(hit_values, 98) - 50))
hit_norm = mcolors.TwoSlopeNorm(vmin=50 - hit_abs, vcenter=50.0, vmax=50 + hit_abs)

fig, axes = plt.subplots(2, 1, figsize=(16, 12), gridspec_kw={"height_ratios": [1.25, 0.9], "hspace": 0.22})
fig.patch.set_facecolor("black")

for ax in axes:
    ax.set_facecolor("black")
    ax.tick_params(colors="#D8D8D8")
    for spine in ax.spines.values():
        spine.set_color("#555555")

heatmap_cmap = dark_diverging_colormap()
top_image = axes[0].imshow(hourly_return.to_numpy(dtype=float), aspect="auto", origin="lower", cmap=heatmap_cmap, norm=return_norm)
axes[0].set_xticks(np.arange(7))
axes[0].set_xticklabels(weekday_names, color="#D8D8D8", fontsize=11, fontweight="bold")
axes[0].set_yticks(np.arange(0, 24, 3))
axes[0].set_yticklabels([f"{hour:02d}:00" for hour in range(0, 24, 3)], color="#D8D8D8", fontsize=10)
axes[0].set_ylabel("UTC Hour", color="white", fontsize=11, fontweight="bold")
axes[0].set_title("Mean 10-minute return by weekday and hour", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

bottom_image = axes[1].imshow(month_weekday_hit.to_numpy(dtype=float), aspect="auto", origin="lower", cmap=heatmap_cmap, norm=hit_norm)
axes[1].set_xticks(np.arange(7))
axes[1].set_xticklabels(weekday_names, color="#D8D8D8", fontsize=11, fontweight="bold")
axes[1].set_yticks(np.arange(12))
axes[1].set_yticklabels(month_names, color="#D8D8D8", fontsize=10)
axes[1].set_ylabel("Month", color="white", fontsize=11, fontweight="bold")
axes[1].set_title("Positive daily return rate by month and weekday", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

top_cbar = fig.colorbar(top_image, ax=axes[0], pad=0.012, fraction=0.03)
top_cbar.ax.tick_params(colors="#D8D8D8")
top_cbar.set_label("Mean 10-minute return (bps)", color="#D8D8D8", fontsize=10)

bottom_cbar = fig.colorbar(bottom_image, ax=axes[1], pad=0.012, fraction=0.03)
bottom_cbar.ax.tick_params(colors="#D8D8D8")
bottom_cbar.set_label("Positive-return days (%)", color="#D8D8D8", fontsize=10)

best_hour, best_weekday = np.unravel_index(np.nanargmax(return_values), return_values.shape)
best_month, best_hit_weekday = np.unravel_index(np.nanargmax(hit_values), hit_values.shape)

fig.text(0.055, 0.965, "Bitcoin Seasonality Heatmap", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Return seasonality across the 24/7 trading week and across the calendar year",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.68,
    0.965,
    f"Strongest intraday edge: {weekday_names[best_weekday]} {best_hour:02d}:00",
    color="#FFD166",
    fontsize=14,
    fontweight="bold",
)
fig.text(
    0.68,
    0.938,
    f"Best hit-rate cell: {month_names[best_month]} {weekday_names[best_hit_weekday]}",
    color="#C8C8C8",
    fontsize=10,
)

output_path = script_dir / "seasonality_heatmap.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
