"""Regression coverage for the compact cycle-signal artifact and its method."""

import copy
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Import the modules under the names the site generator itself uses, so
# patches and exception classes refer to the same module objects.
import blockhorizon_data
import signals_artifact as artifact
from web import generate_site


FIXTURE_DIR = Path(__file__).resolve().parent / "tests" / "fixtures" / "signals"
DAY = "2026-01-{:02d}".format


def load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def series(values, *, key=None, name=None, start=1, dates=None):
    dates = dates or [DAY(start + index) for index in range(len(values))]
    item = {"x": dates, "y": list(values)}
    if key is not None:
        item["source_key"] = key
    if name is not None:
        item["name"] = name
    return item


def definitions(signals, **scoring):
    """A minimal method: no warm-up unless a test asks for one."""
    return {
        "method": {
            "version": 2,
            "scoring": {"min_history_days": 0, "min_observations": 1, **scoring},
            "phases": [
                {"key": "bottom", "label": "Bottom", "below": 25},
                {"key": "bearish", "label": "Bearish", "below": 50},
                {"key": "bullish", "label": "Bullish", "below": 75},
                {"key": "top", "label": "Top", "below": None},
            ],
            "change_windows_days": [7, 30, 90, 365],
            "history": {"step_days": 7, "carry_forward_days": 14, "value_significant_digits": 4},
            "freshness": {"sources": {
                "native": {"stale_after_days": 2},
                "blockhorizon": {"stale_after_days": 9},
            }},
            "composite": {"id": "cycle-index", "label": "Cycle Index", "min_members": 1},
        },
        "signals": signals,
    }


def signal(signal_id, *, chart=None, source="native", composite=True, **extra):
    return {
        "id": signal_id,
        "chart_id": chart or signal_id,
        "label": signal_id.title(),
        "category": "Test",
        "source": source,
        "input": {"type": "series", "series": {"name": "metric"}},
        "composite": composite,
        **extra,
    }


def daily(values, start="2024-01-01"):
    dates = pd.date_range(start, periods=len(values), freq="D").strftime("%Y-%m-%d").tolist()
    return {"series": [series(values, name="metric", dates=dates)]}


class GoldenFixtureTests(unittest.TestCase):
    """The browser fallback is tested against the same expected.json."""

    def test_builder_reproduces_the_shared_golden_artifact(self):
        expected = load_fixture("expected.json")
        charts = load_fixture("charts.json")
        built = artifact.build_signals_artifact(load_fixture("definitions.json"), charts.get)
        self.assertEqual(json.loads(json.dumps(built)), expected)

    def test_golden_artifact_covers_the_reviewed_edge_cases(self):
        expected = load_fixture("expected.json")
        by_id = {entry["id"]: entry for entry in expected["signals"]}
        self.assertEqual([entry["id"] for entry in expected["unavailable"]], ["too-short", "renamed", "no-chart"])
        self.assertEqual(by_id["young"]["changes"]["90"], None)
        self.assertTrue(by_id["lagging"]["stale"])
        self.assertFalse(by_id["weekly-ratio"]["stale"])
        self.assertEqual(expected["composite"]["missing_members"], ["abandoned", "too-short"])
        self.assertEqual(expected["data_through"], "2024-12-17")
        # Exact halfway values round away from zero, above and below zero.
        ties_up = by_id["halfway-up"]
        ties_down = by_id["halfway-down"]
        self.assertLessEqual({1.063, 0.1563, 1235.0, 0.007813}, set(ties_up["history"]["values"]))
        self.assertEqual(ties_down["history"]["values"], [-value for value in ties_up["history"]["values"]])
        self.assertEqual((ties_up["value"], ties_down["value"]), (0.007813, -0.007813))
        # An outage is published as unavailable samples, not as a carried score.
        outage = by_id["gappy"]["history"]
        missing = [index for index, score in enumerate(outage["scores"]) if score is None]
        self.assertEqual(missing, list(range(7, 13)))
        self.assertEqual([outage["values"][index] for index in missing], [None] * 6)
        self.assertEqual(expected["history"]["dates"][7:13], ["2024-09-24", "2024-10-01", "2024-10-08", "2024-10-15", "2024-10-22", "2024-10-29"])
        self.assertTrue(all(len(entry["history"]["scores"]) == len(expected["history"]["dates"]) for entry in expected["signals"]))


