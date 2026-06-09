#!/usr/bin/env python3
"""Tests for model_price_prediction helpers."""

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).parent))

from model_projection import (  # noqa: E402
    apply_price_models,
    build_projection_frame,
    fit_log_log_model,
    hpr_price,
    predict_log_log_model,
)


HALVING_INFO = [
    {"date": pd.Timestamp("2020-01-01"), "reward": 6.25},
    {"date": pd.Timestamp("2024-04-19"), "reward": 3.125},
]


def synthetic_price_history(periods=420):
    dates = pd.date_range("2021-01-01", periods=periods, freq="D")
    daily_issuance = np.full(periods, 900.0)
    supply = 18_000_000 + np.cumsum(daily_issuance)
    blocks_mined = np.full(periods, 144.0)
    blocks_mined[0] = 0.0
    return pd.DataFrame(
        {
            "Date": dates,
            "Price": np.linspace(10_000, 60_000, periods),
            "Block_Height": 700_000 + np.cumsum(blocks_mined),
            "Blocks_Mined": blocks_mined,
            "Subsidy_BTC": np.full(periods, 6.25),
            "Supply_BTC": supply,
            "Daily_Issuance_BTC": daily_issuance,
        }
    )


class ModelProjectionTests(unittest.TestCase):
    def test_fit_and_predict_log_log_model(self):
        x_values = np.array([1.0, 2.0, 4.0, 8.0])
        y_values = 3.0 * (x_values ** 2)

        slope, intercept = fit_log_log_model(x_values, y_values)
        predicted = predict_log_log_model(x_values, slope, intercept)

        self.assertAlmostEqual(slope, 2.0, places=6)
        np.testing.assert_allclose(predicted, y_values, rtol=1e-9)

    def test_hpr_ignores_nonpositive_days(self):
        result = hpr_price([-1, 0, 10])

        self.assertTrue(np.isnan(result[0]))
        self.assertTrue(np.isnan(result[1]))
        self.assertTrue(np.isfinite(result[2]))

    def test_stock_to_income_includes_fees(self):
        history = synthetic_price_history()
        fees = pd.DataFrame({"Date": history["Date"], "Fees_BTC": np.full(len(history), 5.0)})

        metrics = build_projection_frame(history, fees, history["Date"].max(), HALVING_INFO)
        last = metrics.iloc[-1]

        self.assertGreater(last["S2F_Ratio"], 0)
        self.assertGreater(last["S2I_Ratio"], 0)
        self.assertLess(last["S2I_Ratio"], last["S2F_Ratio"])

    def test_apply_price_models_adds_finite_outputs(self):
        history = synthetic_price_history()
        fees = pd.DataFrame({"Date": history["Date"], "Fees_BTC": np.full(len(history), 5.0)})
        metrics = build_projection_frame(
            history,
            fees,
            history["Date"].max() + pd.Timedelta(days=14),
            HALVING_INFO,
        )

        modeled, coefficients = apply_price_models(metrics)
        last = modeled.iloc[-1]

        self.assertIn("Stock-to-Flow", coefficients)
        self.assertGreater(last["Supply_BTC"], history["Supply_BTC"].iloc[-1])
        self.assertTrue(np.isfinite(last["Power_Law"]))
        self.assertTrue(np.isfinite(last["S2F"]))
        self.assertTrue(np.isfinite(last["S2I"]))


if __name__ == "__main__":
    unittest.main()
