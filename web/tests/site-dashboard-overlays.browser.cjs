const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");

const payload = {
  title: "Dashboard overlay positioning", x_value_type: "date",
  series: [{type: "scatter", mode: "lines", name: "BTC price", x: ["2024-01-01", "2025-01-01", "2026-01-01"], y: [10000, 50000, 100000]}],
  layout: {xaxis: {type: "date"}, yaxis: {type: "log", tickprefix: "$"}},
};

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    // Use the actual dashboard class without injecting a positioned fixture.
    // Leave room for a header/sidebar and a lower row to expose page-relative coordinates.
    await page.setContent('<header style="height:160px">Dashboard header</header><main style="margin-left:240px;width:900px"><div id="plot" class="dashboard-mini-plot"></div><div style="height:500px"></div><div id="lower" class="dashboard-mini-plot"></div></main>');
    await page.addStyleTag({path: path.resolve(__dirname, "../assets/site.css")});
    await page.addScriptTag({url: "https://cdn.plot.ly/plotly-2.35.2.min.js"});
    await page.addScriptTag({path: path.resolve(__dirname, "../assets/site.js")});
    for (const id of ["plot", "lower"]) {
      await page.evaluate(({id, payload}) => renderPlot(document.getElementById(id), payload, {compact: true}), {id, payload});
      const plot = page.locator(`#${id}`);
      await plot.scrollIntoViewIfNeeded();
      const box = await plot.boundingBox();
      const size = await plot.evaluate(p => p._fullLayout._size);
      await page.mouse.move(box.x + size.l + size.w * .5, box.y + size.t + size.h * .45);
      await page.waitForTimeout(120);
      const badges = plot.locator('.chart-axis-badge.visible, .chart-series-value-badge.visible');
      assert.equal(await badges.count(), 3, "both crosshair badges and the observed-value badge appear");
      const positions = await badges.evaluateAll(nodes => nodes.map(node => {
        const rect = node.getBoundingClientRect();
        const host = node.parentElement.getBoundingClientRect();
        return {parent: node.offsetParent?.id || node.offsetParent?.tagName, left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, host: {left: host.left, top: host.top, right: host.right, bottom: host.bottom}};
      }));
      for (const position of positions) {
        assert.equal(position.parent, id, `dashboard badges must be positioned within their own plot: ${JSON.stringify(position)}`);
        assert(position.left >= box.x - 1 && position.right <= box.x + box.width + 1);
        assert(position.top >= box.y - 1 && position.bottom <= box.y + box.height + 1);
      }
      await page.mouse.move(box.x + size.l + size.w * .25, box.y + size.t + size.h * .2);
      await page.mouse.down();
      await page.mouse.move(box.x + size.l + size.w * .8, box.y + size.t + size.h * .7, {steps: 5});
      const selection = plot.locator('.chart-zoom-selection:not([hidden])');
      const selectedBox = await selection.boundingBox();
      assert.equal(await selection.evaluate(node => node.offsetParent.id), id);
      assert(Math.abs(selectedBox.y - (box.y + size.t)) < 1);
      assert(Math.abs(selectedBox.height - size.h) < 1);
      await page.mouse.up();
      await page.waitForTimeout(450);
      const reset = plot.locator('.chart-reset-zoom:not([hidden])');
      const resetBox = await reset.boundingBox();
      assert.equal(await reset.evaluate(node => node.offsetParent.id), id);
      assert(resetBox.x >= box.x && resetBox.x + resetBox.width <= box.x + box.width);
      assert(resetBox.y >= box.y && resetBox.y + resetBox.height <= box.y + box.height);
      await reset.click();
      await page.waitForTimeout(450);
      assert.equal(await plot.locator('.chart-reset-zoom:not([hidden])').count(), 0);
    }
    assert.deepEqual(errors, []);
    console.log("PASS: dashboard hover badges, drag selection, and reset stay within their own chart, including a scrolled lower row.");
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
