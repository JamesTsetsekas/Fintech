"""Model helpers for the Bitcoin price prediction chart."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


BITCOIN_DIR = Path(__file__).resolve().parents[1]
if str(BITCOIN_DIR) not in sys.path:
    sys.path.insert(0, str(BITCOIN_DIR))

from bitcoin_chart_utils import POWER_LAW_CONSTANT_LOG10, POWER_LAW_EXPONENT, power_law_price  # noqa: E402


GENESIS_DATE = pd.Timestamp("2009-01-03")
SATOSHIS_PER_BTC = 100_000_000


def hpr_price(days):
    """Return the repo's Rainbow/HPR price curve for days since genesis."""
    days_array = np.asarray(days, dtype=float)
    result = np.full(days_array.shape, np.nan, dtype=float)
    mask = days_array > 0
    result[mask] = 10 ** (2.6521 * np.log(days_array[mask]) - 18.163)
    return result


def fit_log_log_model(x_values, y_values):
    """Fit y = exp(intercept) * x ** slope on positive finite inputs."""
    x_array = np.asarray(x_values, dtype=float)
    y_array = np.asarray(y_values, dtype=float)
    mask = (
        np.isfinite(x_array)
        & np.isfinite(y_array)
        & (x_array > 0)
        & (y_array > 0)
    )
    if mask.sum() < 2:
        raise ValueError("at least two positive finite points are required")

    slope, intercept = np.polyfit(np.log(x_array[mask]), np.log(y_array[mask]), 1)
    return float(slope), float(intercept)


def predict_log_log_model(x_values, slope, intercept):
    """Predict a fitted log-log model, returning NaN for invalid x values."""
    x_array = np.asarray(x_values, dtype=float)
    result = np.full(x_array.shape, np.nan, dtype=float)
    mask = np.isfinite(x_array) & (x_array > 0)
    result[mask] = np.exp(intercept) * (x_array[mask] ** slope)
    return result


def load_price_history(dataset_path):
    """Load daily Bitcoin price/supply data without dropping zero-price rows."""
    data = pd.read_csv(dataset_path)
    data["Date"] = pd.to_datetime(data["date"], format="%m/%d/%y")
    data["Price"] = pd.to_numeric(data["price"], errors="coerce")
    data["Block_Height"] = pd.to_numeric(data["block_height"], errors="coerce")
    data["Subsidy_BTC"] = pd.to_numeric(data["subsidy"], errors="coerce")
    data["Supply_BTC"] = pd.to_numeric(data["supply"], errors="coerce")
    data = data.dropna(subset=["Date", "Block_Height", "Subsidy_BTC", "Supply_BTC"])
    data = data.sort_values("Date").reset_index(drop=True)

    data["Blocks_Mined"] = data["Block_Height"].diff().fillna(0).clip(lower=0)
    data["Daily_Issuance_BTC"] = data["Supply_BTC"].diff().fillna(0).clip(lower=0)
    return data[
        [
            "Date",
            "Price",
            "Block_Height",
            "Blocks_Mined",
            "Subsidy_BTC",
            "Supply_BTC",
            "Daily_Issuance_BTC",
        ]
    ]


def load_daily_fees(data_dir):
    """Aggregate block-level fees into daily BTC-denominated fee income."""
    frames = []
    for csv_path in sorted(Path(data_dir).glob("block_data_*.csv")):
        fees = pd.read_csv(csv_path, usecols=["timestamp", "fees"])
        fees["Date"] = (
            pd.to_datetime(fees["timestamp"], unit="s", utc=True)
            .dt.floor("D")
            .dt.tz_localize(None)
        )
        fees["Fees_BTC"] = pd.to_numeric(fees["fees"], errors="coerce").fillna(0)
        fees["Fees_BTC"] = fees["Fees_BTC"] / SATOSHIS_PER_BTC
        frames.append(fees[["Date", "Fees_BTC"]])

    if not frames:
        return pd.DataFrame(columns=["Date", "Fees_BTC"])

    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby("Date", as_index=False)["Fees_BTC"].sum()


