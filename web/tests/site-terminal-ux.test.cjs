const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8");

function context(extra = {}) {
  const nodes = new Map();
  const node = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, { innerHTML: "", textContent: "", hidden: false, classList: { toggle() {}, add() {}, remove() {} }, setAttribute() {} });
    return nodes.get(selector);
  };
  const scope = {
    window: { location: { search: "", href: "https://example.test/charts/" } },
    document: {
      body: { dataset: {} },
      documentElement: { dataset: {} },
      addEventListener() {},
      querySelector: node,
      querySelectorAll: () => [],
    },
    URL, URLSearchParams, Intl, console,
    ...extra,
  };
  vm.createContext(scope);
  vm.runInContext(source, scope);
  scope.nodes = nodes;
  scope.node = node;
  return scope;
}

const dates = (count, start = Date.UTC(2025, 0, 1)) => Array.from({ length: count }, (_, index) => new Date(start + index * 86_400_000).toISOString().slice(0, 10));

test("URL state parses shareable options, drops invalid values, and orders from/to", () => {
  const scope = context();
  const state = scope.parseTerminalUrlState("?chart=nupl&range=1y&scale=log&ma=1&halvings=0&grid=0&view=sheet&section=onchain&signals=1");
  assert.deepEqual(JSON.parse(JSON.stringify(state)), {
    chart: "nupl", signals: true, range: "1y", from: null, to: null, scale: "log", movingAverage: true,
    halvings: false, grid: false, view: "sheet", section: "onchain",
  });
  const invalid = scope.parseTerminalUrlState("?range=10y&scale=cubic&ma=yes&halvings=maybe&view=pie&from=2024-13-01&to=2024-02-01");
  assert.equal(invalid.range, null);
  assert.equal(invalid.scale, null);
  assert.equal(invalid.movingAverage, false);
  assert.equal(invalid.halvings, null);
  assert.equal(invalid.view, "chart");
  assert.equal(invalid.from, null, "an incomplete or invalid custom window is ignored");
  const swapped = scope.parseTerminalUrlState("?from=2025-03-01&to=2025-01-01&range=4y");
  assert.deepEqual([swapped.from, swapped.to, swapped.range], ["2025-01-01", "2025-03-01", null], "from/to wins over a range shortcut");
});

test("terminal URLs round-trip only non-default options and keep unrelated parameters", () => {
  const scope = context();
  vm.runInContext(`
    appState.activeChartId = "pb-s2f";
    appState.currentPayload = { id: "pb-s2f", x_value_type: "date", allow_scale_toggle: true, default_scale: "log", show_halvings_default: true, series: [] };
    Object.assign(appState.chartOptions, { scale: "log", halvings: true, movingAverage: false, grid: true, table: false, range: "all", customRange: null });
  `, scope);
  const plain = scope.terminalUrl(scope.terminalUrlState(), "https://example.test/charts/?chart=old&utm=keep&market=x");
  assert.equal(plain.search, "?utm=keep&chart=pb-s2f");
  vm.runInContext(`Object.assign(appState.chartOptions, { scale: "linear", halvings: false, movingAverage: true, grid: false, table: true, customRange: ["2024-01-05", "2024-03-01"] }); appState.sectionFilter = "cycle-models";`, scope);
  const url = scope.terminalUrl(scope.terminalUrlState(), "https://example.test/charts/");
  assert.equal(url.search, "?chart=pb-s2f&from=2024-01-05&to=2024-03-01&scale=linear&ma=1&halvings=0&grid=0&view=sheet&section=cycle-models");
  const parsed = scope.parseTerminalUrlState(url.search);
  assert.deepEqual([parsed.from, parsed.to, parsed.scale, parsed.movingAverage, parsed.halvings, parsed.grid, parsed.view, parsed.section],
    ["2024-01-05", "2024-03-01", "linear", true, false, false, "sheet", "cycle-models"]);
});