class DateJoinTests(unittest.TestCase):
    RATIO = {"chart_id": "c", "input": {"type": "ratio", "numerator": {"key": "n"}, "denominator": {"key": "d"}}}

    def resolve(self, numerator, denominator):
        payload = {"series": [
            series([value for _, value in numerator], key="n", dates=[DAY(day) for day, _ in numerator]),
            series([value for _, value in denominator], key="d", dates=[DAY(day) for day, _ in denominator]),
        ]}
        return [(artifact.from_day(day), value) for day, value in artifact.resolve_observations(self.RATIO, payload)]

    def test_a_shifted_denominator_never_pairs_with_another_day(self):
        numerator = [(1, 10), (2, 20), (3, 30)]
        self.assertEqual(self.resolve(numerator, [(2, 2), (3, 3), (4, 4)]), [(DAY(2), 10.0), (DAY(3), 10.0)])

    def test_missing_rows_are_dropped_instead_of_sliding_later_rows(self):
        numerator = [(1, 10), (2, 20), (3, 30)]
        self.assertEqual(self.resolve(numerator, [(1, 5), (2, None), (3, 6)]), [(DAY(1), 2.0), (DAY(3), 5.0)])
        self.assertEqual(self.resolve(numerator, [(1, 5), (3, 6)]), [(DAY(1), 2.0), (DAY(3), 5.0)])

    def test_duplicate_dates_keep_the_latest_real_value_and_zero_is_skipped(self):
        numerator = [(1, 10), (2, 20), (3, 30)]
        denominator = [(1, 1), (1, 4), (2, 0), (3, 3), (3, None)]
        self.assertEqual(self.resolve(numerator, denominator), [(DAY(1), 2.5), (DAY(3), 10.0)])

    def test_unordered_rows_are_sorted_by_date(self):
        self.assertEqual(self.resolve([(3, 30), (1, 10)], [(1, 10), (3, 10)]), [(DAY(1), 1.0), (DAY(3), 3.0)])

    def test_band_position_joins_three_series_by_date(self):
        definition = {"chart_id": "c", "input": {
            "type": "band_position", "value": {"name": "p"}, "lower": {"name": "lo"}, "upper": {"name": "hi"},
        }}
        payload = {"series": [
            series([15, 30, 18], name="p"),
            series([20, 10], name="lo", start=2),
            series([20, 40], name="hi", dates=[DAY(3), DAY(2)]),
        ]}
        resolved = [(artifact.from_day(day), value) for day, value in artifact.resolve_observations(definition, payload)]
        self.assertEqual(resolved, [(DAY(2), 0.5), (DAY(3), 0.8)])

    def test_unresolvable_inputs_raise_instead_of_substituting_another_series(self):
        payload = {"series": [series([1, 2], key="n"), series([1, 2], key="price")]}
        with self.assertRaisesRegex(artifact.SignalUnavailable, "source key 'd' is missing from chart 'c'"):
            artifact.resolve_observations(self.RATIO, payload)
        with self.assertRaisesRegex(artifact.SignalUnavailable, "chart data for 'c' is unavailable"):
            artifact.resolve_observations(self.RATIO, None)

    def test_invalid_dates_and_non_numeric_values_are_ignored(self):
        item = {"x": ["2026-02-30", "2026-01-02", "garbage", "2026-01-03T00:00:00Z", "2026-01-04"], "y": [1, 2, 3, "4", True]}
        self.assertEqual(artifact.series_by_day(item), {artifact.to_day("2026-01-02"): 2.0})


