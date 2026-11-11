#!/usr/bin/env python3
"""Build the compact cycle-signal artifact (``signals.json``) for the site.

The dashboard, chart terminal, signals and alerts pages used to download every
signal's full chart payload and score it in the browser.  This module scores
the same definitions once at build time and publishes one small file next to
the site manifest.

``web/assets/signal-definitions.json`` is the single source for the signal
list, the scoring method and the Cycle Index membership.  The browser keeps a
port of this algorithm only as a fallback for a missing artifact; both are
pinned to the same golden fixture (``web/tests/fixtures/signals``).

The scoring code deliberately uses plain Python floats and the same operation
order as the browser port so both produce identical numbers.
"""

from __future__ import annotations

import json
import math
import re
import sys
from bisect import bisect_left, bisect_right, insort
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_NAME = "signals.json"
DEFINITIONS_PATH = Path(__file__).resolve().parent / "assets" / "signal-definitions.json"
_EPOCH = date(1970, 1, 1)
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")


class SignalUnavailable(Exception):
    """A definition could not be resolved against the available chart data."""


def load_definitions(path: Path = DEFINITIONS_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def to_day(value) -> int | None:
    """Return days since 1970-01-01 for an ISO date string, else ``None``."""
    if not isinstance(value, str) or not _DATE_PATTERN.match(value):
        return None
    try:
        return (date.fromisoformat(value[:10]) - _EPOCH).days
    except ValueError:
        return None


def from_day(day: int) -> str:
    return (_EPOCH + timedelta(days=day)).isoformat()


def finite_number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def round_decimals(value: float, decimals: int) -> float:
    factor = 10 ** decimals
    return math.floor(value * factor + 0.5) / factor


def round_score(value: float | None) -> float | None:
    return None if value is None else round_decimals(value, 1)


def round_significant(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return float(f"{value:.{digits}g}")


def select_series(payload, selector: dict):
    """Find a chart series by its stable source key or its display name."""
    series_list = payload.get("series") if isinstance(payload, dict) else None
    if not isinstance(series_list, list) or not isinstance(selector, dict):
        return None
    for series in series_list:
        if not isinstance(series, dict):
            continue
        if "key" in selector and series.get("source_key") == selector["key"]:
            return series
        if "name" in selector and series.get("name") == selector["name"]:
            return series
    return None


def describe_selector(selector) -> str:
    if isinstance(selector, dict) and "key" in selector:
        return f"source key '{selector['key']}'"
    if isinstance(selector, dict) and "name" in selector:
        return f"series '{selector['name']}'"
    return "an unspecified series"


def series_by_day(series) -> dict[int, float]:
    """Map observation day to value.  A later duplicate date supersedes an
    earlier one; missing or non-finite observations never erase a real one."""
    x_values = series.get("x") if isinstance(series, dict) else None
    y_values = series.get("y") if isinstance(series, dict) else None
    if not isinstance(x_values, list) or not isinstance(y_values, list):
        return {}
    by_day = {}
    for index in range(min(len(x_values), len(y_values))):
        day = to_day(x_values[index])
        value = finite_number(y_values[index])
        if day is None or value is None:
            continue
        by_day[day] = value
    return by_day


def _required_series(payload, selector, chart_id) -> dict[int, float]:
    series = select_series(payload, selector)
    if series is None:
        raise SignalUnavailable(f"{describe_selector(selector)} is missing from chart '{chart_id}'")
    return series_by_day(series)


def resolve_observations(definition: dict, payload) -> list[tuple[int, float]]:
    """Return a signal's dated raw observations, oldest first.

    Derived indicators are joined on the observation date, never on array
    position, so a shifted, missing or duplicated row cannot pair a numerator
    with another day's denominator.
    """
    chart_id = definition.get("chart_id")
    if not isinstance(payload, dict):
        raise SignalUnavailable(f"chart data for '{chart_id}' is unavailable")
    source = definition.get("input") or {}
    kind = source.get("type")
    if kind == "series":
        values = _required_series(payload, source.get("series"), chart_id)
        return sorted(values.items())
    if kind == "ratio":
        numerator = _required_series(payload, source.get("numerator"), chart_id)
        denominator = _required_series(payload, source.get("denominator"), chart_id)
        observations = []
        for day in sorted(numerator):
            divisor = denominator.get(day)
            if divisor is None or divisor == 0:
                continue
            observations.append((day, numerator[day] / divisor))
        return observations
    if kind == "band_position":
        value = _required_series(payload, source.get("value"), chart_id)
        lower = _required_series(payload, source.get("lower"), chart_id)
        upper = _required_series(payload, source.get("upper"), chart_id)
        observations = []
        for day in sorted(value):
            low = lower.get(day)
            high = upper.get(day)
            if low is None or high is None or high == low:
                continue
            observations.append((day, (value[day] - low) / (high - low)))
        return observations
    raise SignalUnavailable(f"unsupported input type '{kind}'")


def expanding_scores(observations, scoring: dict, invert: bool = False) -> list[float | None]:
    """Point-in-time percentile rank of each observation within its history.

    The score for an observation only uses observations up to and including
    its own date (an expanding window), with ties at mid-rank.  Observations
    inside the warm-up period are unscored.
    """
    min_days = scoring.get("min_history_days", 0)
    min_observations = scoring.get("min_observations", 1)
    ordered: list[float] = []
    scores: list[float | None] = []
    first_day = observations[0][0] if observations else 0
    for day, value in observations:
        insort(ordered, value)
        count = len(ordered)
        if day - first_day < min_days or count < min_observations:
            scores.append(None)
            continue
        below = bisect_left(ordered, value)
        equal = bisect_right(ordered, value) - below
        rank = 100 * (below + 0.5 * equal) / count
        scores.append(100 - rank if invert else rank)
    return scores


def as_of_index(days: list[int], target: int, carry_forward_days: int) -> int | None:
    """Index of the latest observation on or before ``target`` that is still
    recent enough to stand in for it."""
    index = bisect_right(days, target) - 1
    if index < 0 or target - days[index] > carry_forward_days:
        return None
    return index


def phase_for(score: float | None, phases: list[dict]) -> str | None:
    if score is None:
        return None
    for phase in phases:
        if phase.get("below") is None or score < phase["below"]:
            return phase["key"]
    return phases[-1]["key"] if phases else None


def _build_market(market: dict | None, payload_for, carry_forward_days: int):
    if not isinstance(market, dict):
        return None
    try:
        payload = payload_for(market.get("chart_id"))
        if not isinstance(payload, dict):
            return None
        prices = _required_series(payload, market.get("price"), market.get("chart_id"))
        averages = _required_series(payload, market.get("average"), market.get("chart_id"))
    except SignalUnavailable:
        return None
    days = sorted(prices)
    if not days:
        return None
    latest_day = days[-1]
    price = prices[latest_day]
    average = averages.get(latest_day)
    month_index = as_of_index(days, latest_day - 30, carry_forward_days)
    month_price = prices[days[month_index]] if month_index is not None else None
    recent_days = days[-int(market.get("recent_observations", 60)):]
    return {
        "date": from_day(latest_day),
        "price": round_decimals(price, 2),
        "change_30d_pct": round_decimals((price / month_price - 1) * 100, 2) if month_price else None,
        "average_200d": round_decimals(average, 2) if average is not None else None,
        "distance_200d_pct": round_decimals((price / average - 1) * 100, 2) if average else None,
        "recent": {
            "dates": [from_day(day) for day in recent_days],
            "prices": [round_decimals(prices[day], 2) for day in recent_days],
            "ratios": [
                round_decimals(prices[day] / averages[day], 4) if averages.get(day) else None
                for day in recent_days
            ],
        },
    }


def build_signals_artifact(definitions: dict, load_payload, generated_at: str | None = None) -> dict:
    """Score every definition and return the publishable artifact.

    ``load_payload(chart_id)`` returns a chart payload dict, or ``None`` when
    the chart has no data.  Definitions that cannot be resolved are reported
    under ``unavailable`` instead of being dropped silently.
    """
    method = definitions["method"]
    scoring = method["scoring"]
    phases = method["phases"]
    windows = method["change_windows_days"]
    history_config = method["history"]
    step_days = history_config["step_days"]
    carry = history_config["carry_forward_days"]
    digits = history_config["value_significant_digits"]
    source_rules = method["freshness"]["sources"]
    composite_config = method["composite"]

    payloads = {}

    def payload_for(chart_id):
        if chart_id not in payloads:
            try:
                payloads[chart_id] = load_payload(chart_id)
            except (OSError, ValueError):
                payloads[chart_id] = None
        return payloads[chart_id]

    resolved = []
    unavailable = []
    for definition in definitions["signals"]:
        try:
            observations = resolve_observations(definition, payload_for(definition["chart_id"]))
            if not observations:
                raise SignalUnavailable("no finite observations")
            scores = expanding_scores(observations, scoring, bool(definition.get("invert")))
            if scores[-1] is None:
                raise SignalUnavailable("history is shorter than the scoring minimum")
        except SignalUnavailable as reason:
            unavailable.append({
                "id": definition["id"],
                "chart_id": definition["chart_id"],
                "label": definition["label"],
                "composite": bool(definition.get("composite")),
                "reason": str(reason),
            })
            continue
        resolved.append({
            "definition": definition,
            "days": [day for day, _ in observations],
            "values": [value for _, value in observations],
            "scores": scores,
        })

    market = _build_market(definitions.get("market"), payload_for, carry)
    latest_days = [item["days"][-1] for item in resolved]
    if market:
        latest_days.append(to_day(market["date"]))
    data_through = max(latest_days) if latest_days else None

    grid = []
    if resolved:
        first_scored = min(
            item["days"][next(index for index, score in enumerate(item["scores"]) if score is not None)]
            for item in resolved
        )
        day = data_through
        while day >= first_scored:
            grid.append(day)
            day -= step_days
        grid.reverse()

    def sample(item, key, target):
        index = as_of_index(item["days"], target, carry)
        return None if index is None else item[key][index]

    signals = []
    for item in resolved:
        definition = item["definition"]
        days, values, scores = item["days"], item["values"], item["scores"]
        latest_day = days[-1]
        changes = {}
        for window in windows:
            earlier = sample(item, "scores", latest_day - window)
            changes[str(window)] = None if earlier is None else round_score(scores[-1] - earlier)
        lag_days = data_through - latest_day
        stale_after = (source_rules.get(definition.get("source")) or {}).get("stale_after_days", 2)
        score = round_score(scores[-1])
        entry = {
            "id": definition["id"],
            "chart_id": definition["chart_id"],
            "label": definition["label"],
            "category": definition["category"],
            "source": definition.get("source"),
            "unit": definition.get("unit"),
            "decimals": definition.get("decimals"),
            "invert": bool(definition.get("invert")),
            "value": round_decimals(values[-1], 6),
            "date": from_day(latest_day),
            "score": score,
            "phase": phase_for(score, phases),
            "changes": changes,
            "lag_days": lag_days,
            "stale": lag_days > stale_after,
            "composite": bool(definition.get("composite")),
            "exclusion": definition.get("exclusion"),
            "first_date": from_day(days[0]),
            "observations": len(days),
            "history": {
                "scores": [round_score(sample(item, "scores", day)) for day in grid],
                "values": [round_significant(sample(item, "values", day), digits) for day in grid],
            },
        }
        signals.append(entry)

    members = [item for item in resolved if item["definition"].get("composite")]
    member_ids = [definition["id"] for definition in definitions["signals"] if definition.get("composite")]
    min_members = composite_config["min_members"]

    def composite_at(target):
        total = 0.0
        used = []
        for item in members:
            score = sample(item, "scores", target)
            if score is None:
                continue
            total += score
            used.append(item["definition"]["id"])
        if not used or len(used) < min_members:
            return None, used
        return total / len(used), used

    composite = None
    if data_through is not None:
        current, used = composite_at(data_through)
        composite_changes = {}
        for window in windows:
            earlier, _ = composite_at(data_through - window)
            composite_changes[str(window)] = (
                None if current is None or earlier is None else round_score(current - earlier)
            )
        score = round_score(current)
        composite = {
            "id": composite_config["id"],
            "label": composite_config["label"],
            "chart_id": composite_config.get("chart_id"),
            "date": from_day(data_through),
            "score": score,
            "phase": phase_for(score, phases),
            "changes": composite_changes,
            "members_total": len(member_ids),
            "members_used": len(used),
            "missing_members": [member for member in member_ids if member not in used],
            "stale_members": [entry["id"] for entry in signals if entry["composite"] and entry["stale"]],
            "history": {"scores": [round_score(composite_at(day)[0]) for day in grid]},
        }

    published_method = json.loads(json.dumps(method))
    published_method["composite"]["members"] = member_ids
    published_method["composite"]["excluded"] = [
        {"id": definition["id"], **(definition.get("exclusion") or {})}
        for definition in definitions["signals"]
        if not definition.get("composite")
    ]
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "data_through": None if data_through is None else from_day(data_through),
        "method": published_method,
        "market": market,
        "composite": composite,
        "history": {"dates": [from_day(day) for day in grid]},
        "signals": signals,
        "unavailable": unavailable,
    }


def directory_payload_loader(data_dir: Path):
    """Read the same per-chart JSON files the browser would have fetched."""
    def load(chart_id):
        path = Path(data_dir) / f"{chart_id}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    return load


def write_signals_artifact(data_dir: Path, definitions: dict | None = None) -> dict:
    """Build and atomically publish ``signals.json`` into ``data_dir``."""
    data_dir = Path(data_dir)
    artifact = build_signals_artifact(definitions or load_definitions(), directory_payload_loader(data_dir))
    if not artifact["signals"]:
        raise RuntimeError("no cycle signal could be resolved from the generated chart data")
    target = data_dir / ARTIFACT_NAME
    temporary = target.with_suffix(".json.tmp")
    try:
        temporary.write_text(
            json.dumps(artifact, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8"
        )
        temporary.replace(target)
    finally:
        # Never leave a partial file in the directory that gets published.
        temporary.unlink(missing_ok=True)
    return artifact


def main(argv: list[str]) -> int:
    data_dir = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent / "data" / "bitcoin"
    artifact = write_signals_artifact(data_dir)
    composite = artifact["composite"] or {}
    print(
        f"Wrote {data_dir / ARTIFACT_NAME}: {len(artifact['signals'])} signals, "
        f"{len(artifact['unavailable'])} unavailable, Cycle Index {composite.get('score')} "
        f"({composite.get('phase')}), data through {artifact['data_through']}"
    )
    for entry in artifact["unavailable"]:
        print(f"  unavailable: {entry['id']} - {entry['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
