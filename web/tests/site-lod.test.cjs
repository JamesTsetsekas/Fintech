const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const DAY = 86400000;

function load() {
  const context = vm.createContext({
    window: { location: { search: "" } },
    document: { body: { dataset: {} }, addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] },
    URLSearchParams, Intl, Date,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);
  return context;
}

const site = load();
const iso = (time) => new Date(time).toISOString().slice(0, 10);
const dates = (count, start = Date.UTC(2009, 9, 6), step = DAY) => Array.from({ length: count }, (_, index) => iso(start + index * step));
// Deterministic pseudo-random walk so failures are reproducible.
function walk(count, seed = 7) {
  let state = seed;
  let value = 1000;
  return Array.from({ length: count }, () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    value *= 1 + ((state / 2147483648) - 0.5) * 0.06;
    return Number(value.toFixed(2));
  });
}
const daily = (count = 6245, extra = {}) => ({ type: "scatter", mode: "lines", name: "BTC price", lod_eligible: true, x: dates(count), y: walk(count), ...extra });
const inWindow = (trace, [start, end]) => trace.x.filter((value) => {
  const time = Date.parse(value);
  return time >= start && time <= end;
}).length;
const lastDays = (trace, days) => {
  const end = Date.parse(trace.x.at(-1));
  return [end - days * DAY, end];
};

test("zoomed windows draw every native observation in view", () => {
  const trace = daily();
  for (const maxPoints of [2200, 600]) {
    for (const [days, expected] of [[30, 31], [91, 92], [365, 366]]) {
      const range = lastDays(trace, days);
      const [drawn] = site.levelOfDetailWindow([trace], range, maxPoints);
      assert.equal(inWindow(drawn, range), expected, `${days}d window at maxPoints ${maxPoints}`);
      assert.ok(drawn.x.length <= maxPoints, "total drawn points stay within the budget");
      const native = trace.x.map((value, index) => [value, trace.y[index]]).filter(([value]) => Date.parse(value) >= range[0]);
      assert.deepEqual([...drawn.x.slice(-native.length)], native.map(([value]) => value), "the visible window is the native sequence");
      assert.deepEqual([...drawn.y.slice(-native.length)], native.map(([, value]) => value));
    }
  }
});

test("min/max buckets keep each bucket's highs and lows instead of striding past them", () => {
  const trace = daily(6245);
  trace.y = trace.y.slice();
  trace.y[3001] = 999999; // one-day spike that a stride of 3 would skip
  trace.y[4502] = 0.5; // one-day crash
  const [full] = site.levelOfDetailWindow([trace], null, 600);
  assert.ok(full.x.length <= 600);
  assert.equal(Math.max(...full.y), 999999);
  assert.equal(Math.min(...full.y), 0.5);
  assert.equal(full.x[0], trace.x[0], "first observation retained");
  assert.equal(full.x.at(-1), trace.x.at(-1), "latest observation retained");
  // Every bucket's extremes: split the full history into the same buckets.
  const buckets = Math.floor(600 / 4);
  for (let bucket = 0; bucket < buckets; bucket += 1) {
    const from = Math.floor(bucket * trace.x.length / buckets);
    const to = Math.floor((bucket + 1) * trace.x.length / buckets) - 1;
    const values = trace.y.slice(from, to + 1);
    const kept = full.x.map((value, index) => [Date.parse(value), full.y[index]])
      .filter(([time]) => time >= Date.parse(trace.x[from]) && time <= Date.parse(trace.x[to])).map(([, value]) => value);
    assert.ok(kept.includes(Math.max(...values)) && kept.includes(Math.min(...values)), `bucket ${bucket} keeps its extremes`);
  }
  // Context outside a zoomed window also keeps the global extremes.
  const [zoomed] = site.levelOfDetailWindow([trace], lastDays(trace, 30), 600);
  assert.equal(Math.max(...zoomed.y), 999999);
  assert.equal(Math.min(...zoomed.y), 0.5);
});