test("chart changes push history while option changes replace the current entry", () => {
  const calls = [];
  const scope = context();
  scope.history = {
    pushState(_state, _title, url) { calls.push(["push", url.search]); scope.window.location.href = url.href; },
    replaceState(_state, _title, url) { calls.push(["replace", url.search]); scope.window.location.href = url.href; },
  };
  vm.runInContext(`appState.activeChartId = "a";`, scope);
  scope.syncTerminalUrl({ push: true });
  scope.syncTerminalUrl({ push: true });
  vm.runInContext(`appState.chartOptions.range = "1y";`, scope);
  scope.syncTerminalUrl();
  assert.deepEqual(calls, [["push", "?chart=a"], ["replace", "?chart=a&range=1y"]], "an unchanged URL is never pushed twice");
});

test("custom zoom ranges round to whole UTC days", () => {
  const scope = context();
  assert.deepEqual(Array.from(scope.customRangeFromAxis(["2024-01-03T00:00:00.000Z", "2024-01-09T00:00:00.000Z"])), ["2024-01-03", "2024-01-08"]);
  assert.deepEqual(Array.from(scope.customRangeFromAxis(["2024-01-09T20:00:00.000Z", "2024-01-03T03:00:00.000Z"])), ["2024-01-03", "2024-01-09"]);
  assert.deepEqual(Array.from(scope.customRangeFromAxis(["2024-01-05T10:00:00Z", "2024-01-05T13:00:00Z"])), ["2024-01-05", "2024-01-05"]);
});

const library = [
  { id: "mvrv-z-score", title: "MVRV Z-Score", section: "On-Chain", section_id: "onchain", description: "Historical on-chain series, refreshed during the Fintech site build." },
  { id: "sth-mvrv", title: "MVRV Short Term Supply", section: "On-Chain", section_id: "onchain", description: "Historical on-chain series, refreshed during the Fintech site build." },
  { id: "lth-mvrv", title: "MVRV Long Term Supply", section: "On-Chain", section_id: "onchain", description: "Historical on-chain series, refreshed during the Fintech site build." },
  { id: "realized-price", title: "Realized Price", section: "On-Chain", section_id: "onchain", description: "Historical on-chain series, refreshed during the Fintech site build." },
  { id: "nupl", title: "NUPL (Net Unrealized Profit Loss)", section: "On-Chain", section_id: "onchain", description: "Historical on-chain series, refreshed during the Fintech site build." },
  { id: "pb-various", title: "PlanB: Stock to Flow + RSI + MA + Realized", section: "Cycle Models", section_id: "cycle-models", description: "Uses the MVRV ratio as one input." },
  { id: "mayer", title: "Mayer Multiple", section: "Technical", section_id: "technical", description: "Price divided by the 200-day average." },
];

test("search matches every word in any order, ignores punctuation, and ranks title hits first", () => {
  const scope = context();
  const ids = (query) => Array.from(scope.searchCharts(library, query), (chart) => chart.id);
  assert.deepEqual(ids("score z mvrv"), ["mvrv-z-score"]);
  assert.deepEqual(ids("z-score"), ["mvrv-z-score"]);
  assert.deepEqual(ids("zscore"), ["mvrv-z-score"]);
  assert.deepEqual(ids("supply short"), ["sth-mvrv"]);
  assert.deepEqual(ids("mvrv").slice(0, 3).sort(), ["lth-mvrv", "mvrv-z-score", "sth-mvrv"]);
  assert.equal(ids("mvrv").at(-1), "pb-various", "description-only matches rank after title matches");
  assert.deepEqual(ids("mvrv 200"), [], "AND matching: every word must match");
});

test("search aliases cover cohort abbreviations, spelling, and expanded names", () => {
  const scope = context();
  const ids = (query) => Array.from(scope.searchCharts(library, query), (chart) => chart.id);
  assert.deepEqual(ids("sth mvrv"), ["sth-mvrv"]);
  assert.deepEqual(ids("LTH"), ["lth-mvrv"]);
  assert.deepEqual(ids("realised").sort(), ["pb-various", "realized-price"]);
  assert.deepEqual(ids("net unrealized"), ["nupl"]);
  assert.deepEqual(ids("onchain nupl"), ["nupl"], "section ids are searchable");
});

