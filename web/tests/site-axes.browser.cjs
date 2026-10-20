const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");

const payload = {
  x_value_type: "date",
  series: [
    { type: "scatter", name: "BTC price", axis: "y", x: ["2026-01-01", "2026-10-19"], y: [70000, 80000] },
    { type: "scatter", name: "Coins in loss", axis: "y2", x: ["2026-01-01", "2026-10-19"], y: [20, 30] },
    { type: "scatter", name: "Old minus new", axis: "y3", x: ["2026-01-01", "2026-10-19"], y: [-20, 20] },
  ],
  layout: {
    xaxis: { anchor: "y3" },
    yaxis: { type: "log", domain: [0.40, 1] },
    yaxis2: { overlaying: "y", side: "right", domain: [0.40, 1], range: [0, 100], ticksuffix: "%" },
    yaxis3: { domain: [0, 0.28], anchor: "x", range: [-50, 50], ticksuffix: " pp" },
  },
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 650 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setContent('<div id="plot" style="position:relative;width:900px;height:500px"></div>');
    await page.addStyleTag({ path: path.resolve(__dirname, "../assets/site.css") });
    await page.addScriptTag({ url: "https://cdn.plot.ly/plotly-2.35.2.min.js" });
    await page.addScriptTag({ path: path.resolve(__dirname, "../assets/site.js") });
    await page.evaluate((payload) => renderPlot(document.querySelector("#plot"), payload), payload);
    const plot = page.locator("#plot");
    const geometry = await plot.evaluate((target) => {
      const layout = target._fullLayout;
      return {
        x: layout.xaxis._offset + layout.xaxis._length / 2,
        top: layout.yaxis._offset + layout.yaxis._length * 0.4,
        lower: layout.yaxis3._offset + layout.yaxis3._length * 0.4,
        gutter: (layout.yaxis._offset + layout.yaxis._length + layout.yaxis3._offset) / 2,
        expectedLower: formatCrosshairValue(layout.yaxis3.p2d(layout.yaxis3._length * 0.4), layout.yaxis3),
        rails: [...target.querySelectorAll(".chart-scale-rail")].map((rail) => ({
          name: rail.dataset.axis, top: Number.parseFloat(rail.style.top), height: Number.parseFloat(rail.style.height),
          axisTop: layout[rail.dataset.axis]._offset, axisHeight: layout[rail.dataset.axis]._length,
        })),
      };
    });
    assert.equal(geometry.rails.length, 3);
    for (const rail of geometry.rails) {
      assert(Math.abs(rail.top - rail.axisTop) < 0.001, `${rail.name} rail uses its pane offset`);
      assert(Math.abs(rail.height - rail.axisHeight) < 0.001, `${rail.name} rail uses its pane height`);
    }
    const bounds = await plot.boundingBox();
    const yBadge = plot.locator(".chart-axis-badge-y");
    await page.mouse.move(bounds.x + geometry.x, bounds.y + geometry.lower);
    assert.equal(await yBadge.getAttribute("data-axis"), "yaxis3");
    assert.equal(await yBadge.textContent(), geometry.expectedLower);
    assert((await yBadge.textContent()).endsWith(" pp"));
    await page.mouse.move(bounds.x + geometry.x, bounds.y + geometry.top);
    assert.equal(await yBadge.getAttribute("data-axis"), "yaxis");
    await page.mouse.move(bounds.x + geometry.x, bounds.y + geometry.gutter);
    assert.equal(await plot.locator(".chart-axis-badge.visible").count(), 0, "pane gutter has no extrapolated axis badge");
    const initial = await plot.evaluate((target) => ({ top: target._fullLayout.yaxis.range.slice(), lower: target._fullLayout.yaxis3.range.slice() }));
    await plot.locator('.chart-scale-rail[data-axis="yaxis3"]').hover();
    await page.mouse.wheel(0, 120);
    await page.waitForFunction((initial) => document.querySelector("#plot")._fullLayout.yaxis3.range[0] !== initial, initial.lower[0]);
    const scaled = await plot.evaluate((target) => ({ top: target._fullLayout.yaxis.range.slice(), lower: target._fullLayout.yaxis3.range.slice() }));
    assert.deepEqual(scaled.top, initial.top, "lower-pane scaling leaves the price axis unchanged");
    assert.notDeepEqual(scaled.lower, initial.lower);
    assert.deepEqual(errors, []);
    console.log("PASS: multi-pane badges select local axes, gutter badges hide, and lower scale rail controls only its pane.");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
