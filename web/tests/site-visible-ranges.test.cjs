const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const context = {
  window: { location: { search: "" } },
  document: { body: { dataset: {} }, addEventListener() {} },
  URLSearchParams, Intl,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);

function fit(data, range, axes = {}, layout = {}) {
  const target = { data, layout, _fullLayout: { xaxis: { type: "linear" }, yaxis: { type: "linear", range: [0, 100] }, ...axes } };
  assert.equal(typeof context.visibleChartYRanges, "function");
  return JSON.parse(JSON.stringify(context.visibleChartYRanges(target, range)));
}

function closeRange(actual, expected) {
  assert.equal(actual?.length, 2);
  expected.forEach((value, index) => assert(Math.abs(actual[index] - value) < 1e-9, `${actual[index]} ≈ ${value}`));
}

test("visible dates refit price without the out-of-window history", () => {
  const result = fit([{ x: ["2024-01-01", "2025-01-01", "2026-01-01"], y: [1, 100, 110] }],
    ["2025-01-01", "2026-01-01"], { xaxis: { type: "date" } });
  closeRange(result.yaxis, [99.4, 110.6]);
});

test("numeric windows use only visible extrema including descending X", () => {
  const result = fit([{ x: [4, 3, 2, 1, 0], y: [1000, 8, 6, 4, -1000] }], [1, 3]);
  closeRange(result.yaxis, [3.76, 8.24]);
});

test("each pane and overlay axis gets its own visible range", () => {
  const result = fit([
    { x: [0, 1, 2], y: [1, 10, 20] },
    { x: [0, 1, 2], y: [3, 0.2, 0.4], yaxis: "y2" },
    { x: [0, 1, 2], y: [1000, -2, 2], yaxis: "y3" },
  ], [1, 2], { yaxis2: { type: "linear" }, yaxis3: { type: "linear" } });
  closeRange(result.yaxis, [9.4, 20.6]);
  closeRange(result.yaxis2, [0.188, 0.412]);
  closeRange(result.yaxis3, [-2.24, 2.24]);
});

test("log-price ranges use log coordinates and exclude invalid prices", () => {
  const result = fit([{ x: [0, 1, 2, 3, 4], y: [0, -1, 10, 1000, null] }], [0, 4], { yaxis: { type: "log" } });
  closeRange(result.yaxis, [0.88, 3.12]);
});

test("OHLC fitting includes highs and lows rather than just closing prices", () => {
  for (const type of ["candlestick", "ohlc"]) {
    const result = fit([{ type, x: [0, 1, 2], open: [1, 15, 80], close: [1, 20, 90], high: [2, 30, 100], low: [0.5, 10, 70] }], [1, 1]);
    closeRange(result.yaxis, [8.8, 31.2]);
  }
});

test("hidden series, helper metadata, and secondary X data do not distort fitting", () => {
  const result = fit([
    { x: [0, 1], y: [10, 20] },
    { x: [0, 1], y: [-1000, 1000], visible: false },
    { x: [0, 1], y: [-1000, 1000], visible: "legendonly" },
    { x: [0, 1], y: [-1000, 1000], meta: { fintechHelper: true } },
    { x: [0, 1], y: [-1000, 1000], xaxis: "x2" },
    { x: [0, 1], y: [-1000, 1000], opacity: 0 },
  ], [0, 1]);
  closeRange(result.yaxis, [9.4, 20.6]);
});

test("nulls, missing values, blanks, booleans, and nonfinite values are not zeros", () => {
  const result = fit([{ mode: "markers", x: [0, 1, 2, 3, 4, 5, 6, 7, 8], y: [null, undefined, "", false, NaN, Infinity, 10, "20", true] }], [0, 8]);
  closeRange(result.yaxis, [9.4, 20.6]);
});

test("crossing sparse line segments contribute interpolated boundary values", () => {
  const result = fit([{ mode: "lines", x: [0, 10], y: [0, 100] }], [4, 6]);
  closeRange(result.yaxis, [38.8, 61.2]);
});

