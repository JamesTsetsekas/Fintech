"""Colour sanitisation, deterministic timestamps, and conditional bundle fetch."""

import io
import json
from email.message import Message
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from web import blockhorizon_data as data

HOSTILE = 'red" onmouseover="alert(1)'


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


class ColourSanitisationTests(unittest.TestCase):
    def test_safe_colour_accepts_only_strict_literals(self):
        for good in ("#abc", "#AABBCC", "#aabbccdd", "rgb(255,0,0)", "rgba(0, 0, 0, .5)",
                     "hsl(120, 50%, 50%)", "hsla(120, 50%, 50%, 0.4)"):
            self.assertEqual(data._safe_color(good, "x"), good)
        for bad in (HOSTILE, "red", "#abcd", "#ggg", "rgb(1,2)", "rgb(1,2,3", "var(--x)", "", None, 5,
                    "#fff\n;", "expression(alert(1))", "url(javascript:alert(1))",
                    "#fff;background:url(x)", 'rgb(1,2,3)"><img src=x>'):
            self.assertEqual(data._safe_color(bad, "x"), "x", bad)

    def test_hostile_series_colours_fall_back_to_the_palette(self):
        for bad in (HOSTILE, "url(javascript:alert(1))", "#fff;background:url(x)", "<b>"):
            with self.subTest(bad=bad):
                metric = chart("fees-total", "Fees Total")
                series = metric["series"][0]
                series["color"] = bad
                metric["style_config"] = {"seriesTypes": {"metric": {"color": bad}}}
                trace = data._line_trace(metric, series, 0)
                self.assertEqual(trace["line"]["color"], data.PALETTE[0])

    def test_negative_colour_and_point_colours_are_sanitised(self):
        metric = chart("fees-total", "Fees Total", value=-1)
        series = metric["series"][0]
        series["color"] = "#112233"
        series["pd"]["x"] = {"0": {"color": HOSTILE}, "1": {"color": "rgb(1, 2, 3)"}}
        metric["style_config"] = {"seriesTypes": {"metric": {
            "type": "column", "threshold": 0, "negativeColor": HOSTILE, "color": "#00ff00",
        }}}
        bar = data._line_trace(metric, series, 0)
        self.assertEqual(bar["marker"]["color"], "#00ff00")  # hostile negativeColor is dropped
        metric["style_config"]["seriesTypes"]["metric"]["negativeColor"] = "hsl(10, 50%, 40%)"
        bar = data._line_trace(metric, series, 0)
        self.assertEqual(bar["marker"]["color"], ["hsl(10, 50%, 40%)", "#00ff00"])
        line = data._line_trace({**metric, "style_config": {}}, series, 0)
        self.assertEqual(line["marker"]["color"], ["#112233", "rgb(1, 2, 3)"])
        for item in (bar, line):
            self.assertNotIn("onmouseover", json.dumps(item))

    def test_full_payload_contains_no_hostile_colour(self):
        metric = chart("fees-total", "Fees Total")
        metric["series"][0]["color"] = HOSTILE
        metric["style_config"] = {
            "seriesTypes": {"metric": {"type": "area", "color": HOSTILE, "negativeColor": HOSTILE}},
            "valueZones": [{"seriesKey": "metric", "greenBelow": 1, "fillColor": HOSTILE}],
        }
        payload = data._build_payload(metric, chart("price", "Price"), None)
        self.assertNotIn("onmouseover", json.dumps(payload))

    def test_heatmap_stops_and_value_zones_cannot_carry_hostile_colours(self):
        heat = chart("fees-total", "Fees Total")
        heat["style_config"] = {"heatmap": {"stops": [[0, "#000"], [1, HOSTILE]]}}
        self.assertEqual(
            data._heatmap_trace(heat)[0]["colorscale"], [[0, "#2863a7"], [0.5, "#fffefa"], [1, "#c91f50"]]
        )
        heat["style_config"]["heatmap"]["stops"] = [[0, "#000"], [1, "rgba(1,2,3,0.5)"]]
        self.assertEqual(data._heatmap_trace(heat)[0]["colorscale"], [[0.0, "#000"], [1.0, "rgba(1,2,3,0.5)"]])
        zones = data._sanitize_color_fields([{"seriesKey": "k", "fillColor": HOSTILE, "greenBelow": 1}])
        self.assertEqual(zones, [{"seriesKey": "k", "fillColor": "#888888", "greenBelow": 1}])


