import unittest

import pandas as pd

from bitcoin_chart_utils import spiral_events, spiral_spoke_labels, spiral_theta_degrees


class SpiralGeometryTests(unittest.TestCase):
    def test_four_year_clock_starts_at_top_and_turns_clockwise(self):
        angles = spiral_theta_degrees(["2009-01-01", "2010-01-01", "2011-01-01", "2012-01-01", "2013-01-01", "2024-07-02"])
        self.assertEqual(list(angles[:5]), [0.0, 90.0, 180.0, 270.0, 0.0])
        # Mid-2024 (a leap year) sits halfway through the 9 o'clock quadrant.
        self.assertAlmostEqual(angles[5], 270 + 90 * 183 / 366)

    def test_spoke_labels_run_through_the_current_rotation(self):
        self.assertEqual(
            spiral_spoke_labels(2026),
            ["2009, '13, '17, '21, '25", "2010, '14, '18, '22, '26", "2011, '15, '19, '23, '27", "2012, '16, '20, '24, '28"],
        )
        self.assertEqual(spiral_spoke_labels(2029)[0], "2009, '13, '17, '21, '25, '29")


class SpiralEventTests(unittest.TestCase):
    def frame(self, prices, start="2020-01-01"):
        return pd.DataFrame({"Date": pd.date_range(start, periods=len(prices), freq="D"), "Price": prices})

    def test_marks_new_closing_highs_and_only_recovered_deep_bottoms(self):
        # Peak 100 -> 20 (80% drawdown) -> new high 120 -> 90 (still open, 25%).
        events = spiral_events(self.frame([10, 50, 100, 60, 20, 40, 120, 90]))
        self.assertEqual(events["ath"]["Price"].tolist(), [10, 50, 100, 120])
        self.assertEqual(events["bottoms"]["Price"].tolist(), [20])
        self.assertAlmostEqual(events["bottoms"]["Drawdown"].iloc[0], 0.8)
        self.assertEqual(events["open_low"]["Price"], 90)
        self.assertAlmostEqual(events["open_low"]["Drawdown"], 0.25)

    def test_shallow_recovered_drawdowns_are_not_cycle_bottoms(self):
        events = spiral_events(self.frame([100, 50, 110]))
        self.assertTrue(events["bottoms"].empty)
        self.assertIsNone(events["open_low"])

    def test_halvings_use_the_close_on_the_halving_date(self):
        events = spiral_events(self.frame([1.0 + index for index in range(10)], start="2016-07-05"))
        self.assertEqual(events["halvings"]["Date"].tolist(), [pd.Timestamp("2016-07-09")])
        self.assertEqual(events["halvings"]["Price"].tolist(), [5.0])


if __name__ == "__main__":
    unittest.main()
