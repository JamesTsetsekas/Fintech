"""Known-unit regression coverage for the web hashprice generator."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from web import generate_site


class MinerHashpriceTests(unittest.TestCase):
    def test_daily_and_smoothed_hashprice_are_usd_per_petahash_per_day(self):
        # 1,000 EH/s = 1,000,000 PH/s; $50M/day gives $50/PH/s/day.
        frame = pd.DataFrame({
            "Date": pd.date_range("2026-01-01", periods=30, freq="D"),
            "Price": 100_000.0,
            "Estimated_Hashrate_EH_S": 1_000.0,
            "Miner_Revenue_USD": 50_000_000.0,
        })
        with patch.object(generate_site, "load_market_frame", return_value=frame):
            payload = generate_site.build_miner_hashprice()

        series = {item["name"]: item for item in payload["series"]}
        for name in ("Daily hashprice", "30D average"):
            with self.subTest(series=name):
                values = series[name]["y"]
                self.assertEqual(len(values), 21)  # Rolling mean needs 10 days.
                for value in values:
                    self.assertAlmostEqual(value, 50.0)


if __name__ == "__main__":
    unittest.main()
