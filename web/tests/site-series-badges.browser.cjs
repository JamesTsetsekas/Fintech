const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 650 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.setContent('<div id="plot" style="position:relative;width:900px;height:500px"></div>');
    await page.addStyleTag({ path: path.resolve(__dirname, "../assets/site.css") });
    await page.addScriptTag({ url: "https://cdn.plot.ly/plotly-2.35.2.min.js" });
    await page.addScriptTag({ path: path.resolve(__dirname, "../assets/site.js") });
    await page.evaluate(async () => {
      const x = ["2024-01-01", "2025-01-01", "2026-01-01"];
      const target = document.querySelector("#plot");
      await Plotly.newPlot(target, [
        { type: "scatter", name: "Price", x, y: [10, 1000, 100000], mode: "markers", marker: { color: ["#0106f5", "#f9ff54", "#ea5149"], size: 8 } },
        { type: "scatter", name: "Score", x, y: [0, 50, 100], yaxis: "y2", mode: "lines", line: { color: "#c96442" } },
      ], {
        hovermode: "x unified", hoverdistance: -1,
        xaxis: { type: "date" },
        yaxis: { type: "log", range: [0, 6], tickprefix: "$" },
        yaxis2: { type: "linear", range: [-10, 110], overlaying: "y", side: "right", ticksuffix: "%" },
      });
      installSeriesValueBadges(target);
    });
    const plot = page.locator("#plot");
    const bounds = await plot.boundingBox();
    for (const [date, value, score, color] of [
      ["2025-01-01", 1000, 50, "rgb(249, 255, 84)"],
      ["2026-01-01", 100000, 100, "rgb(234, 81, 73)"],
    ]) {
      const geometry = await plot.evaluate((target, { date, value, score }) => {
        const layout = target._fullLayout;
        return {
          x: layout.xaxis._offset + layout.xaxis.d2p(date),
          pointerY: layout.yaxis._offset + layout.yaxis._length * 0.6,
          priceY: layout.yaxis._offset + layout.yaxis.d2p(value),
          scoreY: layout.yaxis2._offset + layout.yaxis2.d2p(score),
          text: formatCrosshairValue(value, layout.yaxis),
        };
      }, { date, value, score });
      await page.mouse.move(bounds.x + geometry.x, bounds.y + geometry.pointerY);
      await page.waitForTimeout(80);
      const priceBadge = plot.locator('.chart-series-value-badge[data-axis="yaxis"]');
      const scoreBadge = plot.locator('.chart-series-value-badge[data-axis="yaxis2"]');
      assert.equal(await priceBadge.textContent(), geometry.text);
      assert.equal(await scoreBadge.textContent(), `${score}%`);
      assert(Math.abs(await priceBadge.evaluate(node => parseFloat(node.style.top)) - geometry.priceY) < 0.01);
      assert(Math.abs(await scoreBadge.evaluate(node => parseFloat(node.style.top)) - geometry.scoreY) < 0.01);
      assert.equal(await priceBadge.evaluate(node => node.style.backgroundColor), color);
      assert.equal(await priceBadge.evaluate(node => getComputedStyle(node).display), "block");
      assert(Math.abs(geometry.priceY - geometry.pointerY) > 5, "series badge follows observed value independently of pointer Y");
    }
    await plot.evaluate(target => target.classList.add("chart-selecting"));
    assert.equal(await plot.locator('.chart-series-value-badge[data-axis="yaxis"]').evaluate(node => getComputedStyle(node).display), "none");
    await plot.evaluate(target => target.classList.remove("chart-selecting"));
    await page.mouse.move(990, 640);
    assert.equal(await plot.locator(".chart-series-value-badge.visible").count(), 0);
    await plot.evaluate(target => cleanupChartInteractions(target));
    assert.equal(await plot.locator(".chart-series-value-badge").count(), 0);
    assert.deepEqual(errors, []);
    console.log("PASS: hovered series badges follow actual log/linear observations and palette colors, independently of cursor Y, and clean up.");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
