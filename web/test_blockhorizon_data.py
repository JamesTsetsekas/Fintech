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
