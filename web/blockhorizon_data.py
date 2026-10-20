"""Import BlockHorizon's public Bitcoin chart bundle into local Plotly payloads.

The generated JSON stays in ``web/data`` (which is ignored by git).  Keeping the
adapter here makes the external source explicit and lets the hourly site build
refresh the imported charts alongside the repository's native charts.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


SOURCE_DASHBOARD_URL = "https://charts.blockhorizon.io/dashboard"
SOURCE_BUNDLE_URL = (
    "https://zbvrubdalcojapjygbcz.supabase.co/functions/v1/"
    "bundle_handler/serve?resolution=downsampled_v2"
)

# Reviewed against the 154-chart public dashboard on 2026-10-20. Stable slugs
# identify charts; upstream display-title edits must never select stale cache.
# The three replay/distribution views below require a different renderer and
# are deliberately excluded. Bundle-only index charts are not library entries.
REFERENCE_CHARTS = {
    'accumulation-addresses': 'Addresses Accumulation',
    'active-addresses': 'Addresses Active',
    'addresses-in-loss': 'Addresses in Loss',
    'percent-addresses-in-loss': 'Addresses in Loss (%)',
    'addresses-in-profit': 'Addresses in Profit',
    'percent-addresses-in-profit': 'Addresses in Profit (%)',
    'new-addresses': 'Addresses New',
    'receiving-addresses': 'Addresses Receiving',
    'sending-addresses': 'Addresses Sending',
    'total-addresses': 'Addresses Total (Cumulative)',
    'non-zero-addresses': 'Addresses with Non-Zero Balance',
    'asol': 'ASOL: Average Spent Output Lifespan',
    'balanced-price': 'Balanced Price',
    'block-height': 'Block Height',
    'blocks-mined': 'Blocks Mined',
    'cdd': 'CDD (Coin Days Destroyed)',
    '90d-cdd': 'CDD 90-Day',
    'long-term-supply-cdd': 'CDD Long Term Supply (LTS)',
    'short-term-supply-cdd': 'CDD Short Term Supply (STS)',
    'coin-blocks-created': 'Coin Blocks Created (CBC)',
    'coin-blocks-destroyed': 'Coin Blocks Destroyed (CBD)',
    'issuance': 'Coin issuance',
    'cost-basis-heatmap': 'Cost basis Heatmap',
    'cushion-depth-fan': 'Cushion Depth Fan',
    'days-until-halving': 'Days Until Halving',
    'delta-cap': 'Delta Cap',
    'delta-price': 'Delta Price',
    'difficulty': 'Difficulty',
    'difficulty-ribbon': 'Difficulty Ribbon',
    'frm': 'Fee Ratio Multiple (FRM)',
    'fees-avg': 'Fees Mean (per Transaction)',
    'fees-total': 'Fees Total (Daily)',
    'hodl-waves': 'HODL Waves',
    'market-cap': 'Market Cap',
    'market-cap-to-thermocap-ratio': 'Market Cap to Thermocap Ratio',
    'miner-revenue-block-rewards': 'Miner Revenue: Block Rewards',
    'miner-revenue-fees': 'Miner Revenue: Fees (%)',
    'miner-revenue-total': 'Miner Revenue: Total (Daily)',
    'mvrv': 'MVRV (Market Value to Realized Value Ratio)',
    'lth-mvrv': 'MVRV Long Term Supply (LTS)',
    'mvrv-momentum': 'MVRV Momentum Oscillator',
    'sth-mvrv': 'MVRV Short Term Supply (STS)',
    'mvrv-z-score': 'MVRV Z-Score',
    'nupl': 'NUPL (Net Unrealized Profit Loss)',
    'lts-nupl': 'NUPL Long Term Supply (LTS)',
    'sts-nupl': 'NUPL Short Term Supply (STS)',
    'pi-cycle': 'Pi Cycle Top Indicator',
    'pb-200wma': 'PlanB: Moving Averages',
    'pb-realized-prices': 'PlanB: Realized Prices',
    'pb-rsi': 'PlanB: RSI',
    'pb-s2f': 'PlanB: Stock to Flow (S2F)',
    'pb-various': 'PlanB: Stock to Flow + RSI + MA + Realized',
    'price': 'Price',
    'price-drawdown': 'Price Drawdown',
    'ohlc': 'Price OHLC',
    '100wma': 'Price: 100 Week Moving Average (100WMA)',
    '200wma': 'Price: 200 Week Moving Average (200WMA)',
    '50wma': 'Price: 50 Week Moving Average (50WMA)',
    'realized-cap': 'Realized Cap',
    'realized-cap-hodl-waves': 'Realized Cap HODL Waves',
    'realized-price': 'Realized Price',
    'realized-price-lts': 'Realized Price - Long Term Supply (LTS)',
    'realized-price-sts': 'Realized Price - Short Term Supply (STS)',
    'realized-price-2y': 'Realized Price: 2 Year',
    'realized-price-4y': 'Realized Price: 4 Year',
    'sopr': 'SOPR (Spent Output Profit Ratio)',
    'asopr': 'SOPR Adjusted (aSOPR)',
    'lts-sopr': 'SOPR Long Term Supply (LTS)',
    'sts-sopr': 'SOPR Short Term Supply (STS)',
    'spent-outputs-10y': 'Spent Outputs 10y+',
    'spent-outputs-1d-1w': 'Spent Outputs 1d–1w',
    'spent-outputs-1h-24h': 'Spent Outputs 1h–1d',
    'spent-outputs-1m-3m': 'Spent Outputs 1m–3m',
    'spent-outputs-1w-1m': 'Spent Outputs 1w–1m',
    'spent-outputs-1y-2y': 'Spent Outputs 1y–2y',
    'spent-outputs-2y-3y': 'Spent Outputs 2y–3y',
    'spent-outputs-3m-6m': 'Spent Outputs 3m–6m',
    'spent-outputs-3y-5y': 'Spent Outputs 3y–5y',
    'spent-outputs-5y-7y': 'Spent Outputs 5y–7y',
    'spent-outputs-6m-12m': 'Spent Outputs 6m–12m',
    'spent-outputs-7y-10y': 'Spent Outputs 7y–10y',
    'spent-outputs-1h': 'Spent Outputs <1h',
    'adjusted-supply': 'Supply Adjusted',
    'circulating-supply': 'Supply Circulating',
    'supply-in-loss': 'Supply in Loss',
    'percent-supply-in-loss': 'Supply in Loss (%)',
    'old-vs-new-loss': 'Supply in Loss (%): Old vs New Coins',
    'supply-in-profit': 'Supply in Profit',
    'percent-supply-in-profit': 'Supply in Profit (%)',
    'supply-last-active-10y': 'Supply Last Active 10y+',
    'supply-last-active-1d-1w': 'Supply Last Active 1d–1w',
    'supply-last-active-1m-3m': 'Supply Last Active 1m–3m',
    'supply-last-active-1w-1m': 'Supply Last Active 1w–1m',
    'supply-last-active-1-year-ago': 'Supply Last Active 1y+ Ago (%)',
    'supply-last-active-1y-2y': 'Supply Last Active 1y–2y',
    'supply-last-active-2-year-ago': 'Supply Last Active 2y+ Ago (%)',
    'supply-last-active-2y-3y': 'Supply Last Active 2y–3y',
    'supply-last-active-3m-6m': 'Supply Last Active 3m–6m',
    'supply-last-active-3-year-ago': 'Supply Last Active 3y+ Ago (%)',
    'supply-last-active-3y-5y': 'Supply Last Active 3y–5y',
    'supply-last-active-5-year-ago': 'Supply Last Active 5y+ Ago (%)',
    'supply-last-active-5y-7y': 'Supply Last Active 5y–7y',
    'supply-last-active-6m-12m': 'Supply Last Active 6m–12m',
    'supply-last-active-7y-10y': 'Supply Last Active 7y–10y',
    'supply-last-active-24h': 'Supply Last Active <1d',
    'long-term-supply': 'Supply Long Term (LTS)',
    'long-term-supply-in-loss': 'Supply Long Term (LTS) in Loss',
    'long-term-supply-in-profit': 'Supply Long Term (LTS) in Profit',
    'long-term-supply-position-change': 'Supply Long Term (LTS) Position Change',
    'probably-lost-supply': 'Supply Probably Lost',
    'revived-supply-1-year': 'Supply Revived 1y+',
    'revived-supply-2-year': 'Supply Revived 2y+',
    'revived-supply-3-year': 'Supply Revived 3y+',
    'revived-supply-5-year': 'Supply Revived 5y+',
    'short-term-supply': 'Supply Short Term (STS)',
    'short-term-supply-in-loss': 'Supply Short Term (STS) in Loss',
    'short-term-supply-in-profit': 'Supply Short Term (STS) in Profit',
    'short-term-supply-position-change': 'Supply Short Term (STS) Position Change',
    'terminal-price': 'Terminal Price',
    'thermocap': 'Thermocap',
    'top-cap': 'Top Cap',
    'top-price': 'Top Price',
    'total-transactions': 'Total Transactions (Cumulative)',
    'transaction-count-per-day': 'Transaction Count (Daily)',
    'transaction-rate': 'Transaction Rate',
    'spent-volume-10y': 'Transfer Volume 10y+',
    'spent-volume-1d-1w': 'Transfer Volume 1d–1w',
    'spent-volume-1h-24h': 'Transfer Volume 1h–1d',
    'spent-volume-1m-3m': 'Transfer Volume 1m–3m',
    'spent-volume-1w-1m': 'Transfer Volume 1w–1m',
    'spent-volume-1y-2y': 'Transfer Volume 1y–2y',
    'spent-volume-2y-3y': 'Transfer Volume 2y–3y',
    'spent-volume-3m-6m': 'Transfer Volume 3m–6m',
    'spent-volume-3y-5y': 'Transfer Volume 3y–5y',
    'spent-volume-5y-7y': 'Transfer Volume 5y–7y',
    'spent-volume-6m-12m': 'Transfer Volume 6m–12m',
    'spent-volume-7y-10y': 'Transfer Volume 7y–10y',
    'spent-volume-1h': 'Transfer Volume <1h',
    'percent-volume-in-loss': 'Transfer Volume in Loss (%)',
    'transfer-volume-avg': 'Transfer Volume Mean (per Transaction)',
    'transfer-volume-total': 'Transfer Volume Total (Daily)',
    'utxo-total': 'UTXO Count',
    'utxo-value-created-avg': 'UTXO Value Created Mean (per Output)',
    'utxo-value-created-total': 'UTXO Value Created Total (Daily)',
    'utxo-value-spent-avg': 'UTXO Value Spent Mean (per Output)',
    'utxo-created': 'UTXOs Created',
    'utxos-in-loss': 'UTXOs in Loss',
    'percent-utxos-in-loss': 'UTXOs in Loss (%)',
    'utxos-in-profit': 'UTXOs in Profit',
    'percent-utxos-in-profit': 'UTXOs in Profit (%)',
    'utxo-spent': 'UTXOs Spent',
}

REFERENCE_CHART_TITLES = tuple(REFERENCE_CHARTS.values())

# These formerly reviewed series are no longer in the upstream public bundle.
# Do not keep their old generated data active in the manifest or signals.
RETIRED_CHARTS = {
    'coin-vintages': 'Coin Vintages',
    'adjusted-mvrv': 'MVRV Adjusted Ratio',
    'transfer-volume-in-loss': 'Transfer Volume in Loss',
    'transfer-volume-in-profit': 'Transfer Volume in Profit',
    'percent-volume-in-profit': 'Transfer Volume in Profit (%)',
    'utxo-value-spent-total': 'UTXO Value Spent Total',
}

DEFERRED_CHARTS = {
    "cost-basis-distribution": "Price-bucket histograms and replay frames need a distribution renderer.",
    "overhead-supply-wall": "Derived replay view has no standalone time series in the public bundle.",
    "profit-ladder": "Derived replay view has no standalone time series in the public bundle.",
}

# Native implementations remain authoritative for these equivalent charts.
REFERENCE_EQUIVALENTS = {
    "pi-cycle": "pi-cycle-top",
    "pb-200wma": "200-dma-200-wma",
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

# A small number of source charts use semantic styling that is not represented
# in their public series metadata. Keep these overrides narrow and documented
# rather than applying a generic palette that changes the chart's meaning.
SOURCE_SERIES_OVERRIDES = {
    ("pb-s2f", "s2f_price_model"): {"color": "#393732", "width": 1.8},
    ("pb-s2f", "s2f_error"): {"color": "#858585", "mode": "markers", "size": 3.2},
}

# The source presents its S2F model in logarithmic space even though its
# toolbar default flag is false. Linear scale compresses its price/error
# history into the x-axis and makes the imported chart misleading.
SOURCE_LOG_SCALE_OVERRIDES = {"pb-s2f"}


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


def _value_line_marker(source_series: dict, values: list[float | None]) -> dict | None:
    # The source's normal NUPL view uses five discrete sentiment colors.
    # Its optional Signal view instead colors BTC with a continuous rainbow.
    if source_series.get("series_key") != "nupl":
        return None
    thresholds = ((0, "#e54242"), (.25, "#ef7f11"), (.5, "#ebd249"), (.75, "#24c813"))
    return {
        "color": [
            next((color for threshold, color in thresholds if value < threshold), "#4467eb")
            if isinstance(value, (int, float)) else "rgba(0,0,0,0)"
            for value in values
        ],
        "size": 0,
    }


def _line_trace(chart: dict, source_series: dict, index: int) -> dict | None:
    dates, values = _decode_series(source_series)
    if not dates:
        return None
    style = _series_style(chart, source_series)
    override = SOURCE_SERIES_OVERRIDES.get((chart.get("slug"), source_series.get("series_key")), {})
    color = override.get("color") or style.get("color") or source_series.get("color") or PALETTE[index % len(PALETTE)]
    if (chart.get("gradient_config") or {}).get("default_series_key") == source_series.get("series_key"):
        color = override.get("color") or style.get("color") or source_series.get("color") or "#c96442"
    series_type = style.get("type", "line")
    base = {
        "name": str(source_series.get("name") or source_series.get("series_key") or f"Series {index + 1}").strip(),
        "source_key": source_series.get("series_key"),
        "x": dates,
        "y": values,
        "hovertemplate": (
            f"%{{x}}<br>{source_series.get('value_prefix') or ''}"
            f"%{{y:,.4g}}{source_series.get('value_suffix') or ''}"
            "<extra>%{fullData.name}</extra>"
        ),
    }
    if series_type == "column":
        marker_color = color
        threshold = style.get("threshold")
        negative_color = style.get("negativeColor")
        if isinstance(threshold, (int, float)) and negative_color:
            marker_color = [negative_color if value is not None and value < threshold else color for value in values]
        return {
            **base,
            "type": "bar",
            "marker": {"color": marker_color, "line": {"width": style.get("borderWidth", 0)}},
        }

    trace = {
        **base,
        "type": "scatter",
        "mode": override.get("mode", "lines"),
        "line": {
            "color": color,
            "width": override.get("width", style.get("lineWidth", 1.8)),
            **({"dash": str(style["dashStyle"]).lower()} if style.get("dashStyle") else {}),
        },
    }
    if override.get("mode") == "markers":
        trace["marker"] = {"color": color, "size": override.get("size", 3.2)}
        trace.pop("line", None)
    if series_type == "area":
        area_style = {
            "fill": "tonexty" if style.get("stacking") == "normal" else "tozeroy",
            "fillcolor": color,
            "line": {"color": color, "width": style.get("lineWidth", 0.5)},
        }
        if style.get("stacking") == "normal":
            area_style["stackgroup"] = "onchain-stack"
        trace.update(area_style)
    colors = _point_colors(source_series, len(values))
    if colors:
        trace["mode"] = "lines+markers"
        trace["marker"] = {"color": colors, "size": 6}
    elif gradient_marker := _value_line_marker(source_series, values):
        # Normal mode plots the metric as a continuous value-colored line.
        # Signal mode colors BTC price instead; its metadata is kept separate
        # so this authoritative metric remains available to tables and signals.
        trace["mode"] = "lines"
        trace["line"] = {"color": "rgba(0,0,0,0)", "width": 2}
        trace["marker"] = gradient_marker
        trace["value_colored_line"] = True
    return trace


def _signal_view_config(chart: dict) -> dict | None:
    """Describe the source's optional price-colored-by-metric view."""
    config = chart.get("gradient_config") or {}
    mode = config.get("default_mode")
    if not chart.get("include_btc") or mode not in {"absolute", "error"}:
        return None
    bounds = config.get(mode) or {}
    lower, upper = bounds.get("default_min"), bounds.get("default_max")
    if (not isinstance(lower, (int, float)) or not isinstance(upper, (int, float))
            or not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper):
        return None
    key = config.get("default_series_key")
    if not any(series.get("series_key") == key for series in chart.get("series") or []):
        return None
    return {"mode": mode, "series_key": key, "min": lower, "max": upper}


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
    if not traces:
        raise RuntimeError(f"BlockHorizon chart has no renderable public series: {chart.get('slug')}")
    if not style_config.get("ohlcChart") and not style_config.get("heatmap"):
        if len(traces) != len(chart.get("series") or []):
            raise RuntimeError(f"BlockHorizon chart has an invalid packed series: {chart.get('slug')}")

    dollar_metric = bool(chart.get("series")) and all(
        (series.get("value_prefix") or "") == "$" for series in chart.get("series") or []
    )
    can_overlay_price = bool(chart.get("include_btc")) and not style_config.get("heatmap")
    # A few source charts (notably Price Drawdown) already carry their own
    # price series.  Replacing it with a second BTC trace produced duplicate
    # legend rows and put the source price on the metric axis.  Retain that
    # authoritative series and only synthesize an overlay when it is absent.
    source_price_trace = next((trace for trace in traces if trace.get("source_key") == "price"), None)
    price_trace = source_price_trace or (_bitcoin_price_trace(price_chart) if can_overlay_price else None)
    if price_trace and chart.get("slug") != price_chart.get("slug"):
        if dollar_metric:
            if source_price_trace is None:
                traces.insert(0, price_trace)
        else:
            price_trace["axis"] = "y"
            for trace in traces:
                if trace is not price_trace:
                    trace["axis"] = "y2"
            if source_price_trace is None:
                traces.insert(0, price_trace)

    default_log = bool((chart.get("toolbar_config") or {}).get("default_log_scale"))
    default_log = default_log or chart.get("slug") in SOURCE_LOG_SCALE_OVERRIDES
    yaxis = {
        "title": "BTC price (USD)" if price_trace and not dollar_metric else _metric_axis_title(chart),
        "type": "log" if (price_trace or default_log) else "linear",
        "automargin": True,
    }
    if dollar_metric or price_trace:
        yaxis["tickprefix"] = "$"
    layout = {"yaxis": yaxis}
    # Preserve the source's reviewed viewport.  This is especially important
    # for model charts with forward projections and charts whose BTC overlay
    # starts before the metric itself exists.
    x_config = (chart.get("axis_config") or {}).get("x") or {}
    available_dates = [
        date
        for trace in traces
        for date in (trace.get("x") or [])
        if isinstance(date, str)
    ]
    lower_bound = x_config.get("min") or (min(available_dates) if available_dates else None)
    upper_bound = x_config.get("max") or (max(available_dates) if available_dates else None)
    # Plotly requires both values for an explicit range.  A source-provided
    # one-sided limit therefore pairs with the available data boundary.
    if x_config.get("min") is not None or x_config.get("max") is not None:
        layout["xaxis"] = {"range": [lower_bound, upper_bound]}
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
        if chart.get("slug") == "nupl":
            layout["yaxis2"].update({"range": [-2, 1], "tickvals": [-2, -1, 0, 1]})
    elif chart.get("series"):
        suffixes = {series.get("value_suffix") for series in chart["series"] if series.get("value_suffix")}
        if len(suffixes) == 1:
            yaxis["ticksuffix"] = next(iter(suffixes))

    # The new cohort-loss view has two panes and two different units. Mixing
    # the percentage-point gap into the 0-100% pane changes its meaning.
    if chart.get("slug") == "old-vs-new-loss":
        yaxis["domain"] = [0.40, 1]
        layout["yaxis2"].update({"domain": [0.40, 1], "title": "Supply in loss", "range": [0, 100], "ticksuffix": "%"})
        layout["xaxis"] = {**layout.get("xaxis", {}), "anchor": "y3"}
        layout["yaxis3"] = {
            "title": "Old minus new",
            "domain": [0, 0.28],
            "anchor": "x",
            "ticksuffix": " pp",
            "zeroline": True,
            "automargin": True,
        }
        for trace in traces:
            if trace.get("source_key") == "lts_minus_sts_pp":
                trace["axis"] = "y3"

    # Keep bounded percentage metrics on their source's reviewed 0-100 axis.
    if chart.get("slug") in {
        "percent-supply-in-loss", "percent-utxos-in-loss",
        "percent-volume-in-loss", "percent-addresses-in-loss",
    }:
        layout["yaxis2"]["range"] = [0, 100]

    latest_date = None
    for trace in traces:
        if trace.get("x"):
            latest_date = trace["x"][-1]
            break
    source_updated = built_at or chart.get("updated_at") or datetime.now(timezone.utc).isoformat()
    main_series_id = chart.get("main_series_id")
    main_series_key = next(
        (
            series.get("series_key")
            for series in chart.get("series") or []
            if series.get("id") == main_series_id
        ),
        None,
    )
    return {
        "id": chart["slug"],
        "title": chart["name"].strip(),
        "summary_text": (
            f"Historical on-chain series"
            f"{f'; latest observation {latest_date}' if latest_date else ''}."
        ),
        "updated_at": source_updated,
        "source_label": "BlockHorizon public chart bundle",
        "source_url": f"https://charts.blockhorizon.io/charts/{chart['slug']}",
        "attributions": [
            {
                "kind": "Data",
                "label": "BlockHorizon",
                "url": SOURCE_DASHBOARD_URL,
            }
        ],
        "allow_scale_toggle": bool((chart.get("toolbar_config") or {}).get("has_scale")),
        "default_scale": "log" if (price_trace or default_log) else "linear",
        "scale_axes": ["y"],
        "x_value_type": "date",
        "show_range_selector": bool((chart.get("toolbar_config") or {}).get("has_date", True)),
        "show_halvings_default": bool(chart.get("show_halvings")),
        "main_series_key": main_series_key,
        "signal_view": _signal_view_config(chart),
        "value_zones": style_config.get("valueZones") or [],
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


def _manifest_entry(chart_id: str, title: str, order: int, section_name) -> dict:
    section_id = _section_id(title)
    description = "Historical on-chain series, refreshed during the Fintech site build."
    return {
        "id": chart_id,
        "title": title,
        "section_id": section_id,
        "section": section_name(section_id),
        "description": description,
        "image_path": None,
        "kind": "interactive",
        "data_path": f"web/data/bitcoin/{chart_id}.json",
        "order": 10_000 + order,
        "image_exists": False,
        "source_label": "BlockHorizon",
        "source_url": f"https://charts.blockhorizon.io/charts/{chart_id}",
        "attributions": [
            {
                "kind": "Data",
                "label": "BlockHorizon",
                "url": SOURCE_DASHBOARD_URL,
            }
        ],
    }


def import_reference_charts(output_dir: Path, section_name, *, timeout: int = 90) -> list[dict]:
    """Download, convert, and write the reviewed public reference chart set."""
    bundle, built_at = _fetch_bundle(timeout=timeout)
    charts_by_slug = {}
    for chart in bundle:
        slug = chart.get("slug")
        if not slug or slug in charts_by_slug:
            raise RuntimeError(f"BlockHorizon bundle contains an invalid or duplicate chart slug: {slug}")
        charts_by_slug[slug] = chart
    missing = sorted((set(REFERENCE_CHARTS) | {"price"}) - set(charts_by_slug))
    if missing:
        raise RuntimeError(
            "BlockHorizon bundle is missing reviewed charts; publishing stopped "
            f"until the upstream catalog is reviewed: {', '.join(missing)}"
        )
    price_chart = charts_by_slug["price"]

    # Validate every payload before changing any output. A partial import or a
    # stale cache must never make upstream schema/catalog drift look successful.
    payloads = []
    manifest_entries = []
    for order, slug in enumerate(REFERENCE_CHARTS):
        if slug in REFERENCE_EQUIVALENTS:
            continue
        source_chart = charts_by_slug[slug]
        if not str(source_chart.get("name") or "").strip():
            raise RuntimeError(f"BlockHorizon chart is missing its display title: {slug}")
        payload = _build_payload(source_chart, price_chart, built_at)
        if not payload["series"]:
            raise RuntimeError(f"BlockHorizon chart has no renderable public series: {slug}")
        payloads.append(payload)
        manifest_entries.append(_manifest_entry(slug, payload["title"], order, section_name))

    output_dir.mkdir(parents=True, exist_ok=True)
    for payload in payloads:
        path = output_dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    for slug in RETIRED_CHARTS:
        (output_dir / f"{slug}.json").unlink(missing_ok=True)
    return manifest_entries