test("shared boilerplate descriptions never match, while real descriptions still do", () => {
  const scope = context();
  const ids = (query) => Array.from(scope.searchCharts(library, query), (chart) => chart.id);
  assert.deepEqual(ids("refreshed"), []);
  assert.deepEqual(ids("historical series"), []);
  assert.deepEqual(ids("200 day"), ["mayer"]);
  assert.deepEqual(ids(""), library.map((chart) => chart.id).sort((a, b) => library.find((c) => c.id === a).title.localeCompare(library.find((c) => c.id === b).title)));
});

test("section chips count search results per manifest section and mark the active filter", () => {
  const scope = context();
  vm.runInContext(`appState.manifest = { sections: [{ id: "onchain", name: "On-Chain" }, { id: "technical", name: "Technical" }], charts: [] };`, scope);
  scope.manifestCharts = library;
  vm.runInContext(`appState.manifest.charts = manifestCharts; appState.sectionFilter = "onchain";`, scope);
  scope.renderSectionFilters(scope.searchCharts(library, "mvrv"));
  const markup = scope.node("#section-filters").innerHTML;
  assert.match(markup, /data-section="" aria-pressed="false">All <span[^>]*>4</);
  assert.match(markup, /data-section="onchain" aria-pressed="true">On-Chain <span[^>]*>3</);
  assert.match(markup, /data-section="technical" aria-pressed="false" disabled>Technical <span[^>]*>0</);
  assert.match(markup, /data-section="cycle-models" aria-pressed="false">Cycle Models <span[^>]*>1</, "sections missing from the list are derived from charts");
});

test("percent and ratio series change by points while positive levels change relatively", () => {
  const scope = context();
  const x = ["2026-10-02", "2026-11-01"];
  const drawdown = { name: "Drawdown", hovertemplate: "%{x}<br>%{y:.1f}%<extra></extra>", x, y: [-33, -41] };
  const sharpe = { name: "1Y Sharpe proxy", hovertemplate: "%{x}<br>%{y:.2f}<extra></extra>", x, y: [0.64, -0.83] };
  const price = { name: "BTC price", hovertemplate: "$%{y:,.0f}", x, y: [100, 125] };
  const signedMetric = { name: "Net flow", x, y: [-5, 10] };
  const change = (series) => scope.seriesWindowChange(series, 30);
  assert.equal(scope.formatSeriesChange(change(drawdown)), "-8.0pp");
  assert.equal(scope.formatSeriesChange(change(sharpe)), "-1.47");
  assert.equal(scope.formatSeriesChange(change(price)), "+25.0%");
  assert.equal(change(signedMetric).mode, "absolute", "a series crossing zero cannot use percentage change");
  assert.equal(scope.formatSeriesChange(change(signedMetric)), "+15");
  assert.equal(scope.formatSeriesChange(scope.seriesWindowChange({ ...price, x: [x[1]], y: [1] }, 30)), "—");
});

test("performance and latest values anchor to the observed end, not projections", () => {
  const scope = context();
  const observedEnd = Date.UTC(2026, 9, 1);
  const projection = { name: "Support projection", hovertemplate: "$%{y:,.0f}", x: ["2025-10-01", "2026-10-01", "2039-12-27"], y: [50, 100, 1_000_000] };
  assert.equal(scope.seriesLatestValue(projection, observedEnd), 100);
  assert.equal(scope.seriesLatestValue(projection, null), 1_000_000);
  assert.equal(scope.formatSeriesChange(scope.seriesWindowChange(projection, 365, { anchor: observedEnd })), "+100.0%");
});

