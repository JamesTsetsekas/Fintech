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

function ticks(axis, range) {
  assert.equal(typeof context.priceAxisTickOptions, "function");
  return JSON.parse(JSON.stringify(context.priceAxisTickOptions(axis, range)));
}

test("recent log-price ticks use proper dollar labels between decades", () => {
  const result = ticks({ type: "log", tickprefix: "$", range: [Math.log10(6000), Math.log10(150000)], _length: 400 });
  assert.equal(result.tickmode, "array");
  assert.deepEqual(result.tickvals, [10000, 20000, 50000, 100000]);
  assert.deepEqual(result.ticktext, ["$10K", "$20K", "$50K", "$100K"]);
});

test("broad historical log ranges show spaced powers with bounded tick density", () => {
  const result = ticks({ type: "log", tickprefix: "$", range: [-8, 6], _length: 300 });
  assert(result.tickvals.length >= 3 && result.tickvals.length <= 9);
  assert(result.tickvals.every(value => Math.abs(Math.log10(value) - Math.round(Math.log10(value))) < 1e-9));
  assert(result.ticktext.every(value => /\$/.test(value) && !/e[+-]/i.test(value)));
});

test("tight log windows use readable financial increments", () => {
  const result = ticks({ type: "log", tickprefix: "$", range: [Math.log10(98000), Math.log10(102000)], _length: 270 });
  assert.deepEqual(result.tickvals, [98000, 99000, 100000, 101000, 102000]);
  assert.deepEqual(result.ticktext, ["$98K", "$99K", "$100K", "$101K", "$102K"]);
});

test("linear ranges include actual zero and negative currency values", () => {
  const result = ticks({ type: "linear", tickprefix: "$", range: [-10, 10], _length: 225 });
  assert.deepEqual(result.tickvals, [-10, -5, 0, 5, 10]);
  assert.deepEqual(result.ticktext, ["-$10", "-$5", "$0", "$5", "$10"]);
});

test("cents and fractional cent prices retain sufficient precision", () => {
  const result = ticks({ type: "linear", tickprefix: "$", range: [0.01, 0.03], _length: 225 });
  assert.deepEqual(result.tickvals, [0.01, 0.015, 0.02, 0.025, 0.03]);
  assert.deepEqual(result.ticktext, ["$0.01", "$0.015", "$0.02", "$0.025", "$0.03"]);
});

test("sat-sized prices have exact labels without floating point noise", () => {
  const result = ticks({ type: "linear", tickprefix: "$", range: [1e-8, 5e-8], _length: 225 });
  assert.deepEqual(result.tickvals, [1e-8, 2e-8, 3e-8, 4e-8, 5e-8]);
  assert.deepEqual(result.ticktext, ["$0.00000001", "$0.00000002", "$0.00000003", "$0.00000004", "$0.00000005"]);
});

test("reversed ranges still produce ascending raw dollar tick values", () => {
  const axis = { type: "log", tickprefix: "$", range: [5, 3], _length: 150 };
  const result = ticks(axis);
  assert(result.tickvals.every((value, index) => index === 0 || value > result.tickvals[index - 1]));
  assert(result.tickvals.every(value => value >= 1000 && value <= 100000));
  assert.deepEqual(axis.range, [5, 3]);
});

test("short axes use fewer ticks than tall axes", () => {
  const axis = { type: "linear", tickprefix: "$", range: [0, 100] };
  const short = ticks({ ...axis, _length: 135 });
  const tall = ticks({ ...axis, _length: 600 });
  assert(short.tickvals.length >= 3);
  assert(tall.tickvals.length > short.tickvals.length && tall.tickvals.length <= 9);
});

test("explicit range arguments override the current range without mutation", () => {
  const axis = { type: "linear", tickprefix: "$", range: [0, 100], _length: 225 };
  assert.deepEqual(ticks(axis, [0, 10]).tickvals, [0, 2.5, 5, 7.5, 10]);
  assert.deepEqual(axis.range, [0, 100]);
});

test("single-value scales still label that finite price", () => {
  assert.deepEqual(ticks({ type: "linear", tickprefix: "$", range: [0, 0] }).ticktext, ["$0"]);
  assert.deepEqual(ticks({ type: "log", tickprefix: "$", range: [2, 2] }).ticktext, ["$100"]);
});

test("non-price, category, malformed, or nonfinite axes keep their own ticks", () => {
  for (const axis of [
    {}, { type: "linear", range: [0, 100] }, { type: "linear", tickprefix: "€", range: [0, 100] },
    { type: "category", tickprefix: "$", range: [0, 10] }, { type: "date", tickprefix: "$", range: [0, 10] },
    { type: "log", tickprefix: "$", range: [NaN, 3] }, { type: "linear", tickprefix: "$", range: [0, Infinity] },
    { type: "linear", tickprefix: "$", range: [null, null] }, { type: "linear", tickprefix: "$", range: [] },
  ]) assert.deepEqual(ticks(axis), {});
});
