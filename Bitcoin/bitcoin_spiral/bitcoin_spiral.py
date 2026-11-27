#!/usr/bin/env python3
"""Bitcoin Spiral: log price on a polar clock that turns once every four years."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import (  # noqa: E402
    bitcoin_data_dir,
    currency_label,
    load_daily_price,
    spiral_events,
    spiral_spoke_labels,
    spiral_theta_degrees,
)


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].sort_values("Date").reset_index(drop=True)
events = spiral_events(data)
latest = data.iloc[-1]

price_floor = 10 ** np.floor(np.log10(data["Price"].min()))
price_ceiling = max(1_000_000.0, 10 ** np.ceil(np.log10(data["Price"].max() * 1.5)))
radius_min = np.log10(price_floor)


def radius(prices):
    return np.log10(np.asarray(prices, dtype=float)) - radius_min


def price_tick_label(price):
    if price >= 1_000_000:
        return f"${price / 1_000_000:g}M"
    if price >= 1_000:
        return f"${price / 1_000:g}k"
    return f"${price:g}"


def theta(dates):
    return np.deg2rad(spiral_theta_degrees(dates))


fig = plt.figure(figsize=(14, 14))
fig.patch.set_facecolor("black")
ax = fig.add_subplot(111, projection="polar")
ax.set_facecolor("black")
ax.set_theta_zero_location("N")
ax.set_theta_direction(-1)
ax.set_rlim(0, np.log10(price_ceiling) - radius_min)
ax.grid(color="white", alpha=0.14, linestyle="-", linewidth=0.7)
ax.spines["polar"].set_color("#555555")

# Shade the current calendar year's quadrant.
year_start = pd.Timestamp(year=latest["Date"].year, month=1, day=1)
year_end = pd.Timestamp(year=latest["Date"].year + 1, month=1, day=1) - pd.Timedelta(days=1)
start_angle, end_angle = theta([year_start, year_end])
if end_angle < start_angle:
    end_angle += 2 * np.pi
ax.bar(
    (start_angle + end_angle) / 2,
    ax.get_ylim()[1],
    width=end_angle - start_angle,
    bottom=0,
    color="#ff9f43",
    alpha=0.08,
    linewidth=0,
    zorder=0,
    label=f"{latest['Date'].year} (current year)",
)

ax.plot(theta(data["Date"]), radius(data["Price"]), color="#ff9f43", linewidth=2.2, alpha=0.95, zorder=3, label="Bitcoin")
ax.scatter(theta(events["ath"]["Date"]), radius(events["ath"]["Price"]), color="#3ce38a", s=10, zorder=4, label="All-time highs")
if not events["bottoms"].empty:
    ax.scatter(theta(events["bottoms"]["Date"]), radius(events["bottoms"]["Price"]), color="#ff5f63", s=70, zorder=5, label="Cycle bottoms")
if events["open_low"] is not None:
    low = events["open_low"]
    ax.scatter(
        theta([low["Date"]]),
        radius([low["Price"]]),
        facecolors="none",
        edgecolors="#ff5f63",
        linewidths=1.6,
        s=70,
        zorder=5,
        label=f"Low since ATH ({-low['Drawdown'] * 100:.0f}%)",
    )
if not events["halvings"].empty:
    ax.scatter(
        theta(events["halvings"]["Date"]),
        radius(events["halvings"]["Price"]),
        color="#eef3f8",
        edgecolors="black",
        linewidths=1.0,
        s=70,
        zorder=6,
        label="Halvings",
    )
ax.scatter(
    theta([latest["Date"]]),
    radius([latest["Price"]]),
    color="white",
    edgecolors="#ff9f43",
    linewidths=2.0,
    s=140,
    zorder=7,
    label=f"Now {currency_label(latest['Price'])}",
)

ax.set_xticks(np.deg2rad([0, 90, 180, 270]))
ax.set_xticklabels(spiral_spoke_labels(int(latest["Date"].year)), color="#D8D8D8", fontsize=11)
ax.tick_params(axis="x", pad=26)
tick_prices = [10.0 ** power for power in range(int(np.log10(price_floor)) + 1, int(np.log10(price_ceiling)) + 1)]
ax.set_rticks(radius(tick_prices))
ax.set_yticklabels([price_tick_label(price) for price in tick_prices], color="#D8D8D8", fontsize=9)
ax.set_rlabel_position(96)

fig.text(0.5, 0.965, "Bitcoin Spiral", ha="center", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.5,
    0.938,
    "One clockwise rotation per four years (Jan 1 at the top: 2009, '13, '17, '21, '25); radius is log price",
    ha="center",
    color="#C8C8C8",
    fontsize=11,
)
bottom_text = ", ".join(
    f"{row.Date:%b %Y} {currency_label(row.Price)}".replace("$", r"\$") for row in events["bottoms"].itertuples()
)
fig.text(0.5, 0.045, f"Confirmed cycle bottoms (≥75% drawdown, later recovered): {bottom_text}", ha="center", color="#8F8F8F", fontsize=9)

legend = ax.legend(
    loc="lower center",
    bbox_to_anchor=(0.5, -0.14),
    ncol=4,
    framealpha=0.35,
    facecolor="black",
    edgecolor="#555555",
    fontsize=10,
)
for text in legend.get_texts():
    text.set_color("white")

output_path = script_dir / "bitcoin_spiral.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
