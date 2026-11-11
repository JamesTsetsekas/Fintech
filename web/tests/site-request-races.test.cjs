const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function fixture() {
  const classes = new Set();
  const target = {
    innerHTML: "", removeAttribute() {},
    classList: { add: value => classes.add(value), remove: value => classes.delete(value) },
  };
  const requests = [];
  const renders = [];
  const details = [];
  const context = vm.createContext({
    URLSearchParams,
    window: { location: { search: "" } },
    document: {
      body: { dataset: {} }, addEventListener() {}, querySelectorAll: () => [],
      querySelector: selector => selector === "#terminal-plot" ? target : null,
    },
    fetch: () => {
      const request = deferred();
      requests.push(request);
      return request.promise;
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);
  vm.runInContext(`
    appState.manifest = { charts: ["a", "b"].map(id => ({ id, data_path: id + ".json" })) };
    renderSidebar = updateChartHeadings = updateChartControls = renderDataSheet = updateScaleButton = () => {};
  `, context);
  context.renderTerminalPlot = async () => {
    const payload = vm.runInContext("appState.currentPayload", context);
    renders.push(payload);
    target.innerHTML = payload.id;
  };
  context.renderChartDetails = payload => details.push(payload);
  return {
    context, target, classes, requests, renders, details,
    select: (id, options = {}) => context.selectTerminalChart(id, { updateUrl: false, ...options }),
    state: () => vm.runInContext("appState", context),
    succeed(index, id) { requests[index].resolve({ ok: true, json: async () => ({ id, series: [] }) }); },
  };
}

test("late previous fetch failures cannot replace the current chart or loading state", async () => {
  for (const currentLoaded of [false, true]) {
    const f = fixture();
    const a = f.select("a");
    const b = f.select("b");
    if (currentLoaded) { f.succeed(1, "b"); await b; }
    f.requests[0].reject(new Error("old failure"));
    await a;
    assert.equal(f.target.innerHTML, currentLoaded ? "b" : "");
    assert.equal(f.classes.has("loading-block"), !currentLoaded);
    if (!currentLoaded) { f.succeed(1, "b"); await b; }
  }
});

test("A-B-A shared payload completion only renders the latest selection", async () => {
  const f = fixture();
  const a1 = f.select("a", { signalView: true });
  const b = f.select("b");
  const a2 = f.select("a");
  assert.equal(f.requests.length, 2);
  f.succeed(0, "a");
  await Promise.all([a1, a2]);
  assert.equal(f.renders.length, 1);
  assert.equal(f.details.length, 1);
  f.requests[1].reject(new Error("late B"));
  await b;
  assert.equal(f.target.innerHTML, "a");
});

test("superseded render completion and failure cannot update the latest selection", async () => {
  for (const fail of [false, true]) {
    const f = fixture();
    const rendering = deferred();
    f.context.renderTerminalPlot = () => rendering.promise;
    const a1 = f.select("a");
    f.succeed(0, "a");
    // Drain the fetch/json/getPayload microtasks without timers.
    await f.context.getPayload("a");
    await Promise.resolve();
    const b = f.select("b");
    f.context.renderTerminalPlot = async () => { f.target.innerHTML = "latest A"; };
    const a2 = f.select("a");
    await a2;
    if (fail) rendering.reject(new Error("old render"));
    else rendering.resolve();
    await a1;
    assert.equal(f.target.innerHTML, "latest A");
    assert.equal(f.details.length, 1);
    f.requests[1].reject(new Error("old B"));
    await b;
    assert.equal(f.target.innerHTML, "latest A");
  }
});

test("rejected payloads are evicted, concurrent callers dedupe, and success stays cached", async () => {
  const f = fixture();
  const first = f.context.getPayload("a");
  const concurrent = f.context.getPayload("a");
  const failures = Promise.all([assert.rejects(first, /offline/), assert.rejects(concurrent, /offline/)]);
  assert.equal(f.requests.length, 1);
  f.requests[0].reject(new Error("offline"));
  await failures;
  assert.equal(f.state().payloadCache.has("a"), false);
  const retry = f.context.getPayload("a");
  const retryConcurrent = f.context.getPayload("a");
  assert.equal(f.requests.length, 2);
  f.succeed(1, "a");
  const payload = await retry;
  assert.equal(await retryConcurrent, payload);
  assert.equal(await f.context.getPayload("a"), payload);
  assert.equal(f.requests.length, 2);
});

test("a rejected cache entry cannot evict a replacement entry", async () => {
  const f = fixture();
  const pending = f.context.getPayload("a");
  const failure = assert.rejects(pending, /offline/);
  const replacement = Promise.resolve({ id: "replacement" });
  f.state().payloadCache.set("a", replacement);
  f.requests[0].reject(new Error("offline"));
  await failure;
  assert.equal(f.state().payloadCache.get("a"), replacement);
});
