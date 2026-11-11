"""Color validation, conditional bundle fetch, and deterministic payload timestamps."""

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from web import blockhorizon_data as data
from web import generate_site

PRICE = {"slug": "price", "name": "Price", "series": [{
    "id": 1, "series_key": "price", "name": "Price",
    "pd": {"t0": 1767225600000, "d": [0, 1], "v": [1, 2]},
}]}
MALICIOUS = 'red" onmouseover="alert(1)'


def metric(**style):
    return {
        "slug": "metric", "name": "Metric",
        "style_config": {"seriesTypes": {"metric": style}},
        "series": [{
            "id": 1, "series_key": "metric", "name": "Metric", "color": MALICIOUS,
            "pd": {"t0": 1767225600000, "d": [0, 1], "v": [-1, 2]},
        }],
    }


class ColorValidationTests(unittest.TestCase):
    def test_accepts_plain_css_color_literals(self):
        for value in ("#abc", "#abcd", "#a1b2c3", "#a1b2c3d4", "rgb(1, 2, 3)", "rgba(1,2,3,.5)",
                      "rgb(1 2 3 / 50%)", "hsl(120, 50%, 40%)", "hsla(120deg, 50%, 40%, 0.3)"):
            with self.subTest(value=value):
                self.assertEqual(data._safe_color(value, "#000000"), value)

    def test_rejects_anything_else(self):
        for value in (MALICIOUS, "red", "#12", "#12345", "#gggggg", "url(javascript:alert(1))",
                      "rgb(1,2,3);x", 'rgb(1,2,3)" onload="x', "rgb(1,2)", "<b>", "", None, 5, ["#fff"],
                      "#fff" + " " * 80):
            with self.subTest(value=value):
                self.assertEqual(data._safe_color(value, "FALLBACK"), "FALLBACK")

    def test_malicious_series_and_negative_colors_fall_back_to_the_palette(self):
        chart = metric(type="column", threshold=0, negativeColor=MALICIOUS, color=MALICIOUS)
        trace = data._line_trace(chart, chart["series"][0], 0)
        self.assertEqual(trace["marker"]["color"], data.PALETTE[0])
        self.assertNotIn("onmouseover", json.dumps(trace))

    def test_valid_negative_color_is_kept(self):
        chart = metric(type="column", threshold=0, negativeColor="#c91f50", color="#16844d")
        trace = data._line_trace(chart, chart["series"][0], 0)
        self.assertEqual(trace["marker"]["color"], ["#c91f50", "#16844d"])

    def test_line_area_and_point_colors_are_sanitized(self):
        for kind in ("line", "area"):
            chart = metric(type=kind, color=MALICIOUS)
            trace = data._line_trace(chart, chart["series"][0], 2)
            self.assertNotIn("onmouseover", json.dumps(trace))
            self.assertEqual(trace["line"]["color"], data.PALETTE[2])
        chart = metric()
        chart["series"][0]["pd"]["x"] = {"0": {"color": MALICIOUS}, "1": {"color": "#112233"}}
        trace = data._line_trace(chart, chart["series"][0], 0)
        self.assertEqual(trace["marker"]["color"], [data.PALETTE[0], "#112233"])

    def test_heatmap_stops_are_validated(self):
        chart = {"slug": "h", "name": "H", "style_config": {"heatmap": {"stops": [[0, MALICIOUS], [1, "#fff"]]}},
                 "series": PRICE["series"]}
        self.assertEqual(data._heatmap_trace(chart)[0]["colorscale"][0], [0, "#2863a7"])
        chart["style_config"]["heatmap"]["stops"] = [[0, "#000"], [1, "rgb(1,2,3)"]]
        self.assertEqual(data._heatmap_trace(chart)[0]["colorscale"], [[0, "#000"], [1, "rgb(1,2,3)"]])

    def test_payload_updated_at_never_uses_the_wall_clock(self):
        payload = data._build_payload(metric(color="#fff"), PRICE, None)
        self.assertEqual(payload["updated_at"], payload["series"][0]["x"][-1])


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers):
        super().__init__(json.dumps(body).encode())
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class BundleCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / "logs" / "bundle.json"

    def test_first_fetch_caches_etag_and_next_fetch_is_conditional(self):
        sent = []

        def fake(request, timeout):
            sent.append(request.get_header("If-none-match"))
            if sent[-1] is None:
                return FakeResponse([{"slug": "a"}], {"ETag": '"v1"', "X-Bundle-Built-At": "2026-01-01T00:00:00Z"})
            raise HTTPError(request.full_url, 304, "Not Modified", {}, None)

        with patch.object(data, "urlopen", side_effect=fake):
            first = data._fetch_bundle(cache_path=self.cache)
            second = data._fetch_bundle(cache_path=self.cache)
        self.assertEqual(sent, [None, '"v1"'])
        self.assertEqual(first, ([{"slug": "a"}], "2026-01-01T00:00:00Z"))
        self.assertEqual(second, first)

    def test_changed_bundle_replaces_the_cache(self):
        replies = iter([
            FakeResponse([{"slug": "a"}], {"ETag": '"v1"'}),
            FakeResponse([{"slug": "b"}], {"ETag": '"v2"'}),
        ])
        with patch.object(data, "urlopen", side_effect=lambda request, timeout: next(replies)):
            data._fetch_bundle(cache_path=self.cache)
            bundle, _ = data._fetch_bundle(cache_path=self.cache)
        self.assertEqual(bundle, [{"slug": "b"}])
        self.assertEqual(json.loads(self.cache.read_text())["etag"], '"v2"')

    def test_304_without_a_usable_cache_and_other_errors_propagate(self):
        for code in (304, 500):
            with self.subTest(code=code), patch.object(
                data, "urlopen", side_effect=HTTPError("u", code, "x", {}, None)
            ), self.assertRaises(HTTPError):
                data._fetch_bundle(cache_path=self.cache)

    def test_corrupt_cache_is_ignored(self):
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text("{nope")
        seen = []

        def fake(request, timeout):
            seen.append(request.get_header("If-none-match"))
            return FakeResponse([{"slug": "a"}], {})

        with patch.object(data, "urlopen", side_effect=fake):
            data._fetch_bundle(cache_path=self.cache)
        self.assertEqual(seen, [None])

    def test_structurally_invalid_cache_is_not_trusted_on_304(self):
        for bundle in ([None], [], ["x"], {"a": 1}):
            with self.subTest(bundle=bundle):
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                self.cache.write_text(json.dumps({"etag": '"v1"', "built_at": None, "bundle": bundle}))
                seen = []

                def fake(request, timeout):
                    seen.append(request.get_header("If-none-match"))
                    return FakeResponse([{"slug": "fresh"}], {"ETag": '"v2"'})

                with patch.object(data, "urlopen", side_effect=fake):
                    result, _ = data._fetch_bundle(cache_path=self.cache)
                self.assertEqual(seen, [None])  # unconditional refetch, no If-None-Match
                self.assertEqual(result, [{"slug": "fresh"}])
                self.assertEqual(json.loads(self.cache.read_text())["etag"], '"v2"')

    def test_invalid_download_is_rejected_and_not_cached(self):
        with patch.object(data, "urlopen", return_value=FakeResponse([None], {"ETag": '"bad"'})):
            with self.assertRaises(ValueError):
                data._fetch_bundle(cache_path=self.cache)
        self.assertFalse(self.cache.exists())


