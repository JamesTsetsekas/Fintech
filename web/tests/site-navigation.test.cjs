const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function element() {
  const classes = new Set();
  const listeners = new Map();
  return {
    style: {}, className: "", hidden: false, removed: false,
    classList: { add(value) { classes.add(value); }, remove(value) { classes.delete(value); }, contains(value) { return classes.has(value); } },
    setAttribute() {}, remove() { this.removed = true; },
    addEventListener(name, callback) { listeners.set(name, callback); },
    removeEventListener(name) { listeners.delete(name); },
    fire(name, event) { listeners.get(name)?.(event); },
    listeners,
  };
}

function fixture({ reducedMotion = true, numeric = false, reversed = false, dragmode = "zoom" } = {}) {
  const target = element();
  const children = [];
  const calls = [];
  const pending = [];
  const events = new Map();
  const capture = new Set();
  const initial = numeric ? [0, 1] : ["2026-01-01T00:00:00.000Z", "2026-01-11T00:00:00.000Z"];
  if (reversed) initial.reverse();
  target._fullLayout = {
    _size: { l: 50, t: 20, w: 1000, h: 400 }, dragmode,
    xaxis: { type: numeric ? "linear" : "date", _offset: 50, _length: 1000, range: initial.slice() },
    yaxis: { type: "linear", range: [0, 1000] },
  };
  target._fullLayout.xaxis.p2r = (pixel) => {
    const range = target._fullLayout.xaxis.range.map(value => numeric ? value : new Date(value).getTime());
    const value = range[0] + (range[1] - range[0]) * pixel / 1000;
    return numeric ? value : new Date(value).toISOString();
  };
  target.data = [{ type: "scatter", mode: "lines", x: initial.slice(), y: [10, 110] }];
  target.append = (...items) => children.push(...items);
  target.getBoundingClientRect = () => ({ left: 0, top: 0 });
  target.focus = () => {};
  target.setPointerCapture = id => capture.add(id);
  target.hasPointerCapture = id => capture.has(id);
  target.releasePointerCapture = id => capture.delete(id);
  target.on = (name, fn) => events.set(name, fn);
  target.removeListener = name => events.delete(name);
  const apply = update => {
    for (const [key, value] of Object.entries(update)) {
      const [axis, attr] = key.split(".");
      if (attr) target._fullLayout[axis][attr] = value;
      else Object.assign(target._fullLayout[axis], value);
    }
  };
  const plotly = {
    relayout(_target, update) {
      calls.push({ type: "relayout", update });
      apply(update);
      events.get("plotly_relayout")?.(update);
      return Promise.resolve();
    },
    animate(_target, frame, options) {
      calls.push({ type: "animate", frame, options });
      if (Array.isArray(frame)) return Promise.resolve();
      if (options.transition?.duration === 0) {
        apply(frame.layout);
        return Promise.resolve();
      }
      return new Promise((resolve, reject) => pending.push({
        resolve() { apply(frame.layout); resolve(); }, reject,
      }));
    },
  };
  const context = {
    window: { location: { search: "" }, matchMedia: () => ({ matches: reducedMotion }) },
    document: { body: { dataset: {} }, addEventListener() {}, createElement: element },
    URLSearchParams, Intl, Plotly: plotly,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);
  context.installChartNavigation(target);
  const event = (x, extra = {}) => ({
    clientX: x + 50, clientY: 100, pointerId: 1, pointerType: "mouse", button: 0,
    target: { closest: selector => selector === ".nsewdrag" ? {} : null },
    prevented: false, stopped: false,
    preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; }, ...extra,
  });
  const ranges = () => JSON.parse(JSON.stringify(target._fullLayout.xaxis.range));
  return { context, target, children, calls, pending, events, capture, event, ranges, initial };
}

test("reduced motion refits immediately without an animation and reset restores both axes", async () => {
  const { target, calls, ranges, initial } = fixture();
  await target._fintechNavigation.zoomTo(["2026-01-04", "2026-01-08"]);
  assert(calls.every(call => call.type === "relayout"));
  assert.deepEqual(ranges(), ["2026-01-04T00:00:00.000Z", "2026-01-08T00:00:00.000Z"]);
  assert(target._fullLayout.yaxis.range[0] > 30 && target._fullLayout.yaxis.range[1] < 90);
  await target._fintechNavigation.reset();
  assert.deepEqual(ranges(), initial);
  assert.deepEqual(Array.from(target._fullLayout.yaxis.range), [0, 1000]);
});

test("right-to-left selections choose the same dates as left-to-right selections", async () => {
  for (const pixels of [[200, 800], [800, 200]]) {
    const { target, event, ranges, capture, children } = fixture();
    target.fire("pointerdown", event(pixels[0]));
    target.fire("pointermove", event(pixels[1]));
    assert.equal(children.find(child => child.className === "chart-zoom-selection").style.width, "600px");
    target.fire("pointerup", event(pixels[1]));
    await Promise.resolve();
    assert.deepEqual(ranges(), ["2026-01-03T00:00:00.000Z", "2026-01-09T00:00:00.000Z"]);
    assert.equal(capture.size, 0);
  }
});