class DeterministicTimestampTests(unittest.TestCase):
    def test_updated_at_without_source_timestamp_comes_from_the_data(self):
        first = data._build_payload(chart("fees-total", "Fees Total"), chart("price", "Price"), None)
        second = data._build_payload(chart("fees-total", "Fees Total"), chart("price", "Price"), None)
        self.assertEqual(first["updated_at"], second["updated_at"])
        self.assertTrue(first["updated_at"].startswith("2026-01-02"))


class _Response:
    def __init__(self, body, headers):
        self._body, self.headers = body, headers

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_304(headers=None):
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return HTTPError(data.SOURCE_BUNDLE_URL, 304, "Not Modified", message, io.BytesIO(b""))


class BundleFetchTests(unittest.TestCase):
    BODY = json.dumps([chart("price", "Price")]).encode()

    def test_second_fetch_sends_if_none_match_and_reuses_bundle_on_304(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            ok = _Response(self.BODY, {"ETag": '"v1"', "X-Bundle-Built-At": "2026-10-20T00:00:00Z"})
            with patch.object(data, "urlopen", return_value=ok) as opened:
                bundle, built_at = data._fetch_bundle(cache_dir=cache)
            self.assertIsNone(opened.call_args[0][0].get_header("If-none-match"))
            self.assertEqual((bundle[0]["slug"], built_at), ("price", "2026-10-20T00:00:00Z"))
            with patch.object(data, "urlopen", side_effect=_http_304()) as opened:
                bundle, built_at = data._fetch_bundle(cache_dir=cache)
            self.assertEqual(opened.call_args[0][0].get_header("If-none-match"), '"v1"')
            self.assertEqual((bundle[0]["slug"], built_at), ("price", "2026-10-20T00:00:00Z"))

    def test_304_without_a_valid_cache_is_an_error(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(data, "urlopen", side_effect=_http_304()):
            with self.assertRaises(HTTPError):
                data._fetch_bundle(cache_dir=Path(temporary))

    def test_corrupt_cache_is_ignored_and_never_sent_as_a_validator(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            ok = _Response(self.BODY, {"ETag": '"v1"'})
            with patch.object(data, "urlopen", return_value=ok):
                data._fetch_bundle(cache_dir=cache)
            (cache / "bundle.json").write_bytes(self.BODY[:-5])  # truncated cache
            with patch.object(data, "urlopen", return_value=ok) as opened:
                data._fetch_bundle(cache_dir=cache)
            self.assertIsNone(opened.call_args[0][0].get_header("If-none-match"))

    def test_partial_or_invalid_download_is_never_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            for body in (self.BODY[:-5], b"{}"):
                with patch.object(data, "urlopen", return_value=_Response(body, {"ETag": '"bad"'})):
                    with self.assertRaises(ValueError):
                        data._fetch_bundle(cache_dir=cache)
            self.assertFalse((cache / "bundle.json").exists())
            self.assertFalse((cache / "bundle.meta.json").exists())

    def test_network_failure_does_not_fall_back_to_a_stale_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            with patch.object(data, "urlopen", return_value=_Response(self.BODY, {"ETag": '"v1"'})):
                data._fetch_bundle(cache_dir=cache)
            with patch.object(data, "urlopen", side_effect=OSError("offline")):
                with self.assertRaises(OSError):
                    data._fetch_bundle(cache_dir=cache)


if __name__ == "__main__":
    unittest.main()