def subsidy_for_date(date, halving_info):
    """Return the block subsidy active on a date using the provided schedule."""
    timestamp = pd.Timestamp(date)
    current_reward = float(halving_info[0]["reward"])
    for item in sorted(halving_info, key=lambda row: row["date"]):
        if timestamp >= pd.Timestamp(item["date"]):
            current_reward = float(item["reward"])
        else:
            break
    return current_reward


def build_projection_frame(price_history, daily_fees, end_date, halving_info):
    """Create historical and projected scarcity/income metrics."""
    metrics = price_history.merge(daily_fees, on="Date", how="left")
    metrics["Fees_BTC"] = metrics["Fees_BTC"].fillna(0)

    last_date = metrics["Date"].max()
    end_ts = pd.Timestamp(end_date)
    if end_ts > last_date:
        blocks_per_day = metrics["Blocks_Mined"].tail(365).replace(0, np.nan).mean()
        if not np.isfinite(blocks_per_day) or blocks_per_day <= 0:
            blocks_per_day = 144.0

        trailing_daily_fees = metrics["Fees_BTC"].tail(365).mean()
        if not np.isfinite(trailing_daily_fees):
            trailing_daily_fees = 0.0

        current_supply = float(metrics["Supply_BTC"].iloc[-1])
        current_height = float(metrics["Block_Height"].iloc[-1])
        future_rows = []
        for date in pd.date_range(last_date + pd.Timedelta(days=1), end_ts, freq="D"):
            subsidy = subsidy_for_date(date, halving_info)
            daily_issuance = subsidy * blocks_per_day
            current_supply += daily_issuance
            current_height += blocks_per_day
            future_rows.append(
                {
                    "Date": date,
                    "Price": np.nan,
                    "Block_Height": current_height,
                    "Blocks_Mined": blocks_per_day,
                    "Subsidy_BTC": subsidy,
                    "Supply_BTC": current_supply,
                    "Daily_Issuance_BTC": daily_issuance,
                    "Fees_BTC": trailing_daily_fees,
                }
            )

        if future_rows:
            metrics = pd.concat([metrics, pd.DataFrame(future_rows)], ignore_index=True)

    metrics = metrics.sort_values("Date").reset_index(drop=True)
    metrics["Miner_Income_BTC"] = metrics["Daily_Issuance_BTC"] + metrics["Fees_BTC"]
    metrics["Annual_Flow_BTC"] = (
        metrics["Daily_Issuance_BTC"].rolling(window=365, min_periods=30).sum()
    )
    metrics["Annual_Income_BTC"] = (
        metrics["Miner_Income_BTC"].rolling(window=365, min_periods=30).sum()
    )
    metrics["S2F_Ratio"] = metrics["Supply_BTC"] / metrics["Annual_Flow_BTC"]
    metrics["S2I_Ratio"] = metrics["Supply_BTC"] / metrics["Annual_Income_BTC"]
    metrics["Days_Since_Genesis"] = (metrics["Date"] - GENESIS_DATE).dt.days
    return metrics


def apply_price_models(metrics):
    """Add HPR, power-law, S2F, and S2I model-price columns."""
    modeled = metrics.copy()
    historical = modeled[modeled["Price"].notna() & (modeled["Price"] > 0)]

    power_slope = POWER_LAW_EXPONENT
    power_intercept = POWER_LAW_CONSTANT_LOG10 * np.log(10)
    s2f_slope, s2f_intercept = fit_log_log_model(
        historical["S2F_Ratio"], historical["Price"]
    )
    s2i_slope, s2i_intercept = fit_log_log_model(
        historical["S2I_Ratio"], historical["Price"]
    )

    modeled["HPR"] = hpr_price(modeled["Days_Since_Genesis"])
    modeled["Power_Law"] = power_law_price(modeled["Days_Since_Genesis"])
    modeled["S2F"] = predict_log_log_model(modeled["S2F_Ratio"], s2f_slope, s2f_intercept)
    modeled["S2I"] = predict_log_log_model(modeled["S2I_Ratio"], s2i_slope, s2i_intercept)

    coefficients = {
        "Power Law": (power_slope, power_intercept),
        "Stock-to-Flow": (s2f_slope, s2f_intercept),
        "Stock-to-Income": (s2i_slope, s2i_intercept),
    }
    return modeled, coefficients