test("log Y boundaries interpolate in rendered log space", () => {
  const result = fit([{ mode: "lines", x: [0, 10], y: [1, 10000] }], [2.5, 7.5], { yaxis: { type: "log" } });
  closeRange(result.yaxis, [0.88, 3.12]);
});

test("log X boundaries interpolate in rendered log space", () => {
  const result = fit([{ mode: "lines", x: [1, 1000], y: [0, 30] }], [1, 2], { xaxis: { type: "log" } });
  closeRange(result.yaxis, [9.4, 20.6]);
});

test("markers and unconnected gaps do not invent crossing line segments", () => {
  assert.deepEqual(fit([{ mode: "markers", x: [0, 10], y: [0, 100] }], [4, 6]), {});
  assert.deepEqual(fit([{ mode: "lines", x: [0, 5, 10], y: [0, null, 100] }], [4, 6]), {});
  closeRange(fit([{ mode: "lines", connectgaps: true, x: [0, 5, 10], y: [0, null, 100] }], [4, 6]).yaxis, [38.8, 61.2]);
});

test("reversed Y directions survive a refit and reversed windows select the same data", () => {
  const data = [{ x: [0, 1, 2], y: [10, 20, 30] }];
  closeRange(fit(data, [2, 1], { yaxis: { type: "linear", range: [100, 0] } }).yaxis, [30.6, 19.4]);
  closeRange(fit(data, [1, 2], { yaxis: { type: "linear", autorange: "reversed" } }).yaxis, [30.6, 19.4]);
});

test("single values receive stable nonzero padding in linear and log space", () => {
  closeRange(fit([{ x: [1], y: [0] }], [1, 1]).yaxis, [-0.06, 0.06]);
  closeRange(fit([{ x: [1], y: [100] }], [1, 1]).yaxis, [94, 106]);
  closeRange(fit([{ x: [1], y: [100] }], [1, 1], { yaxis: { type: "log" } }).yaxis, [1.94, 2.06]);
});

test("fixed or categorical axes and heatmaps are left alone", () => {
  assert.deepEqual(fit([{ x: [0, 1], y: [1, 2] }], [0, 1], { yaxis: { fixedrange: true } }), {});
  assert.deepEqual(fit([{ x: [0, 1], y: [1, 2] }], [0, 1], { yaxis: { type: "category" } }), {});
  assert.deepEqual(fit([{ x: [0, 1], y: [1, 2] }], [0, 1], { xaxis: { type: "category" } }), {});
  assert.deepEqual(fit([{ type: "heatmap", x: [0, 1], y: [1, 2], z: [[1, 2]] }], [0, 1]), {});
  assert.deepEqual(fit([{ type: "bar", orientation: "h", x: [0, 1], y: [1, 2] }], [0, 1]), {});
});

test("NUPL's configured sentiment scale and fixed ticks survive a recent price zoom", () => {
  const metric = { type: "linear", range: [-2, 1], tickvals: [-2, -1, 0, 1] };
  const result = fit([
    { x: [0, 1, 2], y: [100, 200, 300] },
    { x: [0, 1, 2], y: [-1, 0.31, 0.38], yaxis: "y2" },
  ], [1, 2], { yaxis2: metric }, { yaxis2: metric });
  closeRange(result.yaxis, [194, 306]);
  closeRange(result.yaxis2, [-2, 1]);
});

test("configured complete percentage scales retain their semantic zero-to-one-hundred bounds", () => {
  for (const metric of [
    { type: "linear", ticksuffix: "%", range: [0, 100] },
    { type: "linear", title: "Share of history (%)", range: [0, 100] },
    { type: "linear", title: { text: "Supply band proxy (%)" }, range: [100, 0] },
  ]) {
    closeRange(fit([{ x: [0, 1, 2], y: [100, 30, 35] }], [1, 2], { yaxis: metric }, { yaxis: metric }).yaxis, metric.range);
  }
});

