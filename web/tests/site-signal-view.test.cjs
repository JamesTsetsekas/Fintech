const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function context() {
  const scope = {
    window: { location: { search: "" } },
    document: { body: { dataset: {} }, addEventListener() {} },
    URL, URLSearchParams, Intl,
  };
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, "../assets/site.js"), "utf8"), scope);
  return scope;
}

function payload() {
  return {
    id: "mvrv-z-score", x_value_type: "date",
    signal_view: { mode: "absolute", series_key: "mvrv_z_score", min: 0, max: 5 },
    value_zones: [{ seriesKey: "mvrv_z_score", greenBelow: .85, redAbove: 1.75 }],
    series: [
      { source_key: "price", name: "BTC price", type: "scatter", mode: "lines", axis: "y", x: ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"], y: [100, 200, 300, 400], line: { color: "#eef3f8" } },
      { source_key: "mvrv_z_score", name: "MVRV Z-Score", type: "scatter", mode: "lines", axis: "y2", x: ["2026-01-01", "2026-01-03", "2026-01-04"], y: [0, 2.5, 5], line: { color: "#c96442" } },
    ],
    layout: { yaxis: { type: "log", tickprefix: "$" }, yaxis2: { side: "right", overlaying: "y" } },
  };
}

test("signal mode colors actual BTC observations by exact-date metric values without changing canonical data", () => {
  const scope = context();
  const source = payload();
  const original = JSON.stringify(source);
  assert.equal(scope.chartDisplaySeries(source), source.series, "normal mode retains both canonical lines");
  const displayed = scope.chartDisplaySeries(source, { signalView: true });
  assert.equal(displayed.length, 1);
  const price = displayed[0];
  assert.equal(price.source_key, "price");
  assert.equal(price.mode, "markers");
  assert.equal(price.marker.size, 8);
  assert.equal(price.y, source.series[0].y, "price values are observations, not metric values");
  assert.equal(price.marker.color[0], "#0106f5");
  assert.equal(price.marker.color[1], "rgba(0,0,0,0)", "missing dates do not carry or interpolate an unobserved metric");
  assert.equal(price.marker.color[3], "#ea5149");
  assert.equal(price.signal_metric_values[2], 2.5);
  assert.equal(JSON.stringify(source), original);
  const layout = scope.chartDisplayLayout(source, { signalView: true });
  assert.equal(layout.yaxis2, undefined);
  assert(source.layout.yaxis2, "normal mode's metric axis remains intact");
  assert.equal(scope.chartValueZoneShapes(source, { signalView: true }).length, 0);
});

test("ratio signals normalize price divided by metric while preserving the original metric tooltip", () => {
  const scope = context();
  const source = payload();
  source.signal_view.mode = "error";
  source.signal_view.min = 0;
  source.signal_view.max = 4;
  source.series[1].y = [50, 150, 0];
  const price = scope.chartDisplaySeries(source, { signalView: true })[0];
  assert.equal(price.marker.color[0], price.marker.color[2], "equal price/cost-basis ratios have equal colors");
  assert.equal(price.marker.color[3], "rgba(0,0,0,0)", "zero denominators cannot generate a signal");
  assert.equal(price.signal_metric_values[0], 50);
  scope.applyReadableHover(price);
  assert(price.hovertext[0].includes("MVRV Z-Score: 50"));
});

test("normal value-zone shading references the metric axis and keeps source thresholds", () => {
  const scope = context();
  const shapes = scope.chartValueZoneShapes(payload());
  assert.equal(shapes.length, 2);
  assert(shapes.every((shape) => shape.yref === "y2" && shape.layer === "below"));
  assert.equal(shapes[0].y1, .85);
  assert.equal(shapes[1].y0, 1.75);
});

test("colored lines connect adjacent observations, retain real gaps, and toggle as one legend item", () => {
  const scope = context();
  const series = {
    source_key: "nupl", name: "NUPL", type: "scatter", mode: "lines", value_colored_line: true,
    x: [1, 2, 3, 4, 5], y: [.1, .2, null, .6, .7],
    marker: { color: ["#ef7f11", "#ef7f11", "#ef7f11", "#24c813", "#24c813"], size: 0 },
    line: { width: 2 },
  };
  const traces = scope.expandGradientLine(series);
  const visible = traces.filter((trace) => !trace.meta?.fintechHelper);
  assert.equal(visible.length, 2);
  assert.deepEqual(Array.from(visible[0].x), [1, 2, null]);
  assert.deepEqual(Array.from(visible[1].x), [4, 5, null]);
  assert(visible.every((trace) => trace.mode === "lines" && !trace.marker));
  assert.equal(new Set(traces.map((trace) => trace.legendgroup)).size, 1);
  assert.equal(visible.filter((trace) => trace.showlegend).length, 1);
  assert.equal(traces.at(-1).x, series.x);
  assert.equal(traces.at(-1).marker.color, series.marker.color);
  assert.equal(series.y[2], null);
});

test("intentional PlanB and financial scatter semantics are preserved", () => {
  const scope = context();
  for (const series of [
    { type: "scatter", mode: "markers", x: [1, 2], y: [1, 2], marker: { color: "#858585", size: 3.2 } },
    { type: "scatter", mode: "lines+markers", x: [1, 2], y: [100, 200], marker: { color: ["#ea5149", "#0106f5"], size: 6 } },
    { type: "candlestick", x: [1, 2], open: [1, 2], high: [2, 3], low: [0, 1], close: [1, 2] },
  ]) assert.equal(scope.expandGradientLine(series)[0], series);
});

test("continuous gradients use color values rather than the plotted price coordinate", () => {
  const scope = context();
  const traces = scope.expandGradientLine({
    type: "scatter", mode: "lines", name: "Projected price", x: [1, 2], y: [100000, 120000],
    marker: { color: [0, 0], cmin: 0, cmax: 5, colorscale: [[0, "#0000ff"], [1, "#ff0000"]] },
  });
  assert.equal(traces[0].line.color, "#0500fa", "low metric values remain blue even when BTC price is high");
});

test("Signal view toolbar toggles its shareable URL and pressed state", async () => {
  const scope = context();
  scope.window.location.href = "https://example.test/charts/?chart=mvrv-z-score";
  const urls = [];
  scope.history = { replaceState(_state, _title, url) { urls.push(url.href); scope.window.location.href = url.href; } };
  const states = [];
  const attributes = {};
  const button = { classList: { toggle(_name, value) { states.push(value); } }, setAttribute(name, value) { attributes[name] = value; } };
  vm.runInContext("appState.currentChart = { id: 'mvrv-z-score' }; appState.currentPayload = { signal_view: {} }; renderTerminalPlot = async () => {};", scope);
  await scope.handleChartAction("signals", button);
  assert.equal(new URL(urls[0]).searchParams.get("signals"), "1");
  assert.equal(attributes["aria-pressed"], "true");
  await scope.handleChartAction("signals", button);
  assert.equal(new URL(urls[1]).searchParams.has("signals"), false);
  assert.equal(attributes["aria-pressed"], "false");
  assert.deepEqual(states, [true, false]);
});
