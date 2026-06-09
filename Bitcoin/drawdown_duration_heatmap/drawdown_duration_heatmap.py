#!/usr/bin/env python3
"""Bitcoin drawdown duration heatmap."""

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


def find_drawdown_episodes(frame):
    """Return peak-to-recovery drawdown episodes."""
    episodes = []
    peak_date = frame.iloc[0]["Date"]
    peak_price = frame.iloc[0]["Price"]
    in_drawdown = False
    start_date = None
    trough_date = peak_date
    trough_price = peak_price

    for _, row in frame.iterrows():
        price = row["Price"]
        date = row["Date"]
        if price >= peak_price:
            if in_drawdown:
                episodes.append(
                    {
                        "Peak_Date": peak_date,
                        "Peak_Price": peak_price,
                        "Start_Date": start_date,
                        "Trough_Date": trough_date,
                        "Trough_Price": trough_price,
                        "Recovery_Date": date,
                        "Max_Drawdown_Pct": (trough_price / peak_price - 1) * 100,
                        "Days_To_Recover": (date - peak_date).days,
                        "Recovered": True,
                    }
                )
                in_drawdown = False
            peak_date = date
            peak_price = price
            trough_date = date
            trough_price = price
        elif price < peak_price:
            if not in_drawdown:
                in_drawdown = True
                start_date = date
                trough_date = date
                trough_price = price
            elif price < trough_price:
                trough_date = date
                trough_price = price

    if in_drawdown:
        episodes.append(
            {
                "Peak_Date": peak_date,
                "Peak_Price": peak_price,
                "Start_Date": start_date,
                "Trough_Date": trough_date,
                "Trough_Price": trough_price,
                "Recovery_Date": pd.NaT,
                "Max_Drawdown_Pct": (trough_price / peak_price - 1) * 100,
                "Days_To_Recover": (frame.iloc[-1]["Date"] - peak_date).days,
                "Recovered": False,
            }
        )
    return pd.DataFrame(episodes)


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
episodes = find_drawdown_episodes(data)
episodes["Peak_Year"] = episodes["Peak_Date"].dt.year
episodes = episodes[
    (episodes["Max_Drawdown_Pct"] <= -20)
    | (episodes["Days_To_Recover"] >= 180)
    | (~episodes["Recovered"])
].copy()
episodes = (
    episodes.sort_values(["Peak_Year", "Max_Drawdown_Pct"])
    .groupby("Peak_Year", as_index=False)
    .first()
    .sort_values("Peak_Date")
    .reset_index(drop=True)
)

depth_edges = np.arange(-90, 5, 5)
depth_centers = (depth_edges[:-1] + depth_edges[1:]) / 2
rows = []
labels = []
durations = []
colors = []
plotted_episodes = []
latest_date = data["Date"].max()

for _, episode in episodes.iterrows():
    end_date = episode["Recovery_Date"] if pd.notna(episode["Recovery_Date"]) else latest_date
    segment = data[(data["Date"] > episode["Peak_Date"]) & (data["Date"] <= end_date)].copy()
    if segment.empty:
        continue
    segment["Drawdown_Pct"] = (segment["Price"] / episode["Peak_Price"] - 1) * 100
    segment["Depth_Bucket"] = pd.cut(
        segment["Drawdown_Pct"],
        bins=depth_edges,
        labels=False,
        include_lowest=True,
        right=False,
    )
    counts = (
        segment.groupby("Depth_Bucket", observed=False)
        .size()
        .reindex(np.arange(len(depth_centers)), fill_value=0)
    )
    rows.append(counts.to_numpy(dtype=float))
    plotted_episodes.append(episode)
    label = f"{episode['Peak_Date'].year} peak"
    if not episode["Recovered"]:
        label += " (open)"
    labels.append(label)
    durations.append(int(segment.shape[0]))
    colors.append("#FF8C00" if not episode["Recovered"] else "#6C7A89")

heatmap = np.vstack(rows)

fig = plt.figure(figsize=(18, 11))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(1, 2, width_ratios=[1.7, 0.7], wspace=0.08)
ax_heat = fig.add_subplot(gs[0])
ax_bar = fig.add_subplot(gs[1], sharey=ax_heat)
ax_heat.set_facecolor("black")
ax_heat.tick_params(colors="#D8D8D8")
for spine in ax_heat.spines.values():
    spine.set_color("#555555")
style_dark_axis(ax_bar)

norm = mcolors.PowerNorm(gamma=0.7, vmin=0, vmax=max(1.0, np.nanpercentile(heatmap, 98)))
image = ax_heat.imshow(heatmap, aspect="auto", origin="upper", cmap=dark_red_colormap(), norm=norm)
ax_heat.set_yticks(np.arange(len(labels)))
ax_heat.set_yticklabels(labels, color="#D8D8D8", fontsize=10, fontweight="bold")
tick_positions = np.arange(0, len(depth_centers), 2)
ax_heat.set_xticks(tick_positions)
ax_heat.set_xticklabels([f"{depth_centers[index]:.0f}%" for index in tick_positions], color="#D8D8D8", fontsize=9)
ax_heat.set_xlabel("Drawdown Depth Bucket", color="white", fontsize=11, fontweight="bold")
ax_heat.set_ylabel("Major Drawdown Episode", color="white", fontsize=11, fontweight="bold")

y_positions = np.arange(len(labels))
ax_bar.barh(y_positions, durations, color=colors, alpha=0.82)
ax_bar.set_xlabel("Days underwater", color="white", fontsize=11, fontweight="bold")
ax_bar.grid(True, axis="x", color="white", alpha=0.12, linestyle="--")
ax_bar.tick_params(labelleft=False)
for index, episode in enumerate(pd.DataFrame(plotted_episodes).itertuples()):
    ax_bar.text(
        durations[index] + max(durations) * 0.02,
        index,
        f"{episode.Max_Drawdown_Pct:.0f}%",
        va="center",
        color="#D8D8D8",
        fontsize=9,
    )

cbar = fig.colorbar(image, ax=ax_heat, pad=0.012, fraction=0.035)
cbar.ax.tick_params(colors="#D8D8D8")
cbar.set_label("Days spent in depth bucket", color="#D8D8D8", fontsize=10)

longest_label = labels[int(np.argmax(durations))]
longest_duration = max(durations)

fig.text(0.055, 0.965, "Bitcoin Drawdown Duration Heatmap", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "How long each major peak-to-recovery episode spent at each drawdown depth",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.69,
    0.965,
    f"Longest underwater episode: {longest_label}",
    color="#FFD166",
    fontsize=14,
    fontweight="bold",
)
fig.text(0.69, 0.938, f"Duration: {longest_duration} days", color="#C8C8C8", fontsize=10)

output_path = script_dir / "drawdown_duration_heatmap.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