class DeterministicPayloadTests(unittest.TestCase):
    def test_native_updated_at_is_latest_observation_and_stable(self):
        series = [
            generate_site.trace("a", pd.to_datetime(["2026-01-01", "2026-03-05"]), [1, 2], "#fff"),
            generate_site.trace("b", pd.to_datetime(["2026-02-01"]), [1], "#fff"),
        ]
        first = generate_site.base_payload("id", "T", "S", series, {})
        second = generate_site.base_payload("id", "T", "S", series, {})
        self.assertEqual(first["updated_at"], "2026-03-05")
        self.assertEqual(first, second)

    def test_non_date_series_have_no_timestamp(self):
        series = [generate_site.numeric_trace("a", [1, 2], [3, 4], "#fff")]
        payload = generate_site.base_payload("id", "T", "S", series, {}, x_value_type="number")
        self.assertIsNone(payload["updated_at"])

    def test_native_json_is_compact_and_reproducible(self):
        series = [generate_site.trace("a", pd.to_datetime(["2026-01-01"]), [1], "#fff")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "a.json"
            generate_site.write_json(path, generate_site.base_payload("id", "T", "S", series, {}))
            text = path.read_text(encoding="utf-8")
            generate_site.write_json(path, generate_site.base_payload("id", "T", "S", series, {}))
            self.assertEqual(text, path.read_text(encoding="utf-8"))
        self.assertNotIn("\n  ", text)
        self.assertEqual(text.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