class ScoringMethodTests(unittest.TestCase):
    SCORING = {"min_history_days": 0, "min_observations": 1}

    def scores(self, values, **options):
        observations = list(enumerate(values))
        return artifact.expanding_scores(observations, {**self.SCORING, **options.pop("scoring", {})}, **options)

    def test_rank_is_invariant_to_how_a_metric_is_expressed(self):
        mvrv = [1.2, 0.8, 2.5, 1.2, 3.1, 0.9, 1.7]
        nupl = [1 - 1 / value for value in mvrv]
        self.assertEqual(self.scores(mvrv), self.scores(nupl))
        self.assertEqual(self.scores(mvrv), self.scores([value * 1000 for value in mvrv]))

    def test_ties_use_mid_rank_and_scores_stay_inside_the_scale(self):
        self.assertEqual(self.scores([1.2, 0.8, 2.5, 1.2]), [50.0, 25.0, 100 * 2.5 / 3, 50.0])
        self.assertEqual(self.scores([5, 5, 5, 5]), [50.0, 50.0, 50.0, 50.0])
        rising = self.scores(list(range(1, 200)))
        self.assertTrue(all(0 < score < 100 for score in rising))

    def test_history_is_point_in_time_and_ignores_later_observations(self):
        values = [3, 1, 4, 1, 5, 9, 2, 6]
        self.assertEqual(self.scores(values + [100, -100])[: len(values)], self.scores(values))
        # In hindsight 4 ranks mid-table; on its date it was the highest reading.
        self.assertEqual(self.scores(values)[2], 100 * 2.5 / 3)

    def test_inverted_signals_mirror_the_rank(self):
        values = [400, 10, 250, 10]
        self.assertEqual(self.scores(values, invert=True), [100 - score for score in self.scores(values)])

    def test_warm_up_requires_both_elapsed_days_and_observations(self):
        observations = [(0, 1.0), (10, 2.0), (20, 3.0), (30, 4.0)]
        by_days = artifact.expanding_scores(observations, {"min_history_days": 20, "min_observations": 1})
        self.assertEqual(by_days[:2], [None, None])
        self.assertIsNotNone(by_days[2])
        by_count = artifact.expanding_scores(observations, {"min_history_days": 0, "min_observations": 4})
        self.assertEqual(by_count[:3], [None, None, None])
        self.assertEqual(by_count[3], 87.5)

    def test_rounding_is_half_away_from_zero_on_the_exact_value(self):
        # These halfway values are exactly representable, so the tie is real.
        decimals = [(6.25, 1, 6.3), (-6.25, 1, -6.3), (0.125, 2, 0.13), (-0.125, 2, -0.13), (2.5, 0, 3.0), (-2.5, 0, -3.0),
                    (0.0078125, 6, 0.007813), (-0.0078125, 6, -0.007813), (18.75, 1, 18.8), (34.5, 1, 34.5)]
        for value, places, expected in decimals:
            with self.subTest(value=value, places=places):
                self.assertEqual(artifact.round_decimals(value, places), expected)
        significant = [(1.0625, 4, 1.063), (-1.0625, 4, -1.063), (0.15625, 4, 0.1563), (-0.15625, 4, -0.1563),
                       (1234.5, 4, 1235.0), (-1234.5, 4, -1235.0), (9.9996, 4, 10.0), (73631.4, 4, 73630.0), (0.0, 4, 0.0)]
        for value, digits, expected in significant:
            with self.subTest(value=value, digits=digits):
                self.assertEqual(artifact.round_significant(value, digits), expected)
        # 1.005 is stored slightly below the tie, so the exact value rounds down.
        self.assertEqual(artifact.round_decimals(1.005, 2), 1.0)
        self.assertEqual(str(artifact.round_decimals(-0.04, 1)), "0.0", "negative zero is never published")
        self.assertEqual(str(artifact.round_significant(-0.0, 4)), "0.0")
        self.assertIsNone(artifact.round_score(None))
        self.assertIsNone(artifact.round_significant(None, 4))
        self.assertEqual(artifact.load_definitions()["method"]["rounding"]["rule"], "half_away_from_zero")

    def test_phase_cut_offs(self):
        phases = artifact.load_definitions()["method"]["phases"]
        cases = [(0, "bottom"), (24.9, "bottom"), (25, "bearish"), (49.9, "bearish"), (50, "bullish"), (74.9, "bullish"), (75, "top"), (100, "top")]
        self.assertEqual([artifact.phase_for(score, phases) for score, _ in cases], [phase for _, phase in cases])
        self.assertIsNone(artifact.phase_for(None, phases))


