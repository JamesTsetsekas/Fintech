#!/usr/bin/env python3
"""Bitcoin fee pressure heatmap."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, dark_red_colormap, style_dark_axis


def load_block_fee_rates(data_dir):
    """Load block-level fee rates and month labels."""
    frames = []
    for csv_path in sorted(Path(data_dir).glob("block_data_*.csv")):
        frame = pd.read_csv(csv_path, usecols=["timestamp", "fees", "weight"])
        frame["Month"] = (
            pd.to_datetime(frame["timestamp"], unit="s", utc=True)
            .dt.tz_localize(None)
            .dt.to_period("M")
            .dt.to_timestamp()
        )
        frame["Fee_Rate_Sats_VByte"] = pd.to_numeric(frame["fees"], errors="coerce") / (
            pd.to_numeric(frame["weight"], errors="coerce") / 4
        )
        frames.append(frame[["Month", "Fee_Rate_Sats_VByte"]])

    blocks = pd.concat(frames, ignore_index=True)
    blocks = blocks.replace([np.inf, -np.inf], np.nan).dropna(subset=["Month", "Fee_Rate_Sats_VByte"])
    blocks = blocks[blocks["Fee_Rate_Sats_VByte"] > 0].copy()
    return blocks


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

blocks = load_block_fee_rates(data_dir)
blocks["Fee_Percentile"] = blocks["Fee_Rate_Sats_VByte"].rank(pct=True) * 100
percentile_edges = np.arange(0, 105, 5)
blocks["Percentile_Bucket"] = pd.cut(
    blocks["Fee_Percentile"],
    bins=percentile_edges,
    labels=False,
    include_lowest=True,
    right=False,
)
blocks = blocks.dropna(subset=["Percentile_Bucket"]).copy()
blocks["Percentile_Bucket"] = blocks["Percentile_Bucket"].astype(int)

months = pd.Index(sorted(blocks["Month"].unique()))
positions = np.arange(len(months))
bucket_count = len(percentile_edges) - 1
distribution = (
    blocks.groupby(["Percentile_Bucket", "Month"], observed=False)
    .size()
    .unstack(fill_value=0)
    .reindex(index=np.arange(bucket_count), columns=months, fill_value=0)
)
share_matrix = distribution.div(distribution.sum(axis=0).replace(0, np.nan), axis=1) * 100
heatmap = share_matrix.iloc[::-1].to_numpy(dtype=float)
percentile_labels = [f"{percentile_edges[index]}-{percentile_edges[index + 1]}" for index in range(bucket_count)][::-1]

monthly_median = blocks.groupby("Month")["Fee_Rate_Sats_VByte"].median().reindex(months)
monthly_hot_share = (blocks["Fee_Percentile"] >= 90).groupby(blocks["Month"]).mean().reindex(months) * 100
median_positive = monthly_median[monthly_median > 0]
median_lower = max(0.5, float(median_positive.min()) * 0.8)
median_upper = max(10.0, float(np.nanpercentile(monthly_median, 97)) * 1.5)
hot_share_upper = max(10.0, float(np.nanpercentile(monthly_hot_share, 99)) * 1.2)

fig = plt.figure(figsize=(20, 12))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(2, 1, height_ratios=[0.8, 1.4], hspace=0.14)
ax_top = fig.add_subplot(gs[0])
ax_heat = fig.add_subplot(gs[1], sharex=ax_top)
style_dark_axis(ax_top)
ax_heat.set_facecolor("black")
ax_heat.tick_params(colors="#D8D8D8")
for spine in ax_heat.spines.values():
    spine.set_color("#555555")

ax_top.plot(positions, monthly_median, color="#FFD166", linewidth=2.1, label="Median block fee rate")
ax_top.fill_between(positions, median_lower, monthly_median, color="#FFD166", alpha=0.08)
ax_top.set_yscale("log")
ax_top.set_ylim(median_lower, median_upper)
ax_top.set_xlim(-0.5, len(months) - 0.5)
ax_top.set_ylabel("sat/vB", color="white", fontsize=11, fontweight="bold")

ax_top_right = ax_top.twinx()
ax_top_right.plot(positions, monthly_hot_share, color="#FF6B6B", linewidth=1.7, alpha=0.9, label="Share of blocks in top 10% fee-rate history")
ax_top_right.tick_params(colors="#D8D8D8")
for spine in ax_top_right.spines.values():
    spine.set_color("#555555")
ax_top_right.set_ylim(0, hot_share_upper)
ax_top_right.set_ylabel("Top-decile blocks (%)", color="#D8D8D8", fontsize=10)

lines = ax_top.get_lines() + ax_top_right.get_lines()
labels = [line.get_label() for line in lines]
legend = ax_top.legend(lines, labels, loc="upper left", facecolor="black", edgecolor="#555555", labelcolor="white")
for text in legend.get_texts():
    text.set_color("white")

norm = mcolors.PowerNorm(gamma=0.75, vmin=0, vmax=max(1.0, np.nanpercentile(heatmap, 99)))
image = ax_heat.imshow(heatmap, aspect="auto", origin="upper", cmap=dark_red_colormap(), norm=norm)
ax_heat.set_xticks([index for index, month in enumerate(months) if month.month == 1 and month.year % 2 == 0])
ax_heat.set_xticklabels(
    [str(month.year) for month in months if month.month == 1 and month.year % 2 == 0],
    color="#D8D8D8",
    fontsize=10,
)
ax_heat.set_yticks(np.arange(0, bucket_count, 2))
ax_heat.set_yticklabels(percentile_labels[::2], color="#D8D8D8", fontsize=9)
ax_heat.set_ylabel("Global Fee-Rate Percentile Bucket", color="white", fontsize=11, fontweight="bold")
ax_heat.set_title("Monthly distribution of block fee-rate percentiles", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

cbar = fig.colorbar(image, ax=[ax_top, ax_heat], pad=0.012, fraction=0.028)
cbar.ax.tick_params(colors="#D8D8D8")
cbar.set_label("Share of monthly blocks in percentile bucket (%)", color="#D8D8D8", fontsize=10)

latest_month = months[-1]
fig.text(0.055, 0.965, "Bitcoin Fee Pressure Heatmap", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Block-space congestion map using repo-local block fee rates and global historical percentiles",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.69,
    0.965,
    f"Latest month median: {monthly_median.iloc[-1]:.2f} sat/vB",
    color="#FFD166",
    fontsize=14,
    fontweight="bold",
)
fig.text(
    0.69,
    0.938,
    f"{latest_month.strftime('%b %Y')} top-decile share: {monthly_hot_share.iloc[-1]:.1f}%",
    color="#C8C8C8",
    fontsize=10,
)
fig.text(
    0.055,
    0.05,
    "Percentile buckets are ranked across the full block history, so bright upper rows indicate months dominated by historically expensive block space.",
    color="#9E9E9E",
    fontsize=9,
)

output_path = script_dir / "fee_pressure_heatmap.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