test("per-point arrays stay aligned with x and readable hover labels are generated per drawn point", () => {
  const trace = daily(5000, { marker: { color: dates(5000).map((_, index) => (index % 2 ? "#111111" : "#222222")) }, text: dates(5000).map((_, index) => `t${index}`), lod_hover_template: "%{y:$,.0f}" });
  const [drawn] = site.levelOfDetailWindow([trace], lastDays(trace, 200), 600);
  assert.equal(drawn.marker.color.length, drawn.x.length);
  assert.equal(drawn.text.length, drawn.x.length);
  assert.equal(drawn.hovertext.length, drawn.x.length);
  drawn.x.forEach((value, index) => {
    const source = trace.x.indexOf(value);
    assert.equal(drawn.text[index], `t${source}`);
    assert.equal(drawn.marker.color[index], trace.marker.color[source]);
    assert.equal(typeof drawn.hovertext[index], "string");
  });
});

test("candles merge into calendar-aligned buckets with honest OHLC instead of being dropped", () => {
  const count = 3000;
  const x = dates(count, Date.UTC(2017, 0, 1));
  const open = walk(count, 3);
  const close = walk(count, 5);
  const high = open.map((value, index) => Math.max(value, close[index]) * 1.02);
  const low = open.map((value, index) => Math.min(value, close[index]) * 0.98);
  const candles = { type: "candlestick", name: "BTC OHLC", lod_eligible: true, x, open, high, low, close };
  const [full] = site.levelOfDetailWindow([candles], null, 600);
  assert.ok(full.x.length <= 600 && full.x.length > 300, "daily history becomes weekly candles");
  const mondayWeek = (value) => {
    const date = new Date(Date.parse(value));
    return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) - ((date.getUTCDay() + 6) % 7) * DAY;
  };
  full.x.forEach((label, bucket) => {
    const members = x.map((value, index) => index).filter((index) => mondayWeek(x[index]) === mondayWeek(label));
    assert.equal(label, x[members[0]], "labelled with the bucket's first observation");
    assert.equal(full.open[bucket], open[members[0]]);
    assert.equal(full.close[bucket], close[members.at(-1)]);
    assert.equal(full.high[bucket], Math.max(...members.map((index) => high[index])));
    assert.equal(full.low[bucket], Math.min(...members.map((index) => low[index])));
  });
  assert.equal(Math.max(...full.high), Math.max(...high), "the all-time high survives aggregation");
  // Zoomed: native daily candles in view; labels stay native dates so the
  // closest pair (which sets every candle's width) is still one day apart.
  const range = lastDays(candles, 90);
  const [zoomed] = site.levelOfDetailWindow([candles], range, 600);
  assert.equal(inWindow(zoomed, range), 91);
  const times = zoomed.x.map(Date.parse);
  assert.ok(times.every((time, index) => !index || time - times[index - 1] >= DAY), "no two candles closer than the native cadence");
  // Weekly candles aggregate into months.
  const weekly = { ...candles, x: dates(count, Date.UTC(1970, 0, 4), 7 * DAY) };
  const [months] = site.levelOfDetailWindow([weekly], null, 600);
  const monthOf = (value) => value.slice(0, 7);
  assert.equal(new Set(months.x.map(monthOf)).size, months.x.length, "one candle per calendar month");
});

test("stacked and filled traces share x-only buckets so their geometry stays aligned", () => {
  const x = dates(6245);
  const stack = [1, 2, 3].map((seed) => ({ type: "scatter", stackgroup: "s", lod_eligible: true, x, y: walk(6245, seed) }));
  for (const range of [null, [Date.parse(x[4000]), Date.parse(x[4300])]]) {
    const drawn = site.levelOfDetailWindow(stack, range, 600);
    assert.deepEqual(drawn[1].x, drawn[0].x);
    assert.deepEqual(drawn[2].x, drawn[0].x);
    assert.ok(drawn[0].x.length <= 600);
  }
});