test("arbitrary metric ranges and partially bounded percentage ranges continue fitting", () => {
  for (const metric of [
    { type: "linear", range: [0, 100] },
    { type: "linear", title: "Puell Multiple", range: [0, 13.842] },
    { type: "linear", title: "Volatility (%)", range: [0, 484.6] },
    { type: "linear", ticksuffix: "%", range: [20, 80] },
  ]) {
    closeRange(fit([{ x: [0, 1, 2], y: [100, 30, 35] }], [1, 2], { yaxis: metric }, { yaxis: metric }).yaxis, [29.7, 35.3]);
  }
});

test("generated dollar-price ticks never freeze an axis when zooming", () => {
  const price = { type: "linear", tickprefix: "$", range: [0, 100], tickvals: [0, 20, 50, 100], tickmode: "array" };
  closeRange(fit([{ x: [0, 1, 2], y: [100, 30, 35] }], [1, 2], { yaxis: price }, { yaxis: price }).yaxis, [29.7, 35.3]);
});

test("stacked compositions and closed polygons preserve the current complete axis bounds", () => {
  for (const trace of [
    { stackgroup: "holders" },
    { fill: "toself" },
    { type: "bar" },
  ]) {
    const result = fit([{ ...trace, x: [0, 1, 2], y: [1000, 10, 20] }], [1, 2], { yaxis: { type: "linear", range: [-5, 105] } }, { barmode: "stack" });
    closeRange(result.yaxis, [-5, 105]);
  }
});

test("ribbons fit all visible boundaries while zero fills retain their baseline", () => {
  closeRange(fit([
    { x: [0, 1, 2], y: [1000, 20, 30] },
    { x: [0, 1, 2], y: [500, 10, 20], fill: "tonexty" },
  ], [1, 2]).yaxis, [8.8, 31.2]);
  closeRange(fit([{ x: [0, 1, 2], y: [1000, 10, 20], fill: "tozeroy" }], [1, 2]).yaxis, [-1.2, 21.2]);
  closeRange(fit([{ mode: "none", x: [0, 10], y: [10, 20], fill: "tozeroy" }], [4, 6]).yaxis, [-0.96, 16.96]);
});

test("Plotly timezone-free date coordinates stay in UTC", () => {
  closeRange(fit([{ x: ["2026-01-01 00:00:00", "2026-01-02 00:00:00"], y: [10, 20] }],
    ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"], { xaxis: { type: "date" } }).yaxis, [9.4, 20.6]);
});

test("ordinary bars include their baseline and explicit bases", () => {
  closeRange(fit([{ type: "bar", x: [0, 1], y: [10, 20] }], [0, 1]).yaxis, [-1.2, 21.2]);
  closeRange(fit([{ type: "bar", x: [0, 1], y: [10, 20], base: [100, 200] }], [0, 1]).yaxis, [92.8, 227.2]);
  closeRange(fit([{ type: "bar", x: [0, 1], y: [-90, 100], base: 100 }], [0, 1], { yaxis: { type: "log" } }).yaxis,
    [1 - (Math.log10(200) - 1) * 0.06, Math.log10(200) + (Math.log10(200) - 1) * 0.06]);
});

test("invalid/empty input and windows with no data do not change any axis", () => {
  assert.deepEqual(fit([], [0, 1]), {});
  assert.deepEqual(fit([{ x: [0, 1], y: [10, 20] }], [3, 4]), {});
  assert.deepEqual(fit([{ x: [0, 1], y: [10, 20] }], [null, null]), {});
  assert.deepEqual(fit([{ x: [0, 1], y: [10, 20] }], [NaN, Infinity]), {});
  assert.deepEqual(fit([{ x: ["invalid"], y: [10] }], ["2025-01-01", "2026-01-01"], { xaxis: { type: "date" } }), {});
});