test("date windows have a one-day minimum and clamp to the chart's source bounds", async () => {
  const { target, ranges } = fixture();
  await target._fintechNavigation.zoomTo(["2026-01-05T11:59:00Z", "2026-01-05T12:01:00Z"]);
  assert.equal(new Date(ranges()[1]) - new Date(ranges()[0]), 86400000);
  await target._fintechNavigation.zoomTo(["2025-12-01", "2025-12-03"]);
  assert.deepEqual(ranges(), ["2026-01-01T00:00:00.000Z", "2026-01-03T00:00:00.000Z"]);
  await target._fintechNavigation.zoomTo(["2026-02-01", "2026-02-03"]);
  assert.deepEqual(ranges(), ["2026-01-09T00:00:00.000Z", "2026-01-11T00:00:00.000Z"]);
});

test("numeric charts show a reset action for a material zoom smaller than one unit", async () => {
  const { target, children } = fixture({ numeric: true });
  await target._fintechNavigation.zoomTo([0.2, 0.8]);
  assert.equal(children.find(child => child.className === "chart-reset-zoom").hidden, false);
});

test("reversed numeric charts retain their descending direction through zoom and reset", async () => {
  const { target, event, ranges, initial } = fixture({ numeric: true, reversed: true });
  await target._fintechNavigation.zoomBy(0.5);
  assert.deepEqual(ranges(), [0.75, 0.25]);
  await target._fintechNavigation.reset();
  for (const pixels of [[200, 800], [800, 200]]) {
    target.fire("pointerdown", event(pixels[0]));
    target.fire("pointermove", event(pixels[1]));
    target.fire("pointerup", event(pixels[1]));
    await Promise.resolve();
    assert(ranges()[0] > ranges()[1], "drag zoom keeps descending X values");
    await target._fintechNavigation.reset();
    assert.deepEqual(ranges(), initial);
  }
});

test("modifier, touch, and pan-mode gestures are left for native Plotly handling", () => {
  for (const extra of [{ shiftKey: true }, { ctrlKey: true }, { metaKey: true }, { pointerType: "touch" }, { button: 1 }]) {
    const { target, event, capture } = fixture();
    const down = event(200, extra);
    target.fire("pointerdown", down);
    assert.equal(down.prevented, false);
    assert.equal(capture.size, 0);
  }
  const { target, event, capture } = fixture({ dragmode: "pan" });
  target.fire("pointerdown", event(200));
  assert.equal(capture.size, 0);
});

test("Escape releases a selection and cleanup removes all navigation listeners and UI", async () => {
  const { context, target, event, capture, children, events } = fixture();
  target.fire("pointerdown", event(200));
  target.fire("pointermove", event(800));
  target.fire("keydown", event(800, { target, key: "Escape" }));
  assert.equal(capture.size, 0);
  assert.equal(children.find(child => child.className === "chart-zoom-selection").hidden, true);
  await context.cleanupChartInteractions(target);
  assert.equal(target.listeners.size, 0);
  assert.equal(events.size, 0);
  assert.equal(target._fintechNavigation, null);
  assert(children.every(child => child.removed));
});

test("an interrupted animation settles even when Plotly leaves its native promise pending", async () => {
  const { target, pending, calls, ranges, initial } = fixture({ reducedMotion: false });
  const earlier = target._fintechNavigation.zoomTo(["2026-01-03", "2026-01-06"]);
  const later = target._fintechNavigation.zoomTo(["2026-01-05", "2026-01-09"]);
  pending[1].resolve();
  await Promise.all([earlier, later]);
  assert.deepEqual(ranges(), ["2026-01-05T00:00:00.000Z", "2026-01-09T00:00:00.000Z"]);
  assert(calls.every(call => call.options.mode === "immediate"));
  const reset = target._fintechNavigation.reset();
  pending[2].resolve();
  await reset;
  assert.deepEqual(ranges(), initial);
});

test("cleanup cancels in-flight animation and invalidates saved navigation handles", async () => {
  const { context, target, calls } = fixture({ reducedMotion: false });
  const saved = target._fintechNavigation;
  const earlier = saved.zoomTo(["2026-01-03", "2026-01-06"]);
  target._fullLayout.xaxis.range = ["2026-01-02", "2026-01-07"];
  target._fullLayout.yaxis.range = [20, 80];
  await context.cleanupChartInteractions(target);
  const stop = calls.find(call => call.type === "animate" && call.options.transition?.duration === 0);
  assert(stop, "cleanup freezes the current layout without another transition");
  assert.equal(stop.options.frame.duration, 0);
  assert.deepEqual(Array.from(stop.frame.layout.xaxis.range), ["2026-01-02", "2026-01-07"]);
  assert.deepEqual(Array.from(stop.frame.layout.yaxis.range), [20, 80]);
  await earlier;
  const count = calls.length;
  await saved.reset();
  await saved.zoomTo(["2026-01-03", "2026-01-06"]);
  await saved.zoomBy(0.5);
  assert.equal(calls.length, count);
});