test("traces that must not be reduced are returned untouched", () => {
  const ineligible = daily(6245, { lod_eligible: false });
  const heatmap = { type: "heatmap", x: dates(3000), y: ["a", "b"], z: [walk(3000), walk(3000, 9)] };
  const gradient = { type: "scatter", mode: "lines", x: ["2020-01-01", "2020-01-02", null, "2020-01-03"], y: [1, 2, null, 3] };
  const signal = daily(6245, { lod_eligible: false, signal_metric_values: walk(6245) });
  const helper = daily(6245, { lod_eligible: false, meta: { fintechHelper: true } });
  const categories = { type: "bar", lod_eligible: true, x: ["Jan", "Feb", "Mar"], y: [1, 2, 3] };
  const input = [ineligible, heatmap, gradient, signal, helper, categories];
  const output = site.levelOfDetailWindow(input, [Date.UTC(2020, 0, 1), Date.UTC(2020, 1, 1)], 600);
  input.forEach((trace, index) => assert.equal(output[index], trace, `trace ${index} is the same object`));
  // A short eligible series is drawn whole (only styling may change).
  const short = daily(500);
  const [whole] = site.levelOfDetailWindow([short], null, 2200);
  assert.deepEqual(whole.x, short.x);
  assert.deepEqual(whole.y, short.y);
});

test("sparse windows gain markers; dense views stay plain lines", () => {
  const weekly = { ...daily(900), x: dates(900, Date.UTC(2009, 0, 4), 7 * DAY), line: { color: "#2863a7" } };
  const [zoomed] = site.levelOfDetailWindow([weekly], lastDays(weekly, 365), 2200);
  assert.equal(zoomed.mode, "lines+markers");
  assert.equal(zoomed.marker.color, "#2863a7", "markers match the line color");
  const [full] = site.levelOfDetailWindow([weekly], null, 2200);
  assert.equal(full.mode, "lines");
  const filled = { ...weekly, fill: "tozeroy" };
  assert.equal(site.levelOfDetailWindow([filled], lastDays(weekly, 365), 2200)[0].mode, "lines", "areas never gain markers");
});

test("zoom floor is eight native samples of the densest series", () => {
  const target = (traces) => ({ _fintechLod: { source: traces, minimumSpan: null } });
  assert.equal(site.levelOfDetailMinimumSpan(target([daily(400)])), 8 * DAY);
  const weekly = { ...daily(900), x: dates(900, Date.UTC(2009, 0, 4), 7 * DAY) };
  assert.equal(site.levelOfDetailMinimumSpan(target([weekly])), 56 * DAY);
  assert.equal(site.levelOfDetailMinimumSpan(target([weekly, daily(400)])), 8 * DAY, "densest series wins");
  assert.equal(site.levelOfDetailMinimumSpan(target([daily(5)])), 0, "very short series keep the plain one-day floor");
  assert.equal(site.levelOfDetailMinimumSpan({ data: [weekly] }), 56 * DAY, "falls back to drawn data");
});

test("zone-less date strings are read as UTC like Plotly", () => {
  assert.equal(site.levelOfDetailTime("2024-01-02"), Date.UTC(2024, 0, 2));
  assert.equal(site.levelOfDetailTime("2024-01-02 12:30:00.5"), Date.UTC(2024, 0, 2, 12, 30, 0, 500));
  assert.equal(site.levelOfDetailTime("2024-01-02T12:30"), Date.UTC(2024, 0, 2, 12, 30));
  assert.ok(Number.isNaN(site.levelOfDetailTime("Q1")));
});

test("installLevelOfDetail keeps the full source and draws within the budget", () => {
  const target = {};
  const source = [daily(6245)];
  const drawn = site.installLevelOfDetail(target, source, 600);
  assert.equal(target._fintechLod.source, source);
  assert.ok(drawn[0].x.length <= 600);
  assert.equal(site.installLevelOfDetail(target, source, undefined), source, "no budget, no reduction");
  assert.equal(target._fintechLod, null);
});
