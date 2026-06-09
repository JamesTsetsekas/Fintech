#!/usr/bin/env python3
"""Bitcoin halving-era ROI heatmap."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import HALVINGS, bitcoin_data_dir, dark_diverging_colormap, load_daily_price


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
current_date = data["Date"].max()

months = np.arange(0, 49)
rows = []
row_labels = []
start_prices = []
latest_values = []

for halving in HALVINGS[1:5]:
    start_block = halving["block"]
    next_block = start_block + 210_000
    epoch = int(halving["epoch"])

    cycle = data[(data["Block_Height"] >= start_block) & (data["Block_Height"] < next_block)].copy()
    if cycle.empty:
        continue

    start_row = cycle.iloc[0]
    start_date = start_row["Date"]
    start_price = start_row["Price"]
    values = []

    for month in months:
        target_date = start_date + pd.DateOffset(months=int(month))
        if target_date > current_date:
            values.append(np.nan)
            continue
        eligible = cycle[cycle["Date"] <= target_date]
        if eligible.empty:
            values.append(np.nan)
            continue
        price = eligible.iloc[-1]["Price"]
        values.append((price / start_price - 1) * 100)

    rows.append(values)
    row_labels.append(f"E{epoch} ({start_date.year})")
    start_prices.append(start_price)
    latest_values.append(pd.Series(values).dropna().iloc[-1])

heatmap = np.array(rows, dtype=float)

fig, ax = plt.subplots(figsize=(20, 8))
fig.patch.set_facecolor("black")
ax.set_facecolor("black")

finite = heatmap[np.isfinite(heatmap)]
vmax = max(500, np.nanpercentile(finite, 95)) if finite.size else 500
norm = mcolors.SymLogNorm(linthresh=50, linscale=1.0, vmin=-90, vmax=vmax, base=10)
im = ax.imshow(heatmap, aspect="auto", cmap=dark_diverging_colormap(), norm=norm)

ax.set_xticks(np.arange(0, len(months), 3))
ax.set_xticklabels([f"{m}m" for m in months[::3]], color="#D8D8D8", fontsize=10)
ax.set_yticks(np.arange(len(row_labels)))
ax.set_yticklabels(row_labels, color="#D8D8D8", fontsize=12, fontweight="bold")
ax.tick_params(colors="#D8D8D8")
for spine in ax.spines.values():
    spine.set_color("#555555")

for row_idx in range(heatmap.shape[0]):
    for col_idx in range(0, heatmap.shape[1] - 1, 6):
        value = heatmap[row_idx, col_idx]
        if not np.isfinite(value):
            continue
        label = f"{value:+.0f}%"
        ax.text(col_idx, row_idx, label, ha="center", va="center", color="#F8FAFC", fontsize=8, fontweight="bold")

cbar = fig.colorbar(im, ax=ax, pad=0.015)
cbar.ax.tick_params(colors="#D8D8D8")
cbar.set_label("ROI since halving (%) - symmetric log scale", color="#D8D8D8", fontsize=10)

ax.set_xlabel("Months Since Halving", color="white", fontsize=12, fontweight="bold")
ax.set_title("Bitcoin Halving Era ROI Heatmap", color="white", fontsize=24, fontweight="bold", pad=28)

summary_parts = [
    f"{label}: start USD {start:,.0f}, latest {latest:+.0f}%"
    for label, start, latest in zip(row_labels, start_prices, latest_values)
]
fig.text(0.08, 0.91, " | ".join(summary_parts), color="#C8C8C8", fontsize=10)
fig.text(0.08, 0.055, "Each row starts at that epoch's first daily close after the halving block.", color="#9E9E9E", fontsize=9)

output_path = script_dir / "halving_era_roi_heatmap.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