class ArtifactTests(unittest.TestCase):
    def build(self, charts, signals, **scoring):
        return artifact.build_signals_artifact(definitions(signals, **scoring), charts.get)

    def test_changes_are_unavailable_until_scored_history_covers_the_window(self):
        values = [float(value) for value in range(1, 41)]
        built = self.build({"m": daily(values)}, [signal("m")])
        entry = built["signals"][0]
        self.assertEqual(set(entry["changes"]), {"7", "30", "90", "365"})
        self.assertIsNotNone(entry["changes"]["7"])
        self.assertIsNotNone(entry["changes"]["30"])
        self.assertIsNone(entry["changes"]["90"], "40 days of history cannot show a 90-day change")
        self.assertIsNone(entry["changes"]["365"])
        two_days = self.build({"m": daily([1.0, 2.0])}, [signal("m")])["signals"][0]
        self.assertEqual(two_days["changes"], {"7": None, "30": None, "90": None, "365": None})

    def test_changes_ignore_the_unscored_warm_up_period(self):
        built = self.build({"m": daily([float(value % 7) for value in range(50)])}, [signal("m")], min_history_days=30)
        entry = built["signals"][0]
        self.assertIsNotNone(entry["changes"]["7"])
        self.assertIsNone(entry["changes"]["30"], "the reading 30 days ago was not scored yet")
        self.assertIsNone(entry["history"]["scores"][0] if len(entry["history"]["scores"]) > 4 else None)

    def test_a_gap_at_the_look_back_date_is_not_bridged_by_old_data(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="D").strftime("%Y-%m-%d").tolist() + ["2024-03-01"]
        payload = {"series": [series([float(value) for value in range(11)], name="metric", dates=dates)]}
        entry = self.build({"m": payload}, [signal("m")])["signals"][0]
        self.assertIsNone(entry["changes"]["30"], "the nearest earlier reading is weeks before the 30-day mark")

    def test_freshness_uses_the_expected_cadence_of_each_source(self):
        charts = {
            "fresh": daily([1.0] * 30),
            "late": daily([1.0] * 27),
            "weekly": daily([1.0] * 22),
            "weekly-late": daily([1.0] * 20),
        }
        built = self.build(charts, [
            signal("fresh"), signal("late"),
            signal("weekly", source="blockhorizon"), signal("weekly-late", source="blockhorizon"),
        ])
        by_id = {entry["id"]: entry for entry in built["signals"]}
        self.assertEqual(built["data_through"], "2024-01-30")
        self.assertEqual({key: (entry["date"], entry["lag_days"], entry["stale"]) for key, entry in by_id.items()}, {
            "fresh": ("2024-01-30", 0, False),
            "late": ("2024-01-27", 3, True),
            "weekly": ("2024-01-22", 8, False),
            "weekly-late": ("2024-01-20", 10, True),
        })
        self.assertEqual(built["composite"]["stale_members"], ["late", "weekly-late"])
        self.assertNotIn("generated_at", built, "the artifact never embeds a clock reading")

    def test_an_outage_longer_than_the_carry_limit_is_published_as_unavailable(self):
        dates = (pd.date_range("2024-01-01", periods=30, freq="D").strftime("%Y-%m-%d").tolist()
                 + pd.date_range("2024-03-26", periods=10, freq="D").strftime("%Y-%m-%d").tolist())
        payload = {"series": [series([float(value % 9) for value in range(40)], name="metric", dates=dates)]}
        built = self.build({"m": payload, "steady": daily([1.0] * 95)}, [signal("m"), signal("steady")])
        history = dict(zip(built["history"]["dates"], built["signals"][0]["history"]["scores"]))
        # The last reading before the outage is 2024-01-30 and expires 14 days
        # later; readings resume on 2024-03-26.
        outage = [day for day in history if "2024-02-13" < day < "2024-03-26"]
        self.assertEqual(outage, ["2024-02-15", "2024-02-22", "2024-02-29", "2024-03-07", "2024-03-14", "2024-03-21"])
        for day, score in history.items():
            with self.subTest(day=day):
                if day in outage:
                    self.assertIsNone(score, "an outage must not repeat the January score")
                else:
                    self.assertIsNotNone(score)
        composite = dict(zip(built["history"]["dates"], built["composite"]["history"]["scores"]))
        self.assertEqual(composite["2024-03-07"], dict(zip(built["history"]["dates"], built["signals"][1]["history"]["scores"]))["2024-03-07"],
                         "the index only averages members that are current on each date")

    def test_unresolved_definitions_are_reported_not_dropped(self):
        charts = {"m": daily([1.0, 2.0, 3.0]), "empty": daily([None, None])}
        renamed = signal("renamed", chart="m")
        renamed["input"] = {"type": "series", "series": {"name": "old name"}}
        built = self.build(charts, [signal("m"), renamed, signal("empty"), signal("absent")])
        self.assertEqual([entry["id"] for entry in built["signals"]], ["m"])
        self.assertEqual({entry["id"]: entry["reason"] for entry in built["unavailable"]}, {
            "renamed": "series 'old name' is missing from chart 'm'",
            "empty": "no finite observations",
            "absent": "chart data for 'absent' is unavailable",
        })
        self.assertEqual(built["composite"]["missing_members"], ["renamed", "empty", "absent"])
        self.assertEqual((built["composite"]["members_used"], built["composite"]["members_total"]), (1, 4))

    def test_composite_is_the_equal_weight_mean_of_members_only(self):
        charts = {
            "a": daily([1.0, 2.0, 3.0, 4.0]),
            "b": daily([4.0, 3.0, 2.0, 1.0]),
            "c": daily([1.0, 5.0, 2.0, 9.0]),
        }
        duplicate = signal("a-rescaled", chart="a", composite=False, exclusion={"reason": "duplicate", "of": "a"})
        members = [signal("a"), signal("b"), signal("c")]
        built = self.build(charts, members + [duplicate])
        scores = {entry["id"]: entry["score"] for entry in built["signals"]}
        self.assertEqual(scores["a"], scores["a-rescaled"])
        expected = (scores["a"] + scores["b"] + scores["c"]) / 3
        self.assertAlmostEqual(built["composite"]["score"], expected, delta=0.051)
        self.assertEqual(built["composite"]["score"], self.build(charts, members)["composite"]["score"],
                         "a duplicate that is shown must not move the index")
        self.assertEqual(built["method"]["composite"]["members"], ["a", "b", "c"])
        self.assertEqual(built["method"]["composite"]["excluded"], [{"id": "a-rescaled", "reason": "duplicate", "of": "a"}])
        self.assertEqual(built["composite"]["phase"], artifact.phase_for(built["composite"]["score"], built["method"]["phases"]))

    def test_composite_needs_enough_current_members(self):
        charts = {"a": daily([1.0, 2.0, 3.0]), "old": daily([1.0, 2.0], start="2023-11-01")}
        plan = definitions([signal("a"), signal("old")])
        plan["method"]["composite"]["min_members"] = 2
        built = artifact.build_signals_artifact(plan, charts.get)
        self.assertIsNone(built["composite"]["score"], "one current member is below the minimum")
        self.assertIsNone(built["composite"]["phase"])
        self.assertEqual(built["composite"]["missing_members"], ["old"])
        plan["method"]["composite"]["min_members"] = 1
        self.assertIsNotNone(artifact.build_signals_artifact(plan, charts.get)["composite"]["score"])

    def test_history_is_a_shared_weekly_grid_ending_at_the_newest_observation(self):
        built = self.build({"m": daily([float(value % 11) for value in range(60)])}, [signal("m")])
        dates = built["history"]["dates"]
        self.assertEqual(dates[-1], built["data_through"])
        steps = {(pd.Timestamp(b) - pd.Timestamp(a)).days for a, b in zip(dates, dates[1:])}
        self.assertEqual(steps, {7})
        entry = built["signals"][0]
        self.assertEqual(len(entry["history"]["scores"]), len(dates))
        self.assertEqual(len(entry["history"]["values"]), len(dates))
        self.assertEqual(entry["history"]["scores"][-1], entry["score"])
        self.assertEqual(len(built["composite"]["history"]["scores"]), len(dates))

    def test_market_block_reports_price_and_trend_distance(self):
        prices = [100.0 + index for index in range(40)]
        payload = {"series": [
            series(prices, name="BTC price", dates=daily(prices)["series"][0]["x"]),
            series([110.0] * 40, name="200D MA", dates=daily(prices)["series"][0]["x"]),
        ]}
        plan = definitions([signal("m")])
        plan["market"] = {"chart_id": "trend", "price": {"name": "BTC price"}, "average": {"name": "200D MA"}, "recent_observations": 5}
        market = artifact.build_signals_artifact(plan, {"trend": payload, "m": daily([1.0, 2.0])}.get)["market"]
        self.assertEqual((market["date"], market["price"], market["average_200d"]), ("2024-02-09", 139.0, 110.0))
        self.assertEqual(market["change_30d_pct"], round((139 / 109 - 1) * 100, 2))
        self.assertEqual(market["distance_200d_pct"], round((139 / 110 - 1) * 100, 2))
        self.assertEqual(market["recent"]["prices"], [135.0, 136.0, 137.0, 138.0, 139.0])
        plan["market"]["price"] = {"name": "renamed"}
        self.assertIsNone(artifact.build_signals_artifact(plan, {"trend": payload, "m": daily([1.0, 2.0])}.get)["market"])


class PublishedDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.definitions = artifact.load_definitions()
        self.by_id = {entry["id"]: entry for entry in self.definitions["signals"]}

    def test_each_underlying_quantity_is_counted_once(self):
        members = {entry["id"] for entry in self.definitions["signals"] if entry["composite"]}
        duplicates = {
            "nupl": "mvrv", "realized-price": "mvrv",
            "sts-nupl": "sth-mvrv", "realized-price-sts": "sth-mvrv",
            "lts-nupl": "lth-mvrv", "realized-price-lts": "lth-mvrv",
            "trend": "mayer",
        }
        for duplicate, representative in duplicates.items():
            with self.subTest(signal=duplicate):
                self.assertFalse(self.by_id[duplicate]["composite"])
                self.assertEqual(self.by_id[duplicate]["exclusion"]["of"], representative)
                self.assertIn(representative, members)
        for trending in ("hashprice", "fees", "thermocap"):
            self.assertEqual(self.by_id[trending]["exclusion"]["reason"], "structural_trend")
        self.assertEqual(len(members), 16)
        self.assertGreaterEqual(len(members), self.definitions["method"]["composite"]["min_members"])

    def test_definitions_are_complete_and_unambiguous(self):
        ids = [entry["id"] for entry in self.definitions["signals"]]
        self.assertEqual(len(ids), 28)
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(len({entry["chart_id"] for entry in self.definitions["signals"]}), len(ids))
        sources = self.definitions["method"]["freshness"]["sources"]
        for entry in self.definitions["signals"]:
            with self.subTest(signal=entry["id"]):
                self.assertIn(entry["source"], sources)
                self.assertEqual("exclusion" in entry, not entry["composite"])
                self.assertIn(entry["input"]["type"], {"series", "ratio", "band_position"})
        self.assertEqual(self.definitions["method"]["version"], 2)
        self.assertEqual([phase["below"] for phase in self.definitions["method"]["phases"]], [25, 50, 75, None])


