"""Deterministic payloads: stable timestamps, compact output, bounded precision loss."""

import importlib.util
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from web import generate_site  # noqa: E402

with patch("dotenv.load_dotenv"):
    _spec = importlib.util.spec_from_file_location("fintech_runner_fp", ROOT / "run.py")
    runner = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(runner)


def fixture_frame(extra_day=False):
    frame = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=30 + int(extra_day), freq="D"),
        "Price": 100_000.0,
        "Estimated_Hashrate_EH_S": 1_000.0,
        "Miner_Revenue_USD": 50_000_000.0,
    })
    return frame


def generate(directory: Path, frame):
    with patch.object(generate_site, "load_market_frame", return_value=frame):
        payload = generate_site.build_miner_hashprice()
    generate_site.write_json(directory / "web" / "data" / "bitcoin" / "miner-hashprice.json", payload)
    generate_site.write_json(
        directory / "web" / "data" / "site-manifest.json",
        {"generated_at": f"generated-{time.time_ns()}", "charts": [payload["id"]]},
    )
    (directory / "index.html").write_text("<html></html>", encoding="utf-8")
    return payload


class DeterministicGenerationTests(unittest.TestCase):
    def test_generating_twice_from_one_fixture_gives_identical_files_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first = generate(Path(one), fixture_frame())
            time.sleep(0.01)
            second = generate(Path(two), fixture_frame())
            self.assertEqual(first["updated_at"], second["updated_at"])
            self.assertEqual(first["updated_at"], "2026-01-30T00:00:00+00:00")
            chart = Path("web/data/bitcoin/miner-hashprice.json")
            self.assertEqual((Path(one) / chart).read_bytes(), (Path(two) / chart).read_bytes())
            self.assertEqual(
                runner.static_site_fingerprint(Path(one), "gh-pages"),
                runner.static_site_fingerprint(Path(two), "gh-pages"),
            )

    def test_new_observation_changes_the_fingerprint(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            generate(Path(one), fixture_frame())
            generate(Path(two), fixture_frame(extra_day=True))
            self.assertNotEqual(
                runner.static_site_fingerprint(Path(one), "gh-pages"),
                runner.static_site_fingerprint(Path(two), "gh-pages"),
            )

    def test_payload_without_dates_has_no_wall_clock_timestamp(self):
        payload = generate_site.base_payload("x", "X", "", [{"x": [1, 2], "y": [1, 2]}], {})
        self.assertIsNone(payload["updated_at"])


class CompactOutputTests(unittest.TestCase):
    def test_output_is_compact_sorted_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "p.json"
            generate_site.write_json(path, {"b": [1, 2.5], "a": {"y": None}})
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text, '{"a":{"y":null},"b":[1,2.5]}\n')

    def test_float_rounding_keeps_chart_precision(self):
        rng = random.Random(7)
        prices = [round(rng.uniform(0.01, 125_000), 8) for _ in range(5000)]
        tiny = [rng.uniform(1e-9, 1e-3) for _ in range(500)]
        ratios = [rng.uniform(-3, 3) for _ in range(500)]
        x_values = [1_700_000_000.123456 + index for index in range(10)]  # numeric axis stays exact
        payload = {"series": [{"x": x_values, "y": prices + tiny + ratios, "count": 12345}]}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "p.json"
            generate_site.write_json(path, payload)
            loaded = json.loads(path.read_text(encoding="utf-8"))
        series = loaded["series"][0]
        self.assertEqual(series["x"], x_values)
        self.assertEqual(series["count"], 12345)
        for original, stored in zip(payload["series"][0]["y"], series["y"]):
            self.assertLessEqual(abs(stored - original), abs(original) * 5e-7 + 1e-300)
        # A $100k price keeps whole cents/dimes: error far below a pixel on any axis.
        self.assertLess(abs(float(json.dumps(generate_site.compact_floats(67123.456789))) - 67123.456789), 0.01)

    def test_special_values_are_left_for_existing_null_handling(self):
        self.assertTrue(math.isnan(generate_site.compact_floats(float("nan"))))
        self.assertEqual(generate_site.compact_floats([0.0, -0.0, 1, None, "s"]), [0.0, -0.0, 1, None, "s"])

    def test_compact_output_is_much_smaller_than_the_old_indented_form(self):
        rng = random.Random(1)
        payload = {"series": [{"x": ["2026-01-01"] * 2000, "y": [rng.uniform(1, 1e5) for _ in range(2000)]}]}
        old = json.dumps(payload, indent=2, separators=(",", ": "))
        new = json.dumps(generate_site.compact_floats(payload), sort_keys=True, separators=(",", ":"))
        self.assertLess(len(new), len(old) * 0.6)


if __name__ == "__main__":
    unittest.main()
