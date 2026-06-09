#!/usr/bin/env python3
"""Bitcoin halving-cycle compass chart."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import HALVINGS, bitcoin_data_dir, current_halving_epoch, load_daily_price


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
data = data.dropna(subset=["Block_Height"]).sort_values("Date").reset_index(drop=True)

era_colors = {
    2: "#5DADE2",
    3: "#7ED957",
    4: "#FFD166",
    5: "#FF8C00",
}
era_summaries = []

fig = plt.figure(figsize=(14, 14))
fig.patch.set_facecolor("black")
ax = fig.add_subplot(111, projection="polar")
ax.set_facecolor("black")
ax.set_theta_zero_location("N")
ax.set_theta_direction(-1)
ax.set_rscale("log")
ax.set_rlim(0.5, 120)
ax.grid(color="white", alpha=0.12, linestyle="--", linewidth=0.8)
ax.spines["polar"].set_color("#555555")

ax.set_thetagrids([0, 90, 180, 270], labels=["Halving", "25%", "50%", "75%"])
for label in ax.get_xticklabels():
    label.set_color("#D8D8D8")
    label.set_fontsize(11)

radial_ticks = [0.5, 1, 2, 5, 10, 20, 50, 100]
radial_labels = ["0.5x", "1x", "2x", "5x", "10x", "20x", "50x", "100x"]
ax.set_rticks(radial_ticks)
ax.set_yticklabels(radial_labels, color="#D8D8D8", fontsize=10)
ax.set_rlabel_position(22.5)

for halving in HALVINGS[1:5]:
    epoch = int(halving["epoch"])
    start_block = halving["block"]
    end_block = start_block + 210_000
    era = data[(data["Block_Height"] >= start_block) & (data["Block_Height"] < end_block)].copy()
    if era.empty:
        continue

    start_price = float(era.iloc[0]["Price"])
    era["Progress"] = ((era["Block_Height"] - start_block) / (end_block - start_block)).clip(0, 1)
    era["Theta"] = era["Progress"] * 2 * np.pi
    era["Multiple"] = (era["Price"] / start_price).clip(lower=0.5)

    peak = era.loc[era["Multiple"].idxmax()]
    current = era.iloc[-1]
    color = era_colors.get(epoch, "#AAAAAA")
    linewidth = 2.8 if epoch == 5 else 2.0
    alpha = 0.95 if epoch == 5 else 0.8

    ax.plot(
        era["Theta"],
        era["Multiple"],
        color=color,
        linewidth=linewidth,
        alpha=alpha,
        label=f"E{epoch} ({era.iloc[0]['Date'].year}) peak {peak['Multiple']:.1f}x",
    )
    ax.scatter([peak["Theta"]], [peak["Multiple"]], color=color, s=34, alpha=0.9, zorder=6)

    if epoch == 5:
        ax.scatter(
            [current["Theta"]],
            [current["Multiple"]],
            color="white",
            edgecolors=color,
            linewidths=1.5,
            s=120,
            zorder=8,
        )
        ax.annotate(
            f"Current\n{current['Multiple']:.2f}x",
            xy=(current["Theta"], current["Multiple"]),
            xytext=(current["Theta"] + 0.22, current["Multiple"] * 1.25),
            color="white",
            fontsize=10,
            ha="left",
            va="center",
            arrowprops={"arrowstyle": "->", "color": "white", "lw": 1.0},
        )

    era_summaries.append(
        f"E{epoch}: start {era.iloc[0]['Date'].strftime('%Y-%m-%d')} | peak {peak['Multiple']:.1f}x | now {current['Multiple']:.2f}x"
    )

current_row = data.iloc[-1]
current_epoch, next_halving_block, progress = current_halving_epoch(current_row["Block_Height"])
blocks_remaining = int(next_halving_block - current_row["Block_Height"])

fig.text(0.5, 0.965, "Bitcoin Halving Phase Compass", ha="center", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.5,
    0.938,
    "One full rotation equals one halving epoch; radius is price multiple since that halving started",
    ha="center",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.14,
    0.07,
    f"Current cycle: E{int(current_epoch['epoch'])} | progress {progress * 100:.1f}% | blocks to next halving {blocks_remaining:,}",
    color="#C8C8C8",
    fontsize=10,
)
fig.text(
    0.14,
    0.045,
    " | ".join(era_summaries),
    color="#8F8F8F",
    fontsize=8.5,
)

legend = ax.legend(
    loc="lower center",
    bbox_to_anchor=(0.5, -0.16),
    ncol=2,
    framealpha=0.35,
    facecolor="black",
    edgecolor="#555555",
    fontsize=10,
)
for text in legend.get_texts():
    text.set_color("white")

output_path = script_dir / "halving_phase_compass.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