test("sidebar, readout, and sheet values use the hover template's units", () => {
  const scope = context();
  assert.equal(scope.seriesDisplayValue({ name: "200D MA", hovertemplate: "%{x}<br>$%{y:,.0f}<extra>200D MA</extra>" }, 73136), "$73,136");
  assert.equal(scope.seriesDisplayValue({ name: "CAGR", hovertemplate: "%{x}<br>%{y:.1f}%<extra></extra>" }, 193), "193%");
  assert.equal(scope.seriesDisplayValue({ name: "Gap", hovertemplate: "%{y:.1f} pp" }, 4.2), "4.2 pp");
  assert.equal(scope.seriesDisplayValue({ name: "BTC OHLC", type: "candlestick" }, 70000), "$70,000");
});

test("detail panel shows template units and observed-end values", () => {
  const scope = context();
  const x = [...dates(400), "2039-12-27"];
  const payload = {
    id: "trend", x_value_type: "date",
    series: [
      { name: "200D MA", hovertemplate: "%{x}<br>$%{y:,.0f}<extra></extra>", source_key: "ma", x, y: [...x.slice(0, -1).map((_, i) => 70000 + i), 9e9] },
      { name: "BTC price", source_key: "price", hovertemplate: "$%{y:,.0f}", x: x.slice(0, -1), y: x.slice(0, -1).map((_, i) => 60000 + i) },
    ],
  };
  vm.runInContext("appState.currentChart = { id: 'trend', description: '' }; renderChartInsights = () => {}; updateChartPhase = () => {};", scope);
  scope.payload = payload;
  vm.runInContext("appState.currentPayload = payload; renderChartDetails(payload)", scope);
  const markup = scope.node("#series-list").innerHTML;
  assert.match(markup, /\$70,399/);
  assert.doesNotMatch(markup, /9B|9,000,000,000/);
  assert.equal(scope.node("#series-date").textContent, "Feb 4, 26");
});

