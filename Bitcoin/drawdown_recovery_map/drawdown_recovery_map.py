#!/usr/bin/env python3
"""Bitcoin drawdown and recovery map."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, load_daily_price, style_dark_axis


def find_drawdown_episodes(data):
    episodes = []
    peak_date = data.iloc[0]["Date"]
    peak_price = data.iloc[0]["Price"]
    in_drawdown = False
    start_date = None
    trough_date = None
    trough_price = peak_price

    for _, row in data.iterrows():
        price = row["Price"]
        date = row["Date"]
        if price >= peak_price:
            if in_drawdown:
                depth = (trough_price / peak_price - 1) * 100
                episodes.append(
                    {
                        "Peak_Date": peak_date,
                        "Peak_Price": peak_price,
                        "Start_Date": start_date,
                        "Trough_Date": trough_date,
                        "Trough_Price": trough_price,
                        "Recovery_Date": date,
                        "Max_Drawdown_Pct": depth,
                        "Days_To_Trough": (trough_date - peak_date).days,
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
        depth = (trough_price / peak_price - 1) * 100
        episodes.append(
            {
                "Peak_Date": peak_date,
                "Peak_Price": peak_price,
                "Start_Date": start_date,
                "Trough_Date": trough_date,
                "Trough_Price": trough_price,
                "Recovery_Date": pd.NaT,
                "Max_Drawdown_Pct": depth,
                "Days_To_Trough": (trough_date - peak_date).days,
                "Days_To_Recover": (data.iloc[-1]["Date"] - peak_date).days,
                "Recovered": False,
            }
        )
    return pd.DataFrame(episodes)


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
data["ATH"] = data["Price"].cummax()
data["Drawdown_Pct"] = (data["Price"] / data["ATH"] - 1) * 100

episodes = find_drawdown_episodes(data)
material = episodes[
    (episodes["Max_Drawdown_Pct"] <= -20) | (episodes["Days_To_Recover"] >= 90) | (~episodes["Recovered"])
].copy()
top_episodes = material.sort_values("Max_Drawdown_Pct").head(12).sort_values("Peak_Date")
current = data.iloc[-1]

fig = plt.figure(figsize=(18, 12))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(2, 1, height_ratios=[1.3, 1.0], hspace=0.28)
ax_drawdown = fig.add_subplot(gs[0])
ax_episodes = fig.add_subplot(gs[1])
style_dark_axis(ax_drawdown)
style_dark_axis(ax_episodes, grid=False)

ax_drawdown.fill_between(data["Date"], data["Drawdown_Pct"], 0, color="#B51D1A", alpha=0.35)
ax_drawdown.plot(data["Date"], data["Drawdown_Pct"], color="#FF6B6B", linewidth=1.4)
ax_drawdown.axhline(-20, color="#FFD166", linestyle="--", linewidth=1, alpha=0.8)
ax_drawdown.axhline(-50, color="#FF8C00", linestyle="--", linewidth=1, alpha=0.8)
ax_drawdown.axhline(-80, color="#FF4D4D", linestyle="--", linewidth=1, alpha=0.8)
ax_drawdown.set_ylim(min(-90, data["Drawdown_Pct"].min() * 1.08), 5)
ax_drawdown.set_ylabel("Drawdown from ATH", color="white", fontsize=11, fontweight="bold")
ax_drawdown.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax_drawdown.xaxis.set_major_locator(mdates.YearLocator(2))
ax_drawdown.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

labels = []
durations = []
colors = []
for _, episode in top_episodes.iterrows():
    label = f"{episode['Peak_Date'].year} peak"
    if not episode["Recovered"]:
        label += " (open)"
    labels.append(label)
    durations.append(episode["Days_To_Recover"])
    colors.append("#FF8C00" if not episode["Recovered"] else "#6C7A89")

y_pos = np.arange(len(labels))
ax_episodes.barh(y_pos, durations, color=colors, alpha=0.8)
ax_episodes.set_yticks(y_pos)
ax_episodes.set_yticklabels(labels, color="#D8D8D8")
ax_episodes.set_xlabel("Days From ATH To Recovery (or current age if open)", color="white", fontsize=11, fontweight="bold")
ax_episodes.invert_yaxis()
ax_episodes.grid(True, axis="x", color="white", alpha=0.12, linestyle="--")

for i, (_, episode) in enumerate(top_episodes.iterrows()):
    label = f"{episode['Max_Drawdown_Pct']:.0f}% | trough {episode['Trough_Date'].date()}"
    ax_episodes.text(episode["Days_To_Recover"] + 25, i, label, va="center", color="#D8D8D8", fontsize=9)

fig.text(0.055, 0.965, "Bitcoin Drawdown Recovery Map", color="white", fontsize=24, fontweight="bold")
fig.text(0.055, 0.938, "ATH drawdowns, recovery durations, and deepest historical underwater periods", color="#C8C8C8", fontsize=11)
fig.text(
    0.75,
    0.965,
    f"Current drawdown: {current['Drawdown_Pct']:.1f}%",
    color="#FF6B6B" if current["Drawdown_Pct"] < -20 else "#FFD166",
    fontsize=15,
    fontweight="bold",
)

output_path = script_dir / "drawdown_recovery_map.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
