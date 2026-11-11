"""Regression coverage for the reviewed BlockHorizon import boundary."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from web import blockhorizon_data as data


def chart(slug, name, value=2):
    return {
        "slug": slug,
        "name": name,
        "series": [{
            "id": 1,
            "series_key": "price" if slug == "price" else "metric",
            "name": name,
            "pd": {"t0": 1767225600000, "d": [0, 1], "v": [value, value + 1]},
        }],
    }


class CatalogImportTests(unittest.TestCase):
    def test_nupl_normal_view_keeps_discrete_source_colors_and_real_gaps(self):
        metric = chart("nupl", "NUPL")
        series = metric["series"][0]
        series["series_key"] = "nupl"
        observations = [-.1, 0, .25, .5, .75, None]
        series["pd"].update({"d": [0, 1, 1, 1, 1, 1], "v": observations})
        trace = data._line_trace(metric, series, 0)
        self.assertEqual(trace["mode"], "lines")
        self.assertTrue(trace["value_colored_line"])
        self.assertEqual(trace["marker"]["size"], 0)
        self.assertEqual(trace["marker"]["color"], ["#e54242", "#ef7f11", "#ebd249", "#24c813", "#4467eb", "rgba(0,0,0,0)"])
        self.assertEqual(trace["y"], observations)

    def test_signal_metadata_is_separate_from_the_metric_observations(self):
        metric = chart("mvrv-z-score", "MVRV Z-Score")
        metric["include_btc"] = True
        metric["series"][0]["series_key"] = "mvrv_z_score"
        metric["gradient_config"] = {
            "default_mode": "absolute", "default_series_key": "mvrv_z_score",
            "absolute": {"default_min": 0, "default_max": 5},
        }
        metric["style_config"] = {"valueZones": [{"seriesKey": "mvrv_z_score", "greenBelow": .85, "redAbove": 1.75}]}
        payload = data._build_payload(metric, chart("price", "Price", 70000), None)
        self.assertEqual(payload["signal_view"], {"mode": "absolute", "series_key": "mvrv_z_score", "min": 0, "max": 5})
        source = next(series for series in payload["series"] if series["source_key"] == "mvrv_z_score")
        self.assertEqual(source["y"], [2, 3])
        self.assertEqual(source["mode"], "lines")
        self.assertNotIn("marker", source, "normal MVRV uses a continuous brand-colored metric line")

    def test_price_ratio_signal_mode_keeps_its_reviewed_domain(self):
        metric = chart("realized-price", "Realized Price")
        metric["include_btc"] = True
        metric["gradient_config"] = {
            "default_mode": "error", "default_series_key": "metric",
            "error": {"default_min": .6, "default_max": 3.5},
        }
        payload = data._build_payload(metric, chart("price", "Price"), None)
        self.assertEqual(payload["signal_view"], {"mode": "error", "series_key": "metric", "min": .6, "max": 3.5})

    def test_signal_metadata_requires_a_supported_metric_and_finite_domain(self):
        metric = chart("fixture", "Metric")
        metric["include_btc"] = True
        metric["gradient_config"] = {
            "default_mode": "absolute", "default_series_key": "missing",
            "absolute": {"default_min": 0, "default_max": 5},
        }
        self.assertIsNone(data._signal_view_config(metric))
        metric["gradient_config"]["default_series_key"] = "metric"
        metric["gradient_config"]["absolute"]["default_max"] = 0
        self.assertIsNone(data._signal_view_config(metric))

    def import_fixture(self, directory, bundle):
        with (
            patch.object(data, "REFERENCE_CHARTS", {"fees-total": "Fees Total (Daily)"}, create=True),
            patch.object(data, "REFERENCE_CHART_TITLES", ("Fees Total",)),
            patch.object(data, "_fetch_bundle", return_value=(bundle, "2026-10-20T00:00:00Z")),
        ):
            return data.import_reference_charts(directory, lambda value: value)

    def test_title_rename_imports_fresh_data_and_keeps_slug(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            cached = {"id": "fees-total", "title": "Fees Total", "series": [{"y": [999]}]}
            (directory / "fees-total.json").write_text(json.dumps(cached), encoding="utf-8")
            entries = self.import_fixture(directory, [chart("price", "Price"), chart("fees-total", "Fees Total (Daily)")])
            payload = json.loads((directory / "fees-total.json").read_text(encoding="utf-8"))
            self.assertEqual([entry["id"] for entry in entries], ["fees-total"])
            self.assertEqual(payload["series"][0]["y"], [2, 3])
            self.assertEqual(entries[0]["title"], "Fees Total (Daily)")

    def test_missing_reviewed_slug_fails_even_with_cached_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            cached = {"id": "fees-total", "title": "Fees Total", "series": [{"y": [999]}]}
            (directory / "fees-total.json").write_text(json.dumps(cached), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "fees-total"):
                self.import_fixture(directory, [chart("price", "Price")])
            self.assertEqual(json.loads((directory / "fees-total.json").read_text(encoding="utf-8")), cached)

    def test_retired_generated_series_are_removed_after_a_successful_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            retired_path = directory / "adjusted-mvrv.json"
            retired_path.write_text('{"series":[{"y":[999]}]}', encoding="utf-8")
            self.import_fixture(directory, [chart("price", "Price"), chart("fees-total", "Fees Total (Daily)")])
            self.assertFalse(retired_path.exists())

    def test_invalid_metric_cannot_succeed_using_only_its_price_overlay(self):
        invalid = chart("fees-total", "Fees Total (Daily)")
        invalid["include_btc"] = True
        invalid["series"][0]["pd"]["d"] = []
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "fees-total"):
                self.import_fixture(directory, [chart("price", "Price"), invalid])
            self.assertEqual(list(directory.iterdir()), [])

    def test_unreviewed_bundle_charts_do_not_enter_the_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            entries = self.import_fixture(Path(temporary), [
                chart("price", "Price"), chart("fees-total", "Fees Total (Daily)"),
                chart("unreviewed-experiment", "Not in the reviewed public library"),
            ])
            self.assertEqual([entry["id"] for entry in entries], ["fees-total"])

    def test_cohort_gap_keeps_its_own_pane_and_percentage_point_unit(self):
        cohort = chart("old-vs-new-loss", "Supply in Loss (%): Old vs New Coins")
        cohort["include_btc"] = True
        cohort["series"] = []
        for key, suffix in [("lts_in_loss_pct", "%"), ("sts_in_loss_pct", "%"), ("lts_minus_sts_pp", " pp")]:
            series = chart("fixture", key)["series"][0]
            series.update({"series_key": key, "value_suffix": suffix})
            cohort["series"].append(series)
        payload = data._build_payload(cohort, chart("price", "Price"), None)
        by_key = {series["source_key"]: series for series in payload["series"]}
        self.assertEqual(by_key["lts_minus_sts_pp"]["axis"], "y3")
        self.assertEqual(by_key["lts_in_loss_pct"]["axis"], "y2")
        self.assertLess(payload["layout"]["yaxis3"]["domain"][1], payload["layout"]["yaxis"]["domain"][0])
        self.assertEqual(payload["layout"]["yaxis2"]["range"], [0, 100])
        self.assertEqual(payload["layout"]["yaxis3"]["ticksuffix"], " pp")
        self.assertIn(" pp", by_key["lts_minus_sts_pp"]["hovertemplate"])

    def test_weekly_candles_drop_the_trailing_week_to_date_candle(self):
        # Weekly candles close on Sundays; the bundle then appends the current
        # week-to-date two days later, which made every candle seven times thinner.
        weekly_days = [0] + [7] * 9 + [2]  # t0 is Sunday 2026-01-04

        def series(key, base):
            return {"series_key": key, "pd": {"t0": 1767484800000, "d": weekly_days, "v": [base + i for i in range(11)]}}

        ohlc = {"slug": "ohlc", "name": "Price OHLC", "style_config": {"ohlcChart": True},
                "axis_config": {"x": {"min": "2026-01-01"}},
                "series": [series("open", 100), series("high", 110), series("low", 90), series("close", 105)]}
        payload = data._build_payload(ohlc, chart("price", "Price"), "2026-03-11T00:12:20+00:00")
        candles = payload["series"][0]
        self.assertEqual(candles["x"][-1], "2026-03-08")
        self.assertEqual(len(candles["x"]), 10)
        self.assertEqual({len(candles[key]) for key in ("open", "high", "low", "close")}, {10})
        self.assertEqual(candles["close"][-1], 114, "the last complete week is kept")
        self.assertEqual(set(data._day_gaps(candles["x"])), {7}, "candles are evenly spaced")
        self.assertEqual(payload["native_resolution"], "weekly")
        # The viewport ends half a candle after the latest candle so its body is not clipped.
        self.assertEqual(payload["layout"]["xaxis"]["range"], ["2026-01-01", "2026-03-12"])

    def test_partial_candle_detection_uses_the_sunday_week_and_build_date(self):
        def keep(dates, built_at=None):
            columns = {"x": dates, "open": list(range(len(dates)))}
            return data._without_partial_period(columns, built_at)["x"]

        # A missing week in the history does not make a completed Sunday look partial.
        self.assertEqual(keep(["2026-01-04", "2026-01-18", "2026-01-25"]), ["2026-01-04", "2026-01-18", "2026-01-25"])
        self.assertEqual(keep(["2025-12-07", "2025-12-14", "2026-01-04", "2026-01-18", "2026-01-25"], "2026-01-26T01:00:00+00:00"),
                         ["2025-12-07", "2025-12-14", "2026-01-04", "2026-01-18", "2026-01-25"])
        # Sunday then a Monday week-to-date: the Monday candle is partial even with one complete week.
        self.assertEqual(keep(["2026-01-04", "2026-01-05"], "2026-01-05T06:00:00Z"), ["2026-01-04"])
        # Ending mid-week is partial (with gaps in history too); ending on Sunday is complete.
        self.assertEqual(keep(["2026-01-04", "2026-01-11", "2026-01-13"], "2026-01-13T09:00:00+00:00"), ["2026-01-04", "2026-01-11"])
        self.assertEqual(keep(["2025-12-07", "2025-12-14", "2026-01-04", "2026-01-18", "2026-01-21"]),
                         ["2025-12-07", "2025-12-14", "2026-01-04", "2026-01-18"])
        # Without one consecutive week the cadence is unproven, so the candle is preserved.
        self.assertEqual(keep(["2026-01-04", "2026-01-18", "2026-01-21"]), ["2026-01-04", "2026-01-18", "2026-01-21"])
        self.assertEqual(keep(["2026-01-04", "2026-01-11", "2026-01-18"], "2026-01-19T00:00:00Z"), ["2026-01-04", "2026-01-11", "2026-01-18"])
        # A single candle, or a week that had already ended at build time, is preserved.
        self.assertEqual(keep(["2026-01-13"]), ["2026-01-13"])
        self.assertEqual(keep(["2026-01-04", "2026-01-11", "2026-01-13"], "2026-01-20T00:00:00Z"), ["2026-01-04", "2026-01-11", "2026-01-13"])
        # Series that do not follow the Sunday-ending weekly convention are preserved.
        self.assertEqual(keep(["2026-01-07", "2026-01-14", "2026-01-16"]), ["2026-01-07", "2026-01-14", "2026-01-16"])
        self.assertEqual(keep(["2026-01-01", "2026-01-02", "2026-01-03"]), ["2026-01-01", "2026-01-02", "2026-01-03"])
        self.assertEqual(keep(["2025-11-30", "2026-01-04", "2026-02-01", "2026-02-03"]), ["2025-11-30", "2026-01-04", "2026-02-01", "2026-02-03"])
        # Every column is trimmed together and unparseable input is left alone.
        trimmed = data._without_partial_period({"x": ["2026-01-04", "2026-01-11", "2026-01-12"], "open": [1, 2, 3], "close": [4, 5, 6]})
        self.assertEqual(trimmed, {"x": ["2026-01-04", "2026-01-11"], "open": [1, 2], "close": [4, 5]})
        odd = {"x": ["2026-01-04", None], "open": [1, 2]}
        self.assertEqual(data._without_partial_period(odd), odd)

    def test_native_resolution_names_the_finest_date_cadence(self):
        def trace(step, count=12):
            start = data.datetime(2020, 1, 1)
            return {"x": [(start + data.timedelta(days=step * index)).strftime("%Y-%m-%d") for index in range(count)]}

        self.assertEqual(data._native_resolution([trace(7)]), "weekly")
        self.assertEqual(data._native_resolution([trace(7), trace(1)]), "daily")
        self.assertEqual(data._native_resolution([trace(31)]), "monthly")
        self.assertEqual(data._native_resolution([trace(91)]), "quarterly")
        self.assertEqual(data._native_resolution([trace(365)]), "yearly")
        self.assertIsNone(data._native_resolution([{"x": ["2020-01-01"]}, {"x": ["Q1", "Q2", "Q3"]}]))
        # Every imported payload declares it, deterministically and without wall-clock time.
        first = data._build_payload(chart("mvrv", "MVRV"), chart("price", "Price"), None)
        second = data._build_payload(chart("mvrv", "MVRV"), chart("price", "Price"), None)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertIn("native_resolution", first)

    @unittest.skipUnless(os.environ.get("FINTECH_LIVE_TESTS") == "1", "opt-in upstream integration check")
    def test_current_bundle_rebuilds_the_entire_reviewed_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            entries = data.import_reference_charts(directory, lambda value: value)
            expected = set(data.REFERENCE_CHARTS) - set(data.REFERENCE_EQUIVALENTS)
            self.assertEqual({entry["id"] for entry in entries}, expected)
            self.assertEqual(len(entries), 149)
            for entry in entries:
                payload = json.loads((directory / f"{entry['id']}.json").read_text(encoding="utf-8"))
                self.assertTrue(payload["series"], entry["id"])
                self.assertTrue(any(series.get("x") for series in payload["series"]), entry["id"])
                self.assertEqual(payload["id"], entry["id"])
                self.assertEqual(payload["title"], entry["title"])


if __name__ == "__main__":
    unittest.main()