def market_frame(days=1500):
    """Deterministic daily history long enough for every rolling window plus
    the two-year scoring warm-up."""
    index = np.arange(days)
    price = 20_000 + 60 * index + 9_000 * np.sin(index / 55) + 2_500 * np.sin(index / 9)
    return pd.DataFrame({
        "Date": pd.date_range("2021-01-01", periods=days, freq="D"),
        "Price": price,
        "Daily_High": price * 1.02,
        "Miner_Revenue_USD": price * (900 + 40 * np.sin(index / 30)),
        "Estimated_Hashrate_EH_S": 150 + index * 0.4,
        "Fee_Rate_Sats_VByte": 12 + 8 * np.sin(index / 21),
        "Fee_Share_Pct": 3 + 2 * np.sin(index / 33),
    })


# Series keys the imported bundle must keep publishing for each signal chart.
BLOCKHORIZON_SERIES_KEYS = {
    "nupl": "nupl",
    "percent-utxos-in-profit": "Percent UTXOs in profit",
    "market-cap-to-thermocap-ratio": "Market cap to thermocap ratio",
    "sts-nupl": "sts_nupl",
    "lts-nupl": "lts_nupl",
    "realized-price-sts": "Realized price STS",
    "balanced-price": "balanced_price",
    "sth-mvrv": "sth_mvrv",
    "realized-price": "realized_price",
    "mvrv": "mvrv",
    "percent-supply-in-profit": "Percent supply in profit",
    "top-price": "top_price",
    "mvrv-z-score": "mvrv_z_score",
    "delta-price": "delta_price",
    "lth-mvrv": "lth_mvrv",
    "realized-price-lts": "Realized price LTS",
}


def source_chart(slug, series_key, weeks=215):
    values = [round(1.5 + np.sin(index / 9) + index * 0.001, 6) for index in range(weeks)]
    return {
        "slug": slug,
        "name": slug,
        "include_btc": slug != "price",
        "series": [{
            "id": 1,
            "series_key": series_key,
            "name": series_key,
            "value_prefix": "$" if "price" in slug else "",
            "pd": {"t0": 1609459200000, "d": [0] + [7] * (weeks - 1), "v": values},
        }],
    }


