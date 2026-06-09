#!/usr/bin/env python3
"""Bitcoin rolling risk-adjusted return chart."""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bitcoin_chart_utils import bitcoin_data_dir, currency_label, load_daily_price, style_dark_axis


TRADING_DAYS = 365


def rolling_metrics(returns, window, min_periods):
    """Return annualized return, volatility, Sharpe proxy, and Sortino proxy."""
    mean_return = returns.rolling(window, min_periods=min_periods).mean()
    volatility = returns.rolling(window, min_periods=min_periods).std()
    downside_volatility = returns.where(returns < 0, 0).rolling(window, min_periods=min_periods).std()

    annual_return = mean_return * TRADING_DAYS * 100
    annual_volatility = volatility * np.sqrt(TRADING_DAYS) * 100
    sharpe = mean_return / volatility * np.sqrt(TRADING_DAYS)
    sortino = mean_return / downside_volatility * np.sqrt(TRADING_DAYS)
    return annual_return, annual_volatility, sharpe.replace([np.inf, -np.inf], np.nan), sortino.replace([np.inf, -np.inf], np.nan)


script_dir = Path(__file__).parent
data_dir = bitcoin_data_dir(__file__)

data = load_daily_price(data_dir)
data = data[data["Price"] > 0].copy()
data["Log_Return"] = np.log(data["Price"]).diff()
data["ATH"] = data["Price"].cummax()
data["Drawdown_Pct"] = (data["Price"] / data["ATH"] - 1) * 100

data["Return_1Y"], data["Vol_1Y"], data["Sharpe_1Y"], data["Sortino_1Y"] = rolling_metrics(
    data["Log_Return"],
    365,
    180,
)
data["Return_4Y"], data["Vol_4Y"], data["Sharpe_4Y"], data["Sortino_4Y"] = rolling_metrics(
    data["Log_Return"],
    1460,
    730,
)
plot_data = data.dropna(subset=["Sharpe_1Y"]).copy()
current = plot_data.iloc[-1]

fig = plt.figure(figsize=(18, 12))
fig.patch.set_facecolor("black")
gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 1.25, 1.0], hspace=0.13)
ax_price = fig.add_subplot(gs[0])
ax_sharpe = fig.add_subplot(gs[1], sharex=ax_price)
ax_risk = fig.add_subplot(gs[2], sharex=ax_price)
for ax in (ax_price, ax_sharpe, ax_risk):
    style_dark_axis(ax)

ax_price.plot(plot_data["Date"], plot_data["Price"], color="white", linewidth=1.35, label="BTC price")
ax_price.set_yscale("log")
ax_price.set_ylabel("BTC Price (USD)", color="white", fontsize=11, fontweight="bold")
ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: currency_label(x)))

ax_sharpe.axhspan(-4, 0, color="#B51D1A", alpha=0.18)
ax_sharpe.axhspan(1, 2, color="#0B7A3B", alpha=0.14)
ax_sharpe.axhspan(2, 5, color="#0B7A3B", alpha=0.24)
ax_sharpe.axhline(0, color="#D8D8D8", linestyle="--", linewidth=1.1, alpha=0.7)
ax_sharpe.axhline(1, color="#00D26A", linestyle="--", linewidth=1.0, alpha=0.7)
ax_sharpe.axhline(2, color="#00D26A", linestyle=":", linewidth=1.0, alpha=0.7)
ax_sharpe.plot(plot_data["Date"], plot_data["Sharpe_1Y"], color="#00D1FF", linewidth=1.5, label="1Y Sharpe proxy")
ax_sharpe.plot(plot_data["Date"], plot_data["Sharpe_4Y"], color="#FFD166", linewidth=1.8, label="4Y Sharpe proxy")
ax_sharpe.plot(plot_data["Date"], plot_data["Sortino_1Y"], color="#7ED957", linewidth=1.2, alpha=0.72, label="1Y Sortino proxy")
ax_sharpe.set_ylim(-3.2, 4.2)
ax_sharpe.set_ylabel("Risk-Adjusted Return", color="white", fontsize=11, fontweight="bold")
ax_sharpe.legend(loc="upper right", facecolor="black", edgecolor="#555555", labelcolor="white", ncol=3)

ax_return = ax_risk.twinx()
style_dark_axis(ax_return, grid=False)
ax_risk.plot(plot_data["Date"], plot_data["Vol_1Y"], color="#FF6B6B", linewidth=1.45, label="1Y realized vol")
ax_risk.plot(plot_data["Date"], plot_data["Vol_4Y"], color="#FF8C00", linewidth=1.65, label="4Y realized vol")
ax_return.plot(plot_data["Date"], plot_data["Return_1Y"], color="#00D26A", linewidth=1.25, alpha=0.75, label="1Y annualized return")
ax_risk.set_ylabel("Realized Volatility", color="#FF8C00", fontsize=11, fontweight="bold")
ax_return.set_ylabel("Annualized Return", color="#00D26A", fontsize=11, fontweight="bold")
ax_risk.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax_return.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax_risk.set_ylim(0, min(max(np.nanpercentile(plot_data["Vol_1Y"], 99) * 1.15, 100), 320))
return_limit = min(max(np.nanpercentile(np.abs(plot_data["Return_1Y"].dropna()), 97.5) * 1.15, 100), 700)
ax_return.set_ylim(-return_limit, return_limit)
lines, labels = ax_risk.get_legend_handles_labels()
return_lines, return_labels = ax_return.get_legend_handles_labels()
ax_risk.legend(lines + return_lines, labels + return_labels, loc="upper right", facecolor="black", edgecolor="#555555", labelcolor="white", ncol=3)

for ax in (ax_price, ax_sharpe, ax_risk):
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

fig.text(0.055, 0.965, "Bitcoin Risk-Adjusted Returns", color="white", fontsize=24, fontweight="bold")
fig.text(
    0.055,
    0.938,
    "Rolling Sharpe/Sortino proxies use BTC daily log returns with zero risk-free rate; volatility is annualized",
    color="#C8C8C8",
    fontsize=11,
)
fig.text(
    0.76,
    0.965,
    f"1Y Sharpe: {current['Sharpe_1Y']:.2f}",
    color="#00D1FF",
    fontsize=16,
    fontweight="bold",
)
fig.text(
    0.76,
    0.938,
    f"4Y Sharpe: {current['Sharpe_4Y']:.2f} | 1Y vol: {current['Vol_1Y']:.1f}%",
    color="#C8C8C8",
    fontsize=11,
)

output_path = script_dir / "risk_adjusted_returns.png"
plt.savefig(output_path, dpi=300, facecolor="black", bbox_inches="tight")
print(f"Chart saved as '{output_path}'")
plt.close(fig)
