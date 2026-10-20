const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8");

function element() {
  const classes = new Set();
  return {
    className: "", style: {}, dataset: {}, textContent: "", listeners: {},
    classList: { add(value) { classes.add(value); }, remove(value) { classes.delete(value); }, contains(value) { return classes.has(value); } },
    setAttribute() {}, remove() {},
    addEventListener(name, listener) { this.listeners[name] = listener; },
    removeEventListener(name) { delete this.listeners[name]; },
  };
}

function fixture() {
  const target = element();
  const children = [];
  target._fullLayout = {
    _size: { l: 60, r: 44, t: 30, w: 700, h: 400 },
    xaxis: { type: "date", _offset: 60, _length: 700, p2d: () => "2026-10-19" },
    yaxis: { type: "linear", side: "left", _offset: 30, _length: 240, range: [0, 1000], p2d: (pixel) => 1000 - pixel },
    yaxis2: { type: "linear", side: "right", overlaying: "y", _offset: 30, _length: 240, range: [0, 100], p2d: () => 50, ticksuffix: "%" },
    yaxis3: { type: "linear", side: "left", _offset: 330, _length: 100, range: [-50, 50], p2d: (pixel) => 50 - pixel, ticksuffix: " pp" },
  };
  target.getBoundingClientRect = () => ({ left: 10, top: 20 });
  target.append = (...items) => children.push(...items);
  target.appendChild = (item) => children.push(item);
  target.querySelectorAll = () => children.filter((child) => child.className.includes("chart-scale-rail"));
  const context = {
    window: { location: { search: "" } },
    document: { body: { dataset: {} }, addEventListener() {}, createElement: element },
    URLSearchParams, Intl,
    ResizeObserver: class { observe() {} disconnect() {} },
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { context, target, children };
}

test("axis hit testing chooses the local non-overlay pane and excludes the gutter", () => {
  const { context, target } = fixture();
  assert.equal(typeof context.yAxisAtPixel, "function");
  assert.equal(context.yAxisAtPixel(target._fullLayout, 80).name, "yaxis");
  assert.equal(context.yAxisAtPixel(target._fullLayout, 380).name, "yaxis3");
  assert.equal(context.yAxisAtPixel(target._fullLayout, 300), null);
  assert.equal(context.yAxisAtPixel(target._fullLayout, 20), null);
  target._fullLayout.yaxis3.type = "category";
  assert.equal(context.yAxisAtPixel(target._fullLayout, 380), null);
});

test("lower-pane badge converts pixels relative to y3 and retains its pp unit", () => {
  const { context, target, children } = fixture();
  context.installAxisBadges(target);
  const yBadge = children.find((child) => child.className.includes("chart-axis-badge-y"));
  target.listeners.pointermove({ clientX: 470, clientY: 400 });
  assert.equal(yBadge.textContent, "0 pp");
  assert(yBadge.classList.contains("visible"));
  target.listeners.pointermove({ clientX: 470, clientY: 100 });
  assert.equal(yBadge.textContent, "950");
  target.listeners.pointermove({ clientX: 470, clientY: 320 });
  assert(children.every((child) => !child.classList.contains("visible")), "pane gutter hides both badges");
});

test("each price-scale rail uses its own axis position and pane height", () => {
  const { context, target, children } = fixture();
  context.installPriceScaleControls(target);
  const rails = children.filter((child) => child.className.includes("chart-scale-rail"));
  assert.deepEqual(rails.map((rail) => rail.dataset.axis), ["yaxis", "yaxis2", "yaxis3"]);
  const upper = rails.find((rail) => rail.dataset.axis === "yaxis");
  const lower = rails.find((rail) => rail.dataset.axis === "yaxis3");
  assert.equal(upper.style.top, "30px");
  assert.equal(upper.style.height, "240px");
  assert.equal(lower.style.top, "330px");
  assert.equal(lower.style.height, "100px");
  assert.equal(lower.style.left, "0");
});
