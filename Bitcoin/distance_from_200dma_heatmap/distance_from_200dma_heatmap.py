#!/usr/bin/env python3
"""Bitcoin distance-from-200DMA heatmap."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, dark_red_colormap, load_daily_price, style_dark_axis


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
data["DMA_200"] = data["Price"].rolling(200, min_periods=180).mean()
data["Distance_200D_Pct"] = (data["Price"] / data["DMA_200"] - 1) * 100
data = data.dropna(subset=["Distance_200D_Pct"]).copy()
data["Month"] = data["Date"].dt.to_period("M").dt.to_timestamp()

distance_edges = np.array([-80, -60, -40, -30, -20, -10, 0, 10, 20, 40, 60, 80, 120, 160, 220, 320], dtype=float)
distance_centers = (distance_edges[:-1] + distance_edges[1:]) / 2
data["Distance_Bucket"] = pd.cut(
    data["Distance_200D_Pct"].clip(distance_edges[0], distance_edges[-1] - 1e-9),
    bins=distance_edges,
    labels=False,
    include_lowest=True,
    right=False,
)
data["Distance_Bucket"] = data["Distance_Bucket"].astype(int)

months = pd.Index(sorted(data["Month"].unique()))
positions = np.arange(len(months))
distribution = (
    data.groupby(["Distance_Bucket", "Month"], observed=False)
    .size()
    .unstack(fill_value=0)
    .reindex(index=np.arange(len(distance_centers)), columns=months, fill_value=0)
)
share_matrix = distribution.div(distribution.sum(axis=0).replace(0, np.nan), axis=1) * 100
monthly_mean = data.groupby("Month")["Distance_200D_Pct"].mean().reindex(months)
monthly_mode = np.nanargmax(np.nan_to_num(share_matrix.to_numpy(dtype=float), nan=-np.inf), axis=0)

fig = plt.figure(figsize=(20, 12))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(2, 1, height_ratios=[0.78, 1.35], hspace=0.12)
ax_line = fig.add_subplot(gs[0])
ax_heat = fig.add_subplot(gs[1], sharex=ax_line)
style_dark_axis(ax_line)
ax_heat.set_facecolor("black")
ax_heat.tick_params(colors="#D8D8D8")
for spine in ax_heat.spines.values():
    spine.set_color("#555555")

ax_line.axhspan(distance_edges[0], -20, color="#0B7A3B", alpha=0.18)
ax_line.axhspan(40, distance_edges[-1], color="#B51D1A", alpha=0.16)
ax_line.axhline(0, color="#D8D8D8", linestyle="--", linewidth=1.1, alpha=0.7)
ax_line.axhline(-20, color="#00D26A", linestyle="--", linewidth=1.0, alpha=0.8)
ax_line.axhline(40, color="#FF6B6B", linestyle="--", linewidth=1.0, alpha=0.8)
ax_line.plot(positions, monthly_mean, color="#FFD166", linewidth=2.1)
ax_line.set_xlim(-0.5, len(months) - 0.5)
ax_line.set_ylabel("% vs 200D MA", color="white", fontsize=11, fontweight="bold")

norm = mcolors.PowerNorm(gamma=0.75, vmin=0, vmax=max(1.0, np.nanpercentile(share_matrix.to_numpy(dtype=float), 99)))
image = ax_heat.imshow(share_matrix.to_numpy(dtype=float), aspect="auto", origin="lower", cmap=dark_red_colormap(), norm=norm)
ax_heat.plot(positions, monthly_mode, color="#FFD166", linewidth=1.2, alpha=0.92)
ax_heat.set_yticks(np.arange(0, len(distance_centers), 2))
ax_heat.set_yticklabels([f"{distance_centers[index]:.0f}%" for index in range(0, len(distance_centers), 2)], color="#D8D8D8", fontsize=9)
ax_heat.set_xticks([index for index, month in enumerate(months) if month.month == 1 and month.year % 2 == 0])
ax_heat.set_xticklabels(
    [str(month.year) for month in months if month.month == 1 and month.year % 2 == 0],
    color="#D8D8D8",
    fontsize=10,
)
ax_heat.set_ylabel("Distance Bucket", color="white", fontsize=11, fontweight="bold")
ax_heat.set_title("Monthly distribution of daily distance from the 200-day moving average", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

cbar = fig.colorbar(image, ax=[ax_line, ax_heat], pad=0.012, fraction=0.028)
cbar.ax.tick_params(colors="#D8D8D8")
cbar.set_label("Share of monthly trading days in bucket (%)", color="#D8D8D8", fontsize=10)

current_distance = data["Distance_200D_Pct"].iloc[-1]
trailing_cold_days = int((data["Distance_200D_Pct"].tail(365) < -20).sum())
trailing_hot_days = int((data["Distance_200D_Pct"].tail(365) > 40).sum())

fig.text(0.055, 0.965, "Bitcoin Distance From 200DMA Heatmap", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Regime map showing how often BTC trades above or below its 200-day moving average",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.7,
    0.965,
    f"Current distance: {current_distance:+.1f}%",
    color="#FFD166" if current_distance >= 0 else "#00D26A",
    fontsize=15,
    fontweight="bold",
)
fig.text(
    0.7,
    0.938,
    f"Trailing year: {trailing_cold_days} cold-zone days | {trailing_hot_days} overheated-zone days",
    color="#C8C8C8",
    fontsize=10,
)
fig.text(
    0.055,
    0.05,
    "Gold path marks the modal distance bucket for each month. Thresholds at -20% and +40% separate deep discount and overheated conditions.",
    color="#9E9E9E",
    fontsize=9,
)

output_path = script_dir / "distance_from_200dma_heatmap.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
