#!/usr/bin/env python3
"""Bitcoin price acceptance heatmap."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, currency_label, dark_red_colormap, load_daily_price, load_intraday_price


def build_share_matrix(frame, column_name, category_order, bucket_count):
    """Return bucket/category share matrix in percent."""
    counts = (
        frame.groupby(["Bucket", column_name], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(index=np.arange(bucket_count), columns=category_order, fill_value=0)
    )
    shares = counts.div(counts.sum(axis=0).replace(0, np.nan), axis=1) * 100
    return shares.to_numpy(dtype=float)


def select_bucket_ticks(bucket_centers, tick_count=8):
    """Pick readable y-axis tick positions and labels."""
    if len(bucket_centers) <= tick_count:
        indices = np.arange(len(bucket_centers))
    else:
        indices = np.linspace(0, len(bucket_centers) - 1, tick_count).round().astype(int)
        indices = np.unique(indices)
    labels = [currency_label(bucket_centers[index]) for index in indices]
    return indices, labels


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

intraday = load_intraday_price(data_dir)
daily = load_daily_price(data_dir)
daily = daily[daily["Price"] > 0].copy()
intraday["Date"] = pd.to_datetime(intraday["Date"]).dt.normalize()
daily["Date"] = pd.to_datetime(daily["Date"]).dt.normalize()

epoch_lookup = daily[["Date", "Epoch"]].drop_duplicates().sort_values("Date")
intraday = intraday.merge(epoch_lookup, on="Date", how="left")
intraday["Year"] = intraday["DateTime"].dt.year
intraday = intraday.dropna(subset=["Epoch"]).copy()
intraday["Epoch"] = intraday["Epoch"].astype(int)

price_min = max(0.05, intraday["Price"].min())
price_max = intraday["Price"].max()
bucket_edges = np.logspace(np.log10(price_min), np.log10(price_max * 1.05), 30)
bucket_centers = np.sqrt(bucket_edges[:-1] * bucket_edges[1:])
intraday["Bucket"] = pd.cut(
    intraday["Price"],
    bins=bucket_edges,
    labels=False,
    include_lowest=True,
)
intraday = intraday.dropna(subset=["Bucket"]).copy()
intraday["Bucket"] = intraday["Bucket"].astype(int)

years = sorted(intraday["Year"].unique())
epochs = sorted(intraday["Epoch"].unique())
year_matrix = build_share_matrix(intraday, "Year", years, len(bucket_centers))
epoch_matrix = build_share_matrix(intraday, "Epoch", epochs, len(bucket_centers))
year_modes = np.nanargmax(np.nan_to_num(year_matrix, nan=-np.inf), axis=0)
epoch_modes = np.nanargmax(np.nan_to_num(epoch_matrix, nan=-np.inf), axis=0)

norm = mcolors.PowerNorm(
    gamma=0.65,
    vmin=0,
    vmax=max(1.0, np.nanpercentile(np.concatenate([year_matrix.ravel(), epoch_matrix.ravel()]), 99)),
)

fig = plt.figure(figsize=(20, 12))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(2, 1, height_ratios=[1.35, 0.85], hspace=0.18)
ax_year = fig.add_subplot(gs[0])
ax_epoch = fig.add_subplot(gs[1])

for ax in (ax_year, ax_epoch):
    ax.set_facecolor("black")
    ax.tick_params(colors="#D8D8D8")
    for spine in ax.spines.values():
        spine.set_color("#555555")

heatmap_cmap = dark_red_colormap()
im_year = ax_year.imshow(year_matrix, aspect="auto", origin="lower", cmap=heatmap_cmap, norm=norm)
ax_year.plot(np.arange(len(years)), year_modes, color="#FFD166", linewidth=1.35, alpha=0.92)
ax_year.set_xticks([index for index, year in enumerate(years) if year % 2 == 0])
ax_year.set_xticklabels(
    [str(year) for year in years if year % 2 == 0],
    color="#D8D8D8",
    fontsize=10,
)
bucket_tick_positions, bucket_tick_labels = select_bucket_ticks(bucket_centers)
ax_year.set_yticks(bucket_tick_positions)
ax_year.set_yticklabels(bucket_tick_labels, color="#D8D8D8", fontsize=10)
ax_year.set_ylabel("Price Bucket", color="white", fontsize=11, fontweight="bold")
ax_year.set_title("10-minute sample share by calendar year", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

im_epoch = ax_epoch.imshow(epoch_matrix, aspect="auto", origin="lower", cmap=heatmap_cmap, norm=norm)
ax_epoch.plot(np.arange(len(epochs)), epoch_modes, color="#FFD166", linewidth=1.35, alpha=0.92)
ax_epoch.set_xticks(np.arange(len(epochs)))
ax_epoch.set_xticklabels([f"E{epoch}" for epoch in epochs], color="#D8D8D8", fontsize=11, fontweight="bold")
ax_epoch.set_yticks(bucket_tick_positions)
ax_epoch.set_yticklabels(bucket_tick_labels, color="#D8D8D8", fontsize=10)
ax_epoch.set_ylabel("Price Bucket", color="white", fontsize=11, fontweight="bold")
ax_epoch.set_title("10-minute sample share by halving epoch", color="white", fontsize=15, fontweight="bold", loc="left", pad=12)

cbar = fig.colorbar(im_epoch, ax=[ax_year, ax_epoch], pad=0.012, fraction=0.028)
cbar.ax.tick_params(colors="#D8D8D8")
cbar.set_label("Share of 10-minute samples in bucket (%)", color="#D8D8D8", fontsize=10)

current_price = intraday["Price"].iloc[-1]
current_bucket = bucket_centers[intraday["Bucket"].iloc[-1]]
current_year_mode = bucket_centers[year_modes[-1]]
current_epoch_mode = bucket_centers[epoch_modes[-1]]

fig.text(0.055, 0.965, "Bitcoin Price Acceptance Heatmap", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Where BTC spent the most time by price bucket using repo-local 10-minute samples",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.72,
    0.965,
    f"Spot: {currency_label(current_price).replace('$', 'USD ')}",
    color="#FFD166",
    fontsize=15,
    fontweight="bold",
)
fig.text(
    0.72,
    0.938,
    f"Current bucket: {currency_label(current_bucket)} | {years[-1]} mode: {currency_label(current_year_mode)} | E{epochs[-1]} mode: {currency_label(current_epoch_mode)}",
    color="#C8C8C8",
    fontsize=10,
)
fig.text(
    0.055,
    0.05,
    "Gold path marks the modal price bucket for each year and halving epoch. Columns are normalized so incomplete periods remain comparable.",
    color="#9E9E9E",
    fontsize=9,
)

output_path = script_dir / "price_acceptance_heatmap.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