class SignalContractTests(unittest.TestCase):
    """Every published definition must resolve against freshly built chart
    payloads, so renaming a series, key or chart fails here instead of
    silently removing a signal from the site."""

    def build_payloads(self):
        frame = market_frame()
        definitions_ = artifact.load_definitions()
        payloads = {}
        with (
            patch.object(generate_site, "load_daily_price", side_effect=lambda *_: frame.copy()),
            patch.object(generate_site, "load_market_frame", side_effect=lambda *_: frame.copy()),
        ):
            for entry in definitions_["signals"]:
                if entry["source"] == "native":
                    payloads[entry["chart_id"]] = generate_site.INTERACTIVE_BUILDERS[entry["chart_id"]]()
            market_chart = definitions_["market"]["chart_id"]
            payloads[market_chart] = generate_site.INTERACTIVE_BUILDERS[market_chart]()
        price_chart = source_chart("price", "price")
        for slug, series_key in BLOCKHORIZON_SERIES_KEYS.items():
            payloads[slug] = blockhorizon_data._build_payload(source_chart(slug, series_key), price_chart, None)
        return definitions_, json.loads(json.dumps(payloads))

    def test_every_signal_definition_resolves_and_scores(self):
        definitions_, payloads = self.build_payloads()
        built = artifact.build_signals_artifact(definitions_, payloads.get)
        self.assertEqual(built["unavailable"], [])
        self.assertEqual([entry["id"] for entry in built["signals"]], [entry["id"] for entry in definitions_["signals"]])
        for entry in built["signals"]:
            with self.subTest(signal=entry["id"]):
                self.assertTrue(0 <= entry["score"] <= 100)
                self.assertIsNotNone(entry["value"])
        self.assertEqual(built["composite"]["members_used"], built["composite"]["members_total"])
        self.assertIsNotNone(built["market"])
        json.dumps(built, allow_nan=False)

    def test_native_definitions_name_series_the_builders_actually_emit(self):
        definitions_, payloads = self.build_payloads()
        for entry in definitions_["signals"]:
            selectors = [value for key, value in entry["input"].items() if key != "type"]
            for selector in selectors:
                with self.subTest(signal=entry["id"], selector=selector):
                    self.assertIsNotNone(artifact.select_series(payloads[entry["chart_id"]], selector))

    def test_imported_signal_charts_are_reviewed_and_keyed(self):
        definitions_ = artifact.load_definitions()
        imported = {entry["chart_id"] for entry in definitions_["signals"] if entry["source"] == "blockhorizon"}
        self.assertEqual(imported, set(BLOCKHORIZON_SERIES_KEYS))
        self.assertLessEqual(imported, set(blockhorizon_data.REFERENCE_CHARTS) - set(blockhorizon_data.REFERENCE_EQUIVALENTS))
        native = {entry["chart_id"] for entry in definitions_["signals"] if entry["source"] == "native"}
        self.assertLessEqual(native, set(generate_site.INTERACTIVE_BUILDERS))

    def test_a_renamed_series_is_detected(self):
        definitions_, payloads = self.build_payloads()
        for item in payloads["mayer-multiple"]["series"]:
            item["name"] = "Mayer"
        for item in payloads["mvrv"]["series"]:
            if item.get("source_key") == "mvrv":
                item["source_key"] = "mvrv_ratio"
        built = artifact.build_signals_artifact(definitions_, payloads.get)
        self.assertEqual({entry["id"] for entry in built["unavailable"]}, {"mayer", "mvrv"})
        self.assertEqual(built["composite"]["missing_members"], ["mvrv", "mayer"])

    @unittest.skipUnless(os.environ.get("FINTECH_LIVE_TESTS") == "1", "opt-in upstream integration check")
    def test_current_bundle_still_publishes_every_signal_series(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            blockhorizon_data.import_reference_charts(directory, lambda value: value)
            load = artifact.directory_payload_loader(directory)
            for entry in artifact.load_definitions()["signals"]:
                if entry["source"] != "blockhorizon":
                    continue
                with self.subTest(signal=entry["id"]):
                    self.assertTrue(artifact.resolve_observations(entry, load(entry["chart_id"])))


class PublishingTests(unittest.TestCase):
    def write_charts(self, directory):
        for chart_id, payload in load_fixture("charts.json").items():
            (directory / f"{chart_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_artifact_is_written_compactly_next_to_the_chart_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_charts(directory)
            written = artifact.write_signals_artifact(directory, load_fixture("definitions.json"))
            text = (directory / "signals.json").read_text(encoding="utf-8")
            published = json.loads(text)
            self.assertEqual(published["schema_version"], 1)
            self.assertEqual(published["signals"], json.loads(json.dumps(written["signals"])))
            self.assertNotIn("NaN", text)
            self.assertEqual(text.strip(), json.dumps(published, separators=(",", ":")), "the artifact is written without padding")
            self.assertFalse((directory / "signals.json.tmp").exists())
            expected = copy.deepcopy(load_fixture("expected.json"))
            self.assertEqual({key: published[key] for key in ("data_through", "composite", "unavailable")},
                             {key: expected[key] for key in ("data_through", "composite", "unavailable")})

    def test_identical_inputs_build_byte_identical_artifacts(self):
        # No clock reading is embedded, so two builds at different times agree
        # byte for byte and the publisher can skip an unchanged site.
        definitions_ = load_fixture("definitions.json")
        files = []
        for moment in ("2026-01-01T00:00:00+00:00", "2031-06-15T12:34:56+00:00"):
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                self.write_charts(directory)
                frozen = datetime.fromisoformat(moment)
                with patch("datetime.datetime") as clock, patch("time.time", return_value=frozen.timestamp()):
                    clock.now.return_value = frozen
                    clock.utcnow.return_value = frozen
                    artifact.write_signals_artifact(directory, definitions_)
                files.append((directory / "signals.json").read_bytes())
        self.assertEqual(files[0], files[1])
        self.assertTrue(files[0].endswith(b"}\n") and b"\r" not in files[0])
        text = files[0].decode("utf-8")
        for key in ("generated_at", "updated_at", "built_at", "timestamp"):
            self.assertNotIn(key, text)
        self.assertNotRegex(text, r"20(2[5-9]|3\d)-\d\d-\d\dT", "no time of day appears anywhere in the artifact")

    def test_source_fingerprint_identifies_the_inputs(self):
        definitions_ = load_fixture("definitions.json")
        charts = load_fixture("charts.json")
        base = artifact.build_signals_artifact(definitions_, charts.get)
        self.assertRegex(base["source_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(base["source_fingerprint"], artifact.build_signals_artifact(copy.deepcopy(definitions_), copy.deepcopy(charts).get)["source_fingerprint"])
        revised = copy.deepcopy(charts)
        revised["plain-chart"]["series"][0]["y"][3] += 0.5
        self.assertNotEqual(base["source_fingerprint"], artifact.build_signals_artifact(definitions_, revised.get)["source_fingerprint"],
                            "a revised historical observation is a different input")
        unrelated = copy.deepcopy(charts)
        unrelated["plain-chart"]["series"].append({"name": "Not a signal input", "x": ["2024-06-01"], "y": [1]})
        unrelated["plain-chart"]["updated_at"] = "2030-01-01T00:00:00+00:00"
        self.assertEqual(base["source_fingerprint"], artifact.build_signals_artifact(definitions_, unrelated.get)["source_fingerprint"],
                         "series and timestamps the signals do not read are not inputs")
        new_method = copy.deepcopy(definitions_)
        new_method["method"]["version"] = 3
        self.assertNotEqual(base["source_fingerprint"], artifact.build_signals_artifact(new_method, charts.get)["source_fingerprint"])

    def test_site_build_keeps_going_and_removes_a_stale_artifact_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "signals.json").write_text('{"stale": true}', encoding="utf-8")
            with patch("builtins.print"):
                self.assertIsNone(generate_site.generate_signals_artifact(directory))
            self.assertFalse((directory / "signals.json").exists(), "no chart data means no artifact, not an old one")

    def test_site_build_reports_unavailable_signals(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_charts(directory)
            lines = []
            with (
                patch.object(artifact, "load_definitions", return_value=load_fixture("definitions.json")),
                patch("builtins.print", side_effect=lambda *values: lines.append(" ".join(map(str, values)))),
            ):
                entry = generate_site.generate_signals_artifact(directory)
            published = json.loads((directory / "signals.json").read_text(encoding="utf-8"))
            self.assertEqual(entry, {
                "path": "web/data/bitcoin/signals.json",
                "source_fingerprint": published["source_fingerprint"],
                "data_through": "2024-12-17",
                "method_version": 2,
            })
            self.assertIn("WARNING: signal unavailable: renamed (series 'Old metric name' is missing from chart 'plain-chart')", lines)
            self.assertTrue(any(line.startswith("Generated signal artifact: 11 signals") for line in lines))

    def test_manifest_records_the_artifact_and_supplies_the_publication_time(self):
        entry = {"path": "web/data/bitcoin/signals.json", "source_fingerprint": "f" * 64, "data_through": "2024-12-17", "method_version": 2}
        for outcome in (entry, None):
            written = []
            with tempfile.TemporaryDirectory() as temporary:
                with (
                    patch.object(generate_site, "WEB_DATA_DIR", Path(temporary)),
                    patch.object(generate_site, "BITCOIN_SITE_DATA_DIR", Path(temporary) / "bitcoin"),
                    patch.object(generate_site, "generate_interactive_data"),
                    patch.object(generate_site, "import_reference_charts", return_value=[]),
                    patch.object(generate_site, "generate_signals_artifact", return_value=outcome),
                    patch.object(generate_site, "build_bitcoin_manifest", return_value={"generated_at": "2026-01-01T00:00:00+00:00", "charts": []}),
                    patch.object(generate_site, "write_json", side_effect=lambda path, payload: written.append(json.loads(json.dumps(payload)))),
                    patch("builtins.print"),
                ):
                    self.assertEqual(generate_site.main(), 0)
            self.assertEqual(len(written), 2)
            for manifest in written:
                self.assertIn("signals", manifest)
                self.assertEqual(manifest["signals"], outcome)
                self.assertEqual(manifest["generated_at"], "2026-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
