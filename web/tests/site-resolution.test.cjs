const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const DAY = 86400000;
const iso = (time) => new Date(time).toISOString().slice(0, 10);
const series = (dates, values = dates.map((_, index) => index + 1)) => ({ type: "scatter", name: "BTC price", source_key: "price", x: dates, y: values });
const payload = (dates, extra = {}, values) => ({ x_value_type: "date", series: [series(dates, values)], ...extra });
// `count` samples every `step` days ending on `end`.
const ending = (end, count, step) => Array.from({ length: count }, (_, index) => iso(end - (count - 1 - index) * step * DAY));

function button(range) {
  const attributes = {};
  return {
    dataset: { range }, disabled: false, title: "", attributes,
    classList: { toggle() {} },
    setAttribute(name, value) { attributes[name] = String(value); },
    getAttribute(name) { return attributes[name] ?? null; },
    removeAttribute(name) { delete attributes[name]; if (name === "title") this.title = ""; },
  };
}

function fixture() {
  const buttons = ["1m", "3m", "6m", "ytd", "1y", "4y", "all"].map(button);
  const nodes = {
    "#chart-resolution": { textContent: "", hidden: true, title: "" },
    "#chart-range-note": { textContent: "", hidden: true },
    "#terminal-status": { textContent: "" },
  };
  const target = { innerHTML: "", _fullLayout: { xaxis: { range: ["2009-01-01", "2026-11-08"] } } };
  const zooms = [];
  target._fintechNavigation = {
    zoomTo: async (range) => { zooms.push(range); },
    reset: async () => { zooms.push("reset"); },
  };
  nodes["#terminal-plot"] = target;
  const context = vm.createContext({
    window: { location: { search: "" }, Plotly: {} },
    document: {
      body: { dataset: {} },
      addEventListener() {},
      querySelector: (selector) => nodes[selector] || null,
      querySelectorAll: (selector) => (selector === "[data-range]" ? buttons : []),
    },
    URLSearchParams, Intl, Date,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);
  vm.runInContext("syncTerminalUrl = () => {}; announceChartStatus = () => {};", context);
  const byRange = Object.fromEntries(buttons.map((item) => [item.dataset.range, item]));
  return { context, buttons: byRange, chip: nodes["#chart-resolution"], note: nodes["#chart-range-note"], status: nodes["#terminal-status"], zooms };
}

const END = Date.UTC(2026, 10, 8); // Sunday
const weekly = (extra) => payload(ending(END, 600, 7), extra);

test("cadence for the label comes from native_resolution, or from long date series", () => {
  const { context } = fixture();
  assert.equal(context.payloadCadenceDays(payload(ending(END, 600, 1), { native_resolution: "weekly" })), 7, "declared resolution names the label");
  assert.equal(context.payloadCadenceDays(weekly()), 7);
  assert.equal(context.payloadCadenceDays(payload(ending(END, 600, 1))), 1);
  assert.equal(context.payloadCadenceDays(payload(ending(END, 10, 7))), null, "short series are not inferred");
  assert.equal(context.payloadCadenceDays({ x_value_type: "category", series: [] }), null);
});

test("weekly charts mark 1M unavailable but keep it focusable and described", () => {
  const { context, buttons, chip, note } = fixture();
  context.updateResolutionControls(weekly({ native_resolution: "weekly" }));
  assert.equal(chip.textContent, "Weekly data");
  assert.equal(chip.hidden, false);
  assert.equal(buttons["1m"].disabled, false, "native disabled would remove it from keyboard focus");
  assert.equal(buttons["1m"].attributes["aria-disabled"], "true");
  assert.equal(buttons["1m"].attributes["aria-describedby"], "chart-range-note");
  assert.equal(note.textContent, "1M needs at least 8 weekly points");
  assert.equal(buttons["1m"].title, note.textContent);
  assert.equal(note.hidden, true, "the note appears on focus or activation");
  for (const range of ["3m", "6m", "ytd", "1y", "4y", "all"]) {
    assert.equal(buttons[range].attributes["aria-disabled"], undefined, `${range} stays available`);
  }
});

test("monthly charts list every unavailable range in one note", () => {
  const { context, buttons, chip, note } = fixture();
  const monthly = payload(Array.from({ length: 200 }, (_, index) => iso(Date.UTC(2010, index, 1))), { native_resolution: "monthly" });
  context.updateResolutionControls(monthly);
  assert.equal(chip.textContent, "Monthly data");
  for (const range of ["1m", "3m", "6m"]) assert.equal(buttons[range].attributes["aria-disabled"], "true", `${range} unavailable`);
  for (const range of ["1y", "4y", "all"]) assert.equal(buttons[range].attributes["aria-disabled"], undefined, `${range} available`);
  assert.match(note.textContent, /^1M, 3M and 6M (and YTD )?need at least 8 monthly points$/);
});

test("availability counts observations in the inclusive window: 7 unavailable, 8 and 9 available", () => {
  const { context } = fixture();
  const history = ending(Date.UTC(2025, 0, 5), 40, 7); // long weekly history well before every window
  const windows = { "1m": [Date.UTC(2026, 9, 8), END], "3m": [Date.UTC(2026, 7, 8), END], ytd: [Date.UTC(2026, 0, 1), END] };
  for (const [range, [start, end]] of Object.entries(windows)) {
    for (const count of [7, 8, 9]) {
      // `count` observations spread so the first sits exactly on the window start.
      const step = (end - start) / (count - 1);
      const inside = Array.from({ length: count }, (_, index) => iso(start + Math.round(index * step / DAY) * DAY));
      const chart = payload([...history, ...inside]);
      assert.equal(context.rangeShortcutObservations(chart, range), count, `${range} window holds ${count}`);
      assert.equal(context.rangeShortcutUnavailable(chart, range), count < 8, `${range} with ${count} observations`);
    }
  }
});

test("missing values and dates do not count as observations", () => {
  const { context } = fixture();
  const history = ending(Date.UTC(2025, 0, 5), 40, 7);
  const inside = ending(END, 9, 3); // nine dates inside 1M
  const values = [...history.map(() => 1), 1, null, 1, "", 1, 1, 1, 1, 1];
  const chart = payload([...history, ...inside], {}, values);
  assert.equal(context.rangeShortcutObservations(chart, "1m"), 7);
  assert.equal(context.rangeShortcutUnavailable(chart, "1m"), true);
  const undated = payload([...history, ...inside.slice(0, 7), "not-a-date", null]);
  assert.equal(context.rangeShortcutObservations(undated, "1m"), 7);
});

test("eight YTD Sundays keep YTD available and a shared YTD link stays YTD", async () => {
  const { context, zooms } = fixture();
  const chart = payload(ending(Date.UTC(2026, 1, 22), 120, 7), { native_resolution: "weekly" });
  assert.equal(context.rangeShortcutObservations(chart, "ytd"), 8);
  assert.equal(context.rangeShortcutUnavailable(chart, "ytd"), false);
  assert.equal(context.availableRangeShortcut(chart, "ytd"), "ytd");
  context.chart = chart;
  vm.runInContext("appState.currentPayload = chart", context);
  await context.setChartRange("ytd");
  assert.equal(vm.runInContext("appState.chartOptions.range", context), "ytd");
  assert.equal(zooms.at(-1)[0], "2026-01-01T00:00:00.000Z");
});

test("short series impose no limit whether or not they declare a resolution", () => {
  const { context, buttons } = fixture();
  const dates = ending(END, 10, 7);
  for (const chart of [payload(dates, { native_resolution: "weekly" }), payload(dates)]) {
    context.updateResolutionControls(chart);
    assert.deepEqual(Object.values(buttons).map((item) => item.attributes["aria-disabled"]), Array(7).fill(undefined));
    assert.equal(context.availableRangeShortcut(chart, "1m"), "1m");
  }
});

test("daily and image charts clear the previous chart's state", () => {
  const { context, buttons, chip, note } = fixture();
  context.updateResolutionControls(weekly({ native_resolution: "weekly" }));
  context.updateResolutionControls(payload(ending(END, 600, 1)));
  assert.equal(chip.hidden, true);
  assert.equal(note.textContent, "");
  for (const item of Object.values(buttons)) assert.equal(item.attributes["aria-disabled"], undefined);
  context.updateResolutionControls(weekly({ native_resolution: "weekly" }));
  context.updateResolutionControls(null);
  assert.equal(buttons["1m"].attributes["aria-disabled"], undefined);
  assert.equal(chip.hidden, true);
});

test("a shared 1M link on weekly data opens the shortest range it can fill", async () => {
  const { context, zooms } = fixture();
  const chart = weekly({ native_resolution: "weekly" });
  assert.equal(context.availableRangeShortcut(chart, "1m"), "3m");
  assert.equal(context.availableRangeShortcut(chart, "3m"), "3m");
  assert.equal(context.availableRangeShortcut(payload(ending(END, 600, 1)), "1m"), "1m");
  context.chart = chart;
  vm.runInContext("appState.currentPayload = chart", context);
  await context.setChartRange("1m");
  assert.equal(vm.runInContext("appState.chartOptions.range", context), "3m");
  const [start, end] = zooms.at(-1).map((value) => new Date(value).getTime());
  assert.ok((end - start) / DAY >= 89, "zooms to three months");
});

test("activating an unavailable shortcut shows and announces the reason instead of zooming", () => {
  const { context, buttons, note, chip, status, zooms } = fixture();
  context.updateResolutionControls(weekly({ native_resolution: "weekly" }));
  context.explainUnavailableRange(buttons["1m"]);
  assert.equal(note.hidden, false);
  assert.equal(chip.hidden, true, "the note takes the label's place");
  assert.equal(status.textContent, "1M needs at least 8 weekly points");
  assert.equal(zooms.length, 0);
  context.showRangeNote(false);
  assert.equal(note.hidden, true);
  assert.equal(chip.hidden, false);
});
