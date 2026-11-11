#!/usr/bin/env python3
"""Regenerate the shared signal fixture.

``charts.json`` holds small synthetic chart payloads (including shifted,
missing and duplicated dates) and ``expected.json`` is the artifact the Python
builder produces for them.  Python and browser-logic tests both compare
against ``expected.json``, which keeps the two implementations in agreement.

    python web/tests/fixtures/signals/make_fixture.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FIXTURE_DIR.parents[2]))

from signals_artifact import build_signals_artifact  # noqa: E402

GENERATED_AT = "2025-01-02T00:00:00+00:00"
START = date(2024, 6, 1)
DAYS = 200


class Walk:
    """Small deterministic generator; avoids depending on a random module."""

    def __init__(self, seed: int):
        self.state = seed

    def step(self) -> float:
        self.state = (self.state * 1103515245 + 12345) % 2147483648
        return self.state / 2147483648 - 0.5


def iso(offset: int) -> str:
    return (START + timedelta(days=offset)).isoformat()


def walk(seed: int, length: int, start: float, scale: float, decimals: int = 4) -> list[float]:
    generator = Walk(seed)
    value = start
    values = []
    for _ in range(length):
        value = max(start * 0.2, value + generator.step() * scale)
        values.append(round(value, decimals))
    return values


def series(name: str, x: list[str], y: list, key: str | None = None) -> dict:
    item = {"name": name, "type": "scatter", "x": x, "y": y}
    if key is not None:
        item["source_key"] = key
    return item


def build_charts() -> dict:
    daily = [iso(index) for index in range(DAYS)]
    price = walk(7, DAYS, 60000, 2500, 2)
    average = walk(11, DAYS, 58000, 400, 2)

    # Weekly source with a trailing daily observation, like the imported bundle.
    weekly_offsets = list(range(0, DAYS - 1, 7)) + [DAYS - 2]
    weekly_x = [iso(offset) for offset in weekly_offsets]
    weekly_price = [price[offset] for offset in weekly_offsets]
    realized = walk(13, len(weekly_offsets), 42000, 600, 2)
    nupl = [round(1 - realized[index] / weekly_price[index], 12) for index in range(len(weekly_offsets))]
    # The denominator arrives shifted (missing its first row), with one row
    # duplicated by a stale value followed by the corrected value.
    denominator_x = weekly_x[1:9] + [weekly_x[9], weekly_x[9]] + weekly_x[10:]
    denominator_y = realized[1:9] + [1.0, realized[9]] + realized[10:]

    lower = [round(value * 0.94, 2) for value in average]
    upper = [round(value * 1.07, 2) for value in average]
    # Bands are published in a different order and miss a row; the price
    # series contains a null and a duplicated date.
    band_price_x = daily[:50] + [daily[50], daily[50]] + daily[51:]
    band_price_y = price[:50] + [None, price[50]] + price[51:]
    band_lower_x = daily[:120] + daily[121:]
    band_lower_y = lower[:120] + lower[121:]

    days_since = []
    peak = 0.0
    last_peak = 0
    for index, value in enumerate(price):
        if value >= peak:
            peak, last_peak = value, index
        days_since.append(index - last_peak)

    return {
        "plain-chart": {"id": "plain-chart", "series": [series("Metric", daily, walk(3, DAYS, 2.0, 0.3))]},
        "trend-chart": {"id": "trend-chart", "series": [series("BTC price", daily, price), series("200D MA", daily, average)]},
        "weekly-chart": {
            "id": "weekly-chart",
            "series": [
                series("BTC price", weekly_x, weekly_price, "price"),
                series("Realized Price", denominator_x, denominator_y, "realized_price"),
                series("NUPL", weekly_x, nupl, "nupl"),
            ],
        },
        "band-chart": {
            "id": "band-chart",
            "series": [
                series("Upper band", daily, upper),
                series("Lower band", band_lower_x, band_lower_y),
                series("BTC price", band_price_x, band_price_y),
            ],
        },
        "ath-chart": {"id": "ath-chart", "series": [series("BTC price", daily, price), series("Days since ATH", daily, days_since)]},
        "young-chart": {"id": "young-chart", "series": [series("Young", daily[-100:], walk(17, 100, 40.0, 6.0, 2))]},
        "lagging-chart": {"id": "lagging-chart", "series": [series("Lagging", daily[:-5], walk(19, DAYS - 5, 0.05, 0.004, 5))]},
        "abandoned-chart": {"id": "abandoned-chart", "series": [series("Abandoned", daily[:-40], walk(23, DAYS - 40, 3.0, 0.5))]},
        "short-chart": {"id": "short-chart", "series": [series("Short", daily[-40:], walk(29, 40, 1.0, 0.1))]},
    }


def main() -> int:
    definitions = json.loads((FIXTURE_DIR / "definitions.json").read_text(encoding="utf-8"))
    charts = build_charts()
    (FIXTURE_DIR / "charts.json").write_text(json.dumps(charts, separators=(",", ":")) + "\n", encoding="utf-8")
    expected = build_signals_artifact(definitions, charts.get, GENERATED_AT)
    (FIXTURE_DIR / "expected.json").write_text(json.dumps(expected, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote fixture: {len(expected['signals'])} signals, {len(expected['unavailable'])} unavailable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
