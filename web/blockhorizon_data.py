"""Import BlockHorizon's public Bitcoin chart bundle into local Plotly payloads.

The generated JSON stays in ``web/data`` (which is ignored by git).  Keeping the
adapter here makes the external source explicit and lets the hourly site build
refresh the imported charts alongside the repository's native charts.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


SOURCE_DASHBOARD_URL = "https://charts.blockhorizon.io/dashboard"
SOURCE_BUNDLE_URL = (
    "https://zbvrubdalcojapjygbcz.supabase.co/functions/v1/"
    "bundle_handler/serve?resolution=downsampled_v2"
)

# This is the public chart library displayed in the BlockHorizon dashboard on
# 2026-09-09.  The explicit allow-list prevents unpublished/experimental bundle
# entries from appearing in this site without review.
REFERENCE_CHART_TITLES = (
    "Addresses Accumulation",
    "Addresses Active",
    "Addresses in Loss",
    "Addresses in Profit",
    "Addresses in Profit (%)",
    "Addresses New",
    "Addresses Receiving",
    "Addresses Sending",
    "Addresses Total",
    "Addresses with Non-Zero Balance",
    "ASOL: Average Spent Output Lifespan",
    "Balanced Price",
    "Block Height",
    "Blocks Mined",
    "CDD (Coin Days Destroyed)",
    "CDD 90-Day",
    "CDD Long Term Supply",
    "CDD Short Term Supply",
    "Coin Blocks Created (CBC)",
    "Coin Blocks Destroyed (CBD)",
    "Coin Vintages",
    "Cost-Basis Heatmap",
    "Cushion Depth Fan",
    "Days Until Halving",
    "Delta Cap",
    "Delta Price",
    "Difficulty",
    "Difficulty Ribbon",
    "Fee Ratio Multiple (FRM)",
    "Fees Mean",
    "Fees Total",
    "HODL Waves",
    "Issuance",
    "Market Cap",
    "Market Cap To Thermocap Ratio",
    "Miner Revenue: Block Rewards",
    "Miner Revenue: Fees (%)",
    "Miner Revenue: Total",
    "MVRV (Market Value to Realized Value Ratio)",
    "MVRV Adjusted Ratio",
    "MVRV Long Term Supply",
    "MVRV Momentum Oscillator",
    "MVRV Short Term Supply",
    "MVRV Z-Score",
    "NUPL (Net Unrealized Profit Loss)",
    "NUPL Long Term Supply (LTS)",
    "NUPL Short Term Supply (STS)",
    "Outputs Spent <1h",
    "Outputs Spent 1d-1w",
    "Outputs Spent 1h-24h",
    "Outputs Spent 1m-3m",
    "Outputs Spent 1w-1m",
    "Outputs Spent 1y-2y",
    "Outputs Spent 2y-3y",
    "Outputs Spent 3m-6m",
    "Outputs Spent 3y-5y",
    "Outputs Spent 5y-7y",
    "Outputs Spent 6m-12m",
    "Outputs Spent 7y-10y",
    "Outputs Spent 10y+",
    "Pi Cycle Top Indicator",
    "PlanB: Moving Averages",
    "PlanB: Realized Prices",
    "PlanB: RSI",
    "PlanB: Stock to Flow (S2F)",
    "PlanB: Stock to Flow + RSI + MA + Realized",
    "Price",
    "Price Drawdown",
    "Price OHLC",
    "Realized Cap",
    "Realized Cap HODL Waves",
    "Realized Price",
    "Realized Price - Long Term Supply (LTS)",
    "Realized Price - Short Term Supply (STS)",
    "SOPR (Spent Output Profit Ratio)",
    "SOPR Adjusted (aSOPR)",
    "SOPR Long Term Supply (LTS)",
    "SOPR Short Term Supply (STS)",
    "Spent Volume <1h",
    "Spent Volume 1d-1w",
    "Spent Volume 1h-24h",
    "Spent Volume 1m-3m",
    "Spent Volume 1w-1m",
    "Spent Volume 1y-2y",
    "Spent Volume 2y-3y",
    "Spent Volume 3m-6m",
    "Spent Volume 3y-5y",
    "Spent Volume 5y-7y",
    "Spent Volume 6m-12m",
    "Spent Volume 7y-10y",
    "Spent Volume 10y+",
    "Supply Adjusted",
    "Supply Circulating",
    "Supply in Loss",
    "Supply in Profit",
    "Supply in Profit (%)",
    "Supply Last Active < 24 Hours",
    "Supply Last Active 1+ Years Ago (%)",
    "Supply Last Active 1d-1w",
    "Supply Last Active 1m-3m",
    "Supply Last Active 1w-1m",
    "Supply Last Active 1y-2y",
    "Supply Last Active 2+ Years Ago (%)",
    "Supply Last Active 2y-3y",
    "Supply Last Active 3+ Years Ago (%)",
    "Supply Last Active 3m-6m",
    "Supply Last Active 3y-5y",
    "Supply Last Active 5+ Years Ago (%)",
    "Supply Last Active 5y-7y",
    "Supply Last Active 6m-12m",
    "Supply Last Active 7y-10y",
    "Supply Last Active 10y+",
    "Supply Long Term (LTS)",
    "Supply Long Term (LTS) in Loss",
    "Supply Long Term (LTS) in Profit",
    "Supply Long Term (LTS) Position Change",
    "Supply Probably Lost",
    "Supply Revived 1+ Years",
    "Supply Revived 2+ Years",
    "Supply Revived 3+ Years",
    "Supply Revived 5+ Years",
    "Supply Short Term (STS)",
    "Supply Short Term (STS) in Loss",
    "Supply Short Term (STS) in Profit",
    "Supply Short Term (STS) Position Change",
    "Terminal Price",
    "Thermocap",
    "Top Cap",
    "Top Price",
    "Total Transactions",
    "Transaction Count",
    "Transaction Rate",
    "Transfer Volume in Loss",
    "Transfer Volume in Profit",
    "Transfer Volume in Profit (%)",
    "Transfer Volume Mean",
    "Transfer Volume Total",
    "UTXO Count Total",
    "UTXO Value Created Mean",
    "UTXO Value Created Total",
    "UTXO Value Spent Mean",
    "UTXO Value Spent Total",
    "UTXOs Created",
    "UTXOs in Loss",
    "UTXOs in Profit",
    "UTXOs in Profit (%)",
    "UTXOs Spent",
)

# These source charts are already represented by a native Fintech chart.  The
# local implementation remains authoritative and the imported duplicate is
# omitted from the union.
REFERENCE_EQUIVALENTS = {
    "Pi Cycle Top Indicator": "pi-cycle-top",
    "PlanB: Moving Averages": "200-dma-200-wma",
    "Price Drawdown": "drawdown-recovery-map",
}

PALETTE = (
    "#c85f3c",
    "#2863a7",
    "#16844d",
    "#c91f50",
    "#7c5ca8",
    "#d98945",
    "#238a8d",
    "#996515",
    "#5f6caf",
    "#a24d68",
)


def _fetch_bundle(timeout: int = 90) -> tuple[list[dict], str | None]:
    request = Request(
        SOURCE_BUNDLE_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Fintech-Charts/1.0 (+https://github.com/JamesTsetsekas/Fintech)",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
        built_at = response.headers.get("X-Bundle-Built-At")
    if not isinstance(payload, list):
        raise ValueError("BlockHorizon chart bundle did not contain a chart list")
    return payload, built_at


def _decode_series(source_series: dict) -> tuple[list[str], list[float | None]]:
    packed = source_series.get("pd") or {}
    deltas = packed.get("d") or []
    values = packed.get("v") or []
    start_ms = packed.get("t0")
    if start_ms is None or len(deltas) != len(values):
        return [], []

    cursor = datetime.fromtimestamp(float(start_ms) / 1000, tz=timezone.utc)
    dates = []
    for delta in deltas:
        cursor += timedelta(days=float(delta))
        dates.append(cursor.strftime("%Y-%m-%d"))
    return dates, values


def _series_style(chart: dict, source_series: dict) -> dict:
    series_types = (chart.get("style_config") or {}).get("seriesTypes") or {}
    return series_types.get(source_series.get("series_key"), {}) or {}


def _point_colors(source_series: dict, length: int) -> list[str] | None:
    overrides = (source_series.get("pd") or {}).get("x") or {}
    if not overrides:
        return None
    fallback = source_series.get("color") or PALETTE[0]
    return [overrides.get(str(index), {}).get("color", fallback) for index in range(length)]


def _line_trace(chart: dict, source_series: dict, index: int) -> dict | None:
    dates, values = _decode_series(source_series)
    if not dates:
        return None
    style = _series_style(chart, source_series)
    color = style.get("color") or source_series.get("color") or PALETTE[index % len(PALETTE)]
    series_type = style.get("type", "line")
    base = {
        "name": str(source_series.get("name") or source_series.get("series_key") or f"Series {index + 1}").strip(),
        "source_key": source_series.get("series_key"),
        "x": dates,
        "y": values,
        "hovertemplate": "%{x}<br>%{y:,.4g}<extra>%{fullData.name}</extra>",
    }
    if series_type == "column":
        return {
            **base,
            "type": "bar",
            "marker": {"color": color},
        }

    trace = {
        **base,
        "type": "scatter",
        "mode": "lines",
        "line": {"color": color, "width": style.get("lineWidth", 1.8)},
    }
    if series_type == "area":
        trace.update({
            "stackgroup": "onchain-stack",
            "fill": "tonexty",
            "fillcolor": color,
            "line": {"color": color, "width": style.get("lineWidth", 0.5)},
        })
    colors = _point_colors(source_series, len(values))
    if colors:
        trace["mode"] = "lines+markers"
        trace["marker"] = {"color": colors, "size": 4}
    return trace


def _ohlc_trace(chart: dict) -> list[dict]:
    by_key = {series.get("series_key"): series for series in chart.get("series") or []}
    required = ("open", "high", "low", "close")
    if any(key not in by_key for key in required):
        return []
    dates, opens = _decode_series(by_key["open"])
    decoded = {key: _decode_series(by_key[key])[1] for key in required}
    return [{
        "name": "BTC OHLC",
        "source_key": "ohlc",
        "type": "candlestick",
        "x": dates,
        "open": opens,
        "high": decoded["high"],
        "low": decoded["low"],
        "close": decoded["close"],
        "increasing": {"line": {"color": "#16844d", "width": 1}},
        "decreasing": {"line": {"color": "#c91f50", "width": 1}},
    }]


def _heatmap_trace(chart: dict) -> list[dict]:
    source_series = chart.get("series") or []
    if not source_series:
        return []
    dates, _ = _decode_series(source_series[0])
    if not dates:
        return []
    style = (chart.get("style_config") or {}).get("heatmap") or {}
    rows = []
    labels = []
    for series in source_series:
        series_dates, values = _decode_series(series)
        if series_dates == dates:
            labels.append(str(series.get("name") or series.get("series_key") or "").strip())
            rows.append(values)
    if not rows:
        return []
    stops = style.get("stops") or [[0, "#2863a7"], [0.5, "#fffefa"], [1, "#c91f50"]]
    return [{
        "name": "Distribution",
        "source_key": "distribution",
        "type": "heatmap",
        "x": dates,
        "y": labels,
        "z": rows,
        "colorscale": stops,
        "zmin": style.get("min"),
        "zmax": style.get("max"),
        "colorbar": {"title": style.get("colorbarLabel", "Value"), "thickness": 10},
        "hovertemplate": "%{x}<br>%{y}<br>%{z:,.4g}<extra></extra>",
    }]


def _bitcoin_price_trace(price_chart: dict) -> dict | None:
    source = next(iter(price_chart.get("series") or []), None)
    if not source:
        return None
    dates, values = _decode_series(source)
    if not dates:
        return None
    return {
        "name": "BTC price",
        "source_key": "price",
        "type": "scatter",
        "mode": "lines",
        "x": dates,
        "y": values,
        "line": {"color": "#eef3f8", "width": 1.6},
        "hovertemplate": "%{x}<br>$%{y:,.0f}<extra>BTC price</extra>",
    }


def _metric_axis_title(chart: dict) -> str:
    names = [str(series.get("name") or "").strip() for series in chart.get("series") or []]
    if len(names) == 1:
        return names[0]
    return chart["name"].strip()


def _build_payload(chart: dict, price_chart: dict, built_at: str | None) -> dict:
    style_config = chart.get("style_config") or {}
    if style_config.get("ohlcChart"):
        traces = _ohlc_trace(chart)
    elif style_config.get("heatmap"):
        traces = _heatmap_trace(chart)
    else:
        traces = [
            trace
            for index, source_series in enumerate(chart.get("series") or [])
            if (trace := _line_trace(chart, source_series, index)) is not None
        ]

    dollar_metric = bool(chart.get("series")) and all(
        (series.get("value_prefix") or "") == "$" for series in chart.get("series") or []
    )
    can_overlay_price = bool(chart.get("include_btc")) and not style_config.get("heatmap")
    price_trace = _bitcoin_price_trace(price_chart) if can_overlay_price else None
    if price_trace and chart.get("slug") != price_chart.get("slug"):
        if dollar_metric:
            traces.insert(0, price_trace)
        else:
            price_trace["axis"] = "y"
            for trace in traces:
                trace["axis"] = "y2"
            traces.insert(0, price_trace)

    default_log = bool((chart.get("toolbar_config") or {}).get("default_log_scale"))
    yaxis = {
        "title": "BTC price (USD)" if price_trace and not dollar_metric else _metric_axis_title(chart),
        "type": "log" if (price_trace or default_log) else "linear",
        "automargin": True,
    }
    if dollar_metric or price_trace:
        yaxis["tickprefix"] = "$"
    layout = {"yaxis": yaxis}
    if price_trace and not dollar_metric:
        first_series = next(iter(chart.get("series") or []), {})
        layout["yaxis2"] = {
            "title": _metric_axis_title(chart),
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "automargin": True,
            "ticksuffix": first_series.get("value_suffix") or "",
        }
    elif chart.get("series"):
        suffixes = {series.get("value_suffix") for series in chart["series"] if series.get("value_suffix")}
        if len(suffixes) == 1:
            yaxis["ticksuffix"] = next(iter(suffixes))

    latest_date = None
    for trace in traces:
        if trace.get("x"):
            latest_date = trace["x"][-1]
            break
    source_updated = built_at or chart.get("updated_at") or datetime.now(timezone.utc).isoformat()
    return {
        "id": chart["slug"],
        "title": chart["name"].strip(),
        "summary_text": (
            f"Historical on-chain series from BlockHorizon's public chart bundle"
            f"{f'; latest observation {latest_date}' if latest_date else ''}."
        ),
        "updated_at": source_updated,
        "source_label": "BlockHorizon public chart bundle",
        "source_url": SOURCE_DASHBOARD_URL,
        "allow_scale_toggle": bool((chart.get("toolbar_config") or {}).get("has_scale")),
        "default_scale": "log" if (price_trace or default_log) else "linear",
        "scale_axes": ["y"],
        "x_value_type": "date",
        "show_range_selector": bool((chart.get("toolbar_config") or {}).get("has_date", True)),
        "series": traces,
        "layout": layout,
    }


def _section_id(title: str) -> str:
    lower = title.lower()
    if "heatmap" in lower or "waves" in lower or "vintages" in lower:
        return "heatmaps"
    if "halving" in lower:
        return "halving"
    if any(token in lower for token in ("mvrv", "nupl", "realized price", "balanced price", "delta price", "top price", "terminal price", "planb", "sopr")):
        return "cycle-models"
    if any(token in lower for token in ("price", "rsi", "moving average", "difficulty ribbon")):
        return "technical"
    return "onchain"


def import_reference_charts(output_dir: Path, section_name, *, timeout: int = 90) -> list[dict]:
    """Download, convert, and write the reviewed public reference chart set."""
    bundle, built_at = _fetch_bundle(timeout=timeout)
    charts_by_name = {str(chart.get("name") or "").strip(): chart for chart in bundle}
    missing = [title for title in REFERENCE_CHART_TITLES if title not in charts_by_name]
    if missing:
        raise RuntimeError(f"BlockHorizon bundle is missing {len(missing)} reviewed charts: {', '.join(missing[:5])}")
    price_chart = charts_by_name["Price"]
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    for order, title in enumerate(REFERENCE_CHART_TITLES):
        if title in REFERENCE_EQUIVALENTS:
            continue
        source_chart = charts_by_name[title]
        payload = _build_payload(source_chart, price_chart, built_at)
        if not payload["series"]:
            raise RuntimeError(f"BlockHorizon chart has no renderable public series: {title}")
        chart_id = payload["id"]
        path = output_dir / f"{chart_id}.json"
        path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        section_id = _section_id(title)
        manifest_entries.append({
            "id": chart_id,
            "title": title,
            "section_id": section_id,
            "section": section_name(section_id),
            "description": "Public BlockHorizon on-chain series, refreshed during the Fintech site build.",
            "image_path": None,
            "kind": "interactive",
            "data_path": f"web/data/bitcoin/{chart_id}.json",
            "order": 10_000 + order,
            "image_exists": False,
            "source_label": "BlockHorizon",
            "source_url": SOURCE_DASHBOARD_URL,
        })
    return manifest_entries
