const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const DAY = 86400000;
const dates = (count, step, end = Date.UTC(2026, 10, 8)) => Array.from({ length: count }, (_, index) => (
  new Date(end - (count - 1 - index) * step * DAY).toISOString().slice(0, 10)
));

function button(range) {
  const attributes = {};
  return {
    dataset: { range }, disabled: false, title: "", attributes,
    classList: { toggle() {} },
    setAttribute(name, value) { attributes[name] = value; },
    removeAttribute(name) { delete attributes[name]; },
  };
}

function fixture() {
  const buttons = ["1m", "3m", "6m", "ytd", "1y", "4y", "all"].map(button);
  const label = { textContent: "", hidden: true, title: "" };
  const target = { innerHTML: "", _fullLayout: { xaxis: { range: ["2009-01-01", "2026-11-08"] } } };
  const zooms = [];
  target._fintechNavigation = {
    zoomTo: async (range) => { zooms.push(range); },
    reset: async () => { zooms.push("reset"); },
  };
  const context = vm.createContext({
    window: { location: { search: "" }, Plotly: {} },
    document: {
      body: { dataset: {} },
      addEventListener() {},
      querySelector: (selector) => (selector === "#chart-resolution" ? label : selector === "#terminal-plot" ? target : null),
      querySelectorAll: (selector) => (selector === "[data-range]" ? buttons : []),
    },
    URLSearchParams, Intl, Date,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);
  vm.runInContext("syncTerminalUrl = () => {}; announceChartStatus = () => {};", context);
  const byRange = Object.fromEntries(buttons.map((item) => [item.dataset.range, item]));
  return { context, buttons: byRange, label, zooms };
}

const payload = (step, extra = {}) => ({
  x_value_type: "date",
  series: [{ type: "scatter", name: "BTC price", source_key: "price", x: dates(600, step), y: dates(600, step).map((_, index) => index + 1) }],
  ...extra,
});

test("cadence comes from native_resolution, or from the densest date series", () => {
  const { context } = fixture();
  assert.equal(context.payloadCadenceDays(payload(1, { native_resolution: "weekly" })), 7, "declared resolution wins");
  assert.equal(context.payloadCadenceDays(payload(7)), 7);
  assert.equal(context.payloadCadenceDays(payload(1)), 1);
  assert.equal(context.payloadCadenceDays({ x_value_type: "category", series: [] }), null);
});

test("weekly charts label their data and disable shortcuts shorter than eight observations", () => {
  const { context, buttons, label } = fixture();
  context.updateResolutionControls(payload(7, { native_resolution: "weekly" }));
  assert.equal(label.textContent, "Weekly data");
  assert.equal(label.hidden, false);
  assert.equal(buttons["1m"].disabled, true, "one month holds about four weekly points");
  assert.equal(buttons["1m"].attributes["aria-disabled"], "true");
  assert.match(buttons["1m"].title, /fewer than 8 points/);
  for (const range of ["3m", "6m", "1y", "4y", "all"]) assert.equal(buttons[range].disabled, false, `${range} stays available`);
});

test("monthly charts keep only ranges with at least eight months", () => {
  const { context, buttons, label } = fixture();
  context.updateResolutionControls(payload(30.44, { native_resolution: "monthly" }));
  assert.equal(label.textContent, "Monthly data");
  for (const range of ["1m", "3m", "6m"]) assert.equal(buttons[range].disabled, true, `${range} disabled`);
  for (const range of ["1y", "4y", "all"]) assert.equal(buttons[range].disabled, false, `${range} available`);
});

test("daily charts have no label and every shortcut; switching charts restores buttons", () => {
  const { context, buttons, label } = fixture();
  context.updateResolutionControls(payload(7, { native_resolution: "weekly" }));
  context.updateResolutionControls(payload(1));
  assert.equal(label.hidden, true);
  assert.equal(label.textContent, "");
  for (const item of Object.values(buttons)) {
    assert.equal(item.disabled, false);
    assert.equal(item.attributes["aria-disabled"], undefined);
  }
  context.updateResolutionControls(payload(7, { native_resolution: "weekly" }));
  context.updateResolutionControls(null);
  assert.equal(buttons["1m"].disabled, false, "image charts clear the previous chart's state");
  assert.equal(label.hidden, true);
});

test("a shared 1M link on weekly data opens the shortest range it can fill", async () => {
  const { context, zooms } = fixture();
  const weekly = payload(7, { native_resolution: "weekly" });
  assert.equal(context.availableRangeShortcut(weekly, "1m"), "3m");
  assert.equal(context.availableRangeShortcut(weekly, "3m"), "3m");
  assert.equal(context.availableRangeShortcut(payload(1), "1m"), "1m");
  context.weekly = weekly;
  vm.runInContext("appState.currentPayload = weekly", context);
  await context.setChartRange("1m");
  assert.equal(vm.runInContext("appState.chartOptions.range", context), "3m");
  const [start, end] = zooms.at(-1).map((value) => new Date(value).getTime());
  assert.ok((end - start) / DAY >= 89, "zooms to three months");
});
