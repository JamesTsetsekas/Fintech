const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8");

function chartContext(payload) {
  const calls = [];
  const plotly = { relayout(_target, update) { calls.push(update); } };
  class FixedDate extends Date {
    constructor(...args) { super(...(args.length ? args : ["2026-10-20T12:00:00Z"])); }
    static now() { return new Date("2026-10-20T12:00:00Z").getTime(); }
  }
  const context = {
    window: { location: { search: "" }, Plotly: plotly },
    document: {
      body: { dataset: {} },
      addEventListener() {},
      querySelector() { return {}; },
      querySelectorAll() { return []; },
    },
    Plotly: plotly,
    URLSearchParams,
    Intl,
    Date: FixedDate,
    payload,
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  vm.runInContext("appState.currentPayload = payload", context);
  return { context, calls };
}

test("date shortcuts anchor to observed prices instead of future model projections", () => {
  const { context, calls } = chartContext({
    x_value_type: "date",
    series: [
      { name: "Model", x: ["2026-10-20", "2032-04-09"], y: [100, 200] },
      { name: "Price", source_key: "price", x: ["2025-10-19", "2026-10-19", "2026-10-20"], y: [70, 80, null] },
    ],
  });
  context.setChartRange("1y");
  assert.deepEqual(Array.from(calls[0]["xaxis.range"]), ["2025-10-19T00:00:00.000Z", "2026-10-19T00:00:00.000Z"]);
});

test("OHLC shortcuts use the most recent finite close and ignore future candles", () => {
  const { context, calls } = chartContext({
    x_value_type: "date",
    series: [{ type: "candlestick", x: ["2026-10-19", "2026-10-20", "2026-10-21"], close: [80, 90, 100] }],
  });
  context.setChartRange("ytd");
  assert.deepEqual(Array.from(calls[0]["xaxis.range"]), ["2026-01-01T00:00:00.000Z", "2026-10-20T00:00:00.000Z"]);
});

test("metric shortcuts consider all series when no observed price is present", () => {
  const { context, calls } = chartContext({
    x_value_type: "date",
    series: [
      { name: "Earlier metric", x: ["2020-01-01"], y: [1] },
      { name: "Later metric", x: ["2026-10-19", "2026-10-21"], y: [2, 3] },
    ],
  });
  context.setChartRange("1m");
  assert.equal(calls[0]["xaxis.range"][1], "2026-10-19T00:00:00.000Z");
});

test("categorical and invalid date ranges reset without inventing dates", () => {
  for (const payload of [
    { x_value_type: "category", series: [{ x: [2024, 2026], y: [1, 2] }] },
    { x_value_type: "date", series: [{ x: ["invalid"], y: [1] }] },
  ]) {
    const { context, calls } = chartContext(payload);
    assert.doesNotThrow(() => context.setChartRange("1y"));
    assert.equal(calls[0]["xaxis.autorange"], true);
  }
});

function renderHeatmap(signals, columns, options) {
  const { context } = chartContext(null);
  const target = { innerHTML: "", classList: { remove() {} } };
  context.renderSignalHeatmap(target, signals, columns, options);
  return target.innerHTML;
}

function heatmapRows(markup) {
  return markup.split('<span class="heatmap-label"').slice(1).map((row) => (
    [...row.matchAll(/<span class="heatmap-cell([^\"]*)" title="([^\"]*)"><\/span>/g)].map((cell) => ({ classes: cell[1], title: cell[2] }))
  ));
}

test("signal rows share dates, carry prior observations, and leave uncovered periods empty", () => {
  const signals = [
    { label: "Early", points: [{ date: "2026-01-01", score: 10 }, { date: "2026-01-05", score: 90 }] },
    { label: "Later", points: [{ date: "2026-01-02", score: 30 }, { date: "2026-01-04", score: 70 }] },
  ];
  const markup = renderHeatmap(signals, 5);
  const rows = heatmapRows(markup);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map((row) => row.length), [5, 5]);
  assert.match(rows[0][2].title, /Jan 3, 2026/);
  assert.match(rows[1][2].title, /Jan 3, 2026/);
  assert.match(rows[1][2].classes, /phase-bearish/);
  assert.match(rows[1][0].title, /No data/);
  assert.match(rows[1][4].title, /No data/);
  assert.doesNotMatch(rows[1][0].classes, /phase-/);
  assert.doesNotMatch(rows[1][4].classes, /phase-/);
});

test("timeline cutoff keeps the prior observation at the first visible date", () => {
  const markup = renderHeatmap([
    { label: "Metric", points: [{ date: "2025-12-01", score: 10 }, { date: "2026-01-05", score: 90 }] },
  ], 3, { startDate: "2026-01-01" });
  const row = heatmapRows(markup)[0];
  assert.equal(row.length, 3);
  assert.match(row[0].title, /Jan 1, 2026/);
  assert.match(row[0].classes, /phase-bottom/);
  assert.match(row[2].title, /Jan 5, 2026/);
});

test("a short or empty signal history retains every grid column", () => {
  const markup = renderHeatmap([
    { label: "One", points: [{ date: "2026-01-01", score: 10 }, { date: "2026-01-02", score: 90 }] },
    { label: "Empty", points: [] },
  ], 8);
  assert.deepEqual(heatmapRows(markup).map((row) => row.length), [8, 8]);
});