test("malicious upstream colours fall back to the palette and cannot inject attributes", () => {
  const scope = context();
  const evil = 'red" onmouseover="alert(1)';
  assert.equal(scope.safeCssColor(evil, "#123456"), "#123456");
  assert.equal(scope.safeCssColor("url(javascript:alert(1))", "#123456"), "#123456");
  assert.equal(scope.safeCssColor("rgba(0, 0, 0, 0.5)", "#123456"), "rgba(0, 0, 0, 0.5)");
  assert.equal(scope.safeCssColor("#ABCDEF", "#123456"), "#ABCDEF");
  scope.payload = { id: "x", x_value_type: "category", series: [{ name: "Evil", x: ["a"], y: [1], line: { color: evil } }, { name: "Marker", x: ["a"], y: [2], marker: { color: "blue;background:url(x)" } }] };
  vm.runInContext("appState.currentChart = { id: 'x', description: '' }; updateChartPhase = () => {}; appState.currentPayload = payload; renderChartDetails(payload)", scope);
  const markup = scope.node("#series-list").innerHTML;
  assert.doesNotMatch(markup, /onmouseover|url\(/);
  assert.match(markup, /style="background:#c85f3c"/);
  assert.match(markup, /style="background:#2863a7"/);
  assert.equal(scope.seriesColor({ line: { color: "#F5C84B" } }, 0), "#c85f3c", "legacy palette mapping still applies case-insensitively");
});

test("sheet model follows the visible window and CSV exports raw values safely", () => {
  const scope = context();
  const payload = {
    x_value_type: "date",
    series: [
      { name: "Price, USD", x: ["2026-01-01", "2026-01-02", "2026-01-03"], y: [1, 2.5, null] },
      { name: "=cmd|' /C calc'!A0", x: ["2026-01-02", "2026-01-03"], y: [-4, 5] },
    ],
  };
  const model = scope.dataSheetModel(payload, ["2026-01-02T00:00:00Z", "2026-01-03T23:59:59Z"]);
  assert.equal(model.rows.length, 2);
  assert.equal(model.filtered, true);
  const csv = scope.dataSheetCsv(model);
  assert.equal(csv, "Date,\"Price, USD\",'=cmd|' /C calc'!A0\r\n2026-01-02,2.5,-4\r\n2026-01-03,,5\r\n");
  assert.equal(scope.dataSheetModel(payload, null).rows.length, 3);
});

test("visible sheet range follows shortcuts and custom zooms", () => {
  const scope = context();
  scope.payload = { x_value_type: "date", series: [{ name: "Price", source_key: "price", x: ["2024-01-01", "2026-01-01"], y: [1, 2] }] };
  vm.runInContext("appState.chartOptions.range = '1y'", scope);
  assert.deepEqual(Array.from(vm.runInContext("terminalVisibleRange(payload)", scope)), ["2025-01-01T00:00:00.000Z", "2026-01-01T00:00:00.000Z"]);
  vm.runInContext("appState.chartOptions.customRange = ['2024-03-01', '2024-04-01']", scope);
  assert.deepEqual(Array.from(vm.runInContext("terminalVisibleRange(payload)", scope)), ["2024-03-01T00:00:00.000Z", "2024-04-01T23:59:59.999Z"]);
  vm.runInContext("appState.chartOptions.customRange = null; appState.chartOptions.range = 'all'", scope);
  assert.equal(vm.runInContext("terminalVisibleRange(payload)", scope), null);
});

test("toolbar toggles expose aria-pressed and Grid is pressed while the grid is shown", async () => {
  const scope = context();
  vm.runInContext("appState.currentChart = { id: 'a', title: 'A' }; appState.currentPayload = { id: 'a', series: [] }; renderTerminalPlot = async () => {};", scope);
  const button = () => {
    const attributes = {};
    const classes = new Set();
    return { attributes, classes, classList: { toggle(name, on) { if (on) classes.add(name); else classes.delete(name); } }, setAttribute(name, value) { attributes[name] = value; } };
  };
  const grid = button();
  await scope.handleChartAction("grid", grid);
  assert.equal(grid.attributes["aria-pressed"], "false");
  assert.equal(grid.classes.has("active"), false, "an off grid is not highlighted");
  await scope.handleChartAction("grid", grid);
  assert.equal(grid.attributes["aria-pressed"], "true");
  assert.equal(grid.classes.has("active"), true);
  for (const action of ["moving-average", "halvings"]) {
    const toggle = button();
    await scope.handleChartAction(action, toggle);
    assert.equal(toggle.attributes["aria-pressed"], "true", action);
  }
});

test("the single status line announces search counts and chart range", () => {
  const scope = context();
  scope.node("#sidebar-search").value = "mvrv";
  scope.node("#all-count").textContent = "12";
  vm.runInContext("appState.manifest = { charts: [] }", scope);
  assert.equal(scope.librarySearchStatus(), "12 charts match “mvrv”");
  scope.node("#all-count").textContent = "0";
  assert.equal(scope.librarySearchStatus(), "No charts match “mvrv”");
  vm.runInContext("appState.currentChart = { title: 'NUPL' }; appState.chartOptions.range = '1y'; announceChartStatus()", scope);
  assert.equal(scope.node("#terminal-status").textContent, "Showing NUPL, 1Y range");
  vm.runInContext("appState.chartOptions.customRange = ['2024-01-05', '2024-03-01']; announceChartStatus()", scope);
  assert.equal(scope.node("#terminal-status").textContent, "Showing NUPL, Jan 5, 2024 to Mar 1, 2024");
});

test("readout reads nearby observations with units and ignores series that ended long before", () => {
  const scope = context();
  const payload = {
    x_value_type: "date",
    series: [
      { name: "BTC price", source_key: "price", hovertemplate: "$%{y:,.0f}", x: ["2026-01-01", "2026-01-02", "2026-01-03"], y: [100, 200, 300] },
      { name: "Old metric", hovertemplate: "%{y:.1f}%", x: ["2020-01-01", "2020-01-02"], y: [5, 6] },
    ],
  };
  const readout = scope.chartReadout(payload, "2026-01-02");
  assert.equal(readout.label, "Jan 2, 2026");
  assert.deepEqual(JSON.parse(JSON.stringify(readout.items.map((item) => [item.name, item.value]))), [["BTC price", "$200"], ["Old metric", "—"]]);
});
