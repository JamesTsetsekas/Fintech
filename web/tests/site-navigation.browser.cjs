const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");

const dates = Array.from({ length: 80 }, (_, i) => new Date(Date.UTC(2024, 0, i + 1)).toISOString().slice(0, 10));
const payload = {
  title: "Navigation interruption regression", x_value_type: "date",
  series: [{ type: "scatter", mode: "lines", name: "BTC price", source_key: "price", x: dates, y: dates.map((_, i) => 1000 + i * 100) }],
  layout: { xaxis: { type: "date" }, yaxis: { type: "log", range: [0, 5], tickprefix: "$" } },
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 700 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.setContent('<div id="plot" style="position:relative;width:950px;height:500px"></div>');
    await page.addStyleTag({ path: path.resolve(__dirname, "../assets/site.css") });
    await page.addScriptTag({ url: "https://cdn.plot.ly/plotly-2.35.2.min.js" });
    await page.addScriptTag({ path: path.resolve(__dirname, "../assets/site.js") });
    const render = () => page.evaluate(payload => renderPlot(document.querySelector("#plot"), payload), payload);
    const ranges = () => page.locator("#plot").evaluate(p => ({ x: p._fullLayout.xaxis.range.slice(), y: p._fullLayout.yaxis.range.slice() }));
    await render();
    const initial = await ranges();

    await page.evaluate(() => {
      const nav = document.querySelector("#plot")._fintechNavigation;
      window.navigationResults = [];
      const save = promise => promise.then(() => window.navigationResults.push("ok"), error => window.navigationResults.push(String(error)));
      save(nav.zoomTo(["2024-01-10", "2024-01-30"]));
      setTimeout(() => save(nav.zoomTo(["2024-02-01", "2024-02-20"])), 40);
      setTimeout(() => save(nav.reset()), 80);
    });
    await page.waitForTimeout(650);
    assert.deepEqual(await ranges(), initial, "latest reset wins over both interrupted animations");
    const interruptedResults = await page.evaluate(() => window.navigationResults);

    await page.emulateMedia({ reducedMotion: "reduce" });
    const elapsed = await page.evaluate(async () => {
      const started = performance.now();
      await document.querySelector("#plot")._fintechNavigation.zoomTo(["2024-02-01", "2024-02-20"]);
      return performance.now() - started;
    });
    assert(elapsed < 250, `reduced motion finishes without a 350ms transition (${elapsed}ms)`);
    const reduced = await ranges();
    assert.deepEqual(reduced.x.map(value => new Date(value).toISOString().slice(0, 10)), ["2024-02-01", "2024-02-20"]);
    const reducedTicks = await page.locator("#plot").evaluate(p => p._fullLayout.yaxis.tickvals);
    assert(reducedTicks.length >= 3 && reducedTicks.every(value => value > 1000 && value < 10000), "reduced-motion zoom refreshes financial ticks for the visible window");

    const box = await page.locator("#plot").boundingBox();
    const size = await page.locator("#plot").evaluate(p => p._fullLayout._size);
    const centerY = box.y + size.t + size.h / 2;
    await page.keyboard.down("Shift");
    await page.mouse.move(box.x + size.l + size.w * 0.6, centerY);
    await page.mouse.down();
    await page.mouse.move(box.x + size.l + size.w * 0.4, centerY, { steps: 5 });
    await page.mouse.up();
    await page.keyboard.up("Shift");
    await page.waitForTimeout(100);
    const panned = await ranges();
    assert.notDeepEqual(panned.x, reduced.x, "Shift drag retains native panning");
    assert(Math.abs((new Date(panned.x[1]) - new Date(panned.x[0])) - (new Date(reduced.x[1]) - new Date(reduced.x[0]))) < 10,
      "native pan preserves the selected time span");
    assert.equal(await page.locator(".chart-zoom-selection:not([hidden])").count(), 0);

    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.evaluate(() => {
      window.interruptedRender = document.querySelector("#plot")._fintechNavigation.zoomTo(["2024-01-10", "2024-01-30"]);
    });
    await page.waitForTimeout(40);
    await render();
    await page.waitForTimeout(450);
    assert.deepEqual(await ranges(), initial, "a replaced plot is not changed by its former navigation animation");
    assert.equal(await page.locator(".chart-reset-zoom").count(), 1);
    assert.equal(await page.locator(".chart-zoom-selection").count(), 1);

    await page.evaluate(async () => {
      await renderPlot(document.querySelector("#plot"), {
        title: "DCA reversed duration", x_value_type: "number",
        series: [{type: "scatter", mode: "lines", x: [0, 5, 10, 17], y: [80000, 50000, 20000, 5000]}],
        layout: {xaxis: {type: "linear", autorange: "reversed"}, yaxis: {type: "log", tickprefix: "$"}},
      });
      await document.querySelector("#plot")._fintechNavigation.zoomBy(0.5);
    });
    const reversed = await ranges();
    assert(reversed.x[0] > reversed.x[1], "modebar zoom preserves the DCA duration axis direction");

    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.evaluate(async payload => {
      await renderPlot(document.querySelector("#plot"), {
        ...payload,
        series: [...payload.series, {type: "scatter", mode: "lines", name: "NUPL", axis: "y2", x: payload.series[0].x, y: payload.series[0].x.map((_, index) => .3 + index / 1000)}],
        layout: {...payload.layout, yaxis2: {type: "linear", overlaying: "y", side: "right", range: [-2, 1], tickvals: [-2, -1, 0, 1]}},
      });
      await document.querySelector("#plot")._fintechNavigation.zoomTo(["2024-02-01", "2024-02-20"]);
    }, payload);
    assert.deepEqual(await page.locator("#plot").evaluate(p => p._fullLayout.yaxis2.range), [-2, 1], "NUPL retains its semantic metric bounds while price refits");
    assert.equal(await page.locator("#plot .y2tick text").count(), 4, "semantic metric ticks stay visible after zoom");
    assert.deepEqual(errors, []);
    assert.deepEqual(interruptedResults, ["ok", "ok", "ok"], "superseded navigation promises settle");
    console.log("PASS: interrupted zoom/reset, reduced-motion price ticks, semantic metric bounds, native pan, cleanup, and reversed DCA axes.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
