const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function fixture() {
  const children = [];
  const listeners = new Map();
  const element = () => {
    const classes = new Set();
    return {
      style: {}, dataset: {}, textContent: "", className: "", removed: false,
      classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) },
      setAttribute() {}, remove() { this.removed = true; },
    };
  };
  const target = {
    ...element(),
    _fullLayout: {
      _size: { l: 60, r: 40, t: 30, w: 700, h: 400 },
      xaxis: { _offset: 60, _length: 700 },
      yaxis: { type: "log", _offset: 30, _length: 240, side: "left", tickprefix: "$", d2p: y => 240 - Math.log10(y) * 40 },
      yaxis2: { type: "linear", _offset: 30, _length: 240, side: "right", ticksuffix: "%", d2p: y => 240 - y * 2 },
      yaxis3: { type: "linear", _offset: 330, _length: 100, side: "left", ticksuffix: " pp", d2p: y => 50 - y },
    },
    appendChild: child => children.push(child),
    on: (name, listener) => listeners.set(name, listener),
    removeListener: name => listeners.delete(name),
    addEventListener: (name, listener) => listeners.set(name, listener),
    removeEventListener: name => listeners.delete(name),
  };
  const context = {
    window: { location: { search: "" } },
    document: { body: { dataset: {} }, documentElement: { dataset: { theme: "light" } }, addEventListener() {}, createElement: element },
    URLSearchParams, Intl,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);
  return { context, target, children, listeners };
}

test("hovered series badges track observations on local log, right, and lower axes", () => {
  const { context, target, children, listeners } = fixture();
  let priorCleaned = false;
  target._fintechChartCleanup = () => { priorCleaned = true; };
  context.installSeriesValueBadges(target);
  listeners.get("plotly_hover")({ points: [
    { y: 10000, pointNumber: 1, data: { type: "scatter", name: "Price", marker: { color: ["#0106f5", "#f9ff54"] } } },
    { y: 35, data: { type: "scatter", yaxis: "y2", line: { color: "#c96442" } } },
    { y: -20, data: { type: "scatter", yaxis: "y3", line: { color: "#0165f8" } } },
  ] });
  assert.deepEqual(children.map(child => child.textContent), ["$10K", "35%", "-20 pp"]);
  assert.deepEqual(children.map(child => child.style.top), ["110px", "200px", "400px"]);
  assert.deepEqual(children.map(child => child.style.left), ["60px", "760px", "60px"]);
  assert.equal(children[0].style.backgroundColor, "#f9ff54");
  assert.equal(children[0].style.color, "#1f211f", "bright palette values retain readable dark text");
  assert.equal(children[2].style.color, "#ffffff", "dark palette values retain readable light text");
  listeners.get("plotly_unhover")();
  assert(children.every(child => !child.classList.contains("visible")));
  target._fintechChartCleanup();
  assert(priorCleaned);
  assert(children.every(child => child.removed));
  assert.equal(listeners.size, 0);
});

test("hidden, categorical, heatmap and out-of-pane observations produce no badge", () => {
  const { context, target, children, listeners } = fixture();
  target._fullLayout.yaxis3.type = "category";
  context.installSeriesValueBadges(target);
  listeners.get("plotly_hover")({ points: [
    { y: 100, data: { type: "scatter", visible: "legendonly" } },
    { y: 2, data: { type: "heatmap", yaxis: "y2" } },
    { y: 30, data: { type: "scatter", yaxis: "y3" } },
    { y: 100000000, data: { type: "scatter" } },
  ] });
  assert.equal(children.length, 0);
});

test("colorscale values interpolate and currency cursor values include their axis prefix", () => {
  const { context } = fixture();
  assert.equal(context.seriesValueBadgeColor({ pointNumber: 1, data: { marker: { color: [0, 5, 10], cmin: 0, cmax: 10, colorscale: [[0, "#000000"], [1, "#ffffff"]] } } }), "#808080");
  assert.equal(context.formatCrosshairValue(12345, { tickprefix: "$" }), "$12.35K");
});
