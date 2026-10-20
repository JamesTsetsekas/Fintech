const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8");

function renderSheet(payload) {
  const sheet = { innerHTML: "" };
  const context = {
    window: { location: { search: "" } },
    document: {
      body: { dataset: {} },
      addEventListener() {},
      querySelector() { return sheet; },
    },
    URLSearchParams,
    Intl,
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  context.renderDataSheet(payload);
  return sheet.innerHTML;
}

function rows(markup) {
  const body = markup.match(/<tbody>([\s\S]*?)<\/tbody>/)?.[1] || "";
  return [...body.matchAll(/<tr>(.*?)<\/tr>/g)].map((row) => (
    [...row[1].matchAll(/<td>(.*?)<\/td>/g)].map((cell) => cell[1])
  ));
}

test("sheet joins differing date histories by date and includes each series' dates", () => {
  const markup = renderSheet({
    x_value_type: "date",
    series: [
      { name: "Price", x: ["2026-10-18", "2026-10-19"], y: [80, 90] },
      { name: "200WMA price", x: ["2026-10-17", "2026-10-19", "2026-10-20"], y: [40, 50, 60] },
    ],
  });
  assert.deepEqual(rows(markup), [
    ["Oct 20, 26", "—", "$60.00"],
    ["Oct 19, 26", "$90.00", "$50.00"],
    ["Oct 18, 26", "$80.00", "—"],
    ["Oct 17, 26", "—", "$40.00"],
  ]);
});

test("sheet keeps null and missing values distinct from a genuine zero", () => {
  const markup = renderSheet({
    x_value_type: "number",
    series: [
      { name: "Metric", x: [1, 2, 3], y: [0, null, 8] },
      { name: "Other", x: [1, 3], y: [null, 4] },
    ],
  });
  assert.deepEqual(rows(markup), [["3", "8", "4"], ["2", "—", "—"], ["1", "0", "—"]]);
});

test("sheet joins numeric categories without interpreting them as dates", () => {
  const markup = renderSheet({
    x_value_type: "category",
    series: [
      { name: "First", x: [2024, 2025], y: [1, 2] },
      { name: "Second", x: [2025, 2026], y: [3, 4] },
    ],
  });
  assert.deepEqual(rows(markup), [["2026", "—", "4"], ["2025", "2", "3"], ["2024", "1", "—"]]);
});

test("horizontal sheets match category labels instead of array positions", () => {
  const markup = renderSheet({
    x_value_type: "number",
    series: [
      { name: "First", orientation: "h", x: [1, 2], y: ["A", "B"] },
      { name: "Second", orientation: "h", x: [3, null], y: ["B", "C"] },
    ],
  });
  assert.deepEqual(rows(markup), [["C", "—", "—"], ["B", "2", "3"], ["A", "1", "—"]]);
});

test("candlestick sheets expose open, high, low, and close on their real dates", () => {
  const markup = renderSheet({
    x_value_type: "date",
    series: [{
      type: "candlestick", name: "BTC OHLC", x: ["2026-10-19"],
      open: [80], high: [100], low: [null], close: [90],
    }],
  });
  for (const label of ["Open", "High", "Low", "Close"]) assert.match(markup, new RegExp(label));
  assert.deepEqual(rows(markup), [["Oct 19, 26", "$80.00", "$100", "—", "$90.00"]]);
});

test("sheet limits the sorted union to the latest 250 coordinates", () => {
  const coordinates = Array.from({ length: 300 }, (_, index) => index + 1);
  const markup = renderSheet({
    x_value_type: "number",
    series: [
      { name: "Earlier", x: coordinates.slice(0, 150), y: coordinates.slice(0, 150) },
      { name: "Later", x: coordinates.slice(150), y: coordinates.slice(150) },
    ],
  });
  const actual = rows(markup);
  assert.equal(actual.length, 250);
  assert.deepEqual(actual[0], ["300", "—", "300"]);
  assert.deepEqual(actual.at(-1), ["51", "51", "—"]);
});
