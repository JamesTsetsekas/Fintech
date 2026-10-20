const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

// The default fixtures reproduce the imported source schema and deliberately
// exceed the compact point budget. Opt into generated public observations with
// FINTECH_LIVE_CHARTS=1 after building web/data.
function payload(id) {
  if (process.env.FINTECH_LIVE_CHARTS === "1") return JSON.parse(fs.readFileSync(path.resolve(__dirname, `../data/bitcoin/${id}.json`), "utf8"));
  const x = Array.from({ length: 850 }, (_, index) => new Date(Date.UTC(2018, 0, index * 3 + 1)).toISOString().slice(0, 10));
  const nupl = id === "nupl";
  const values = x.map((_, index) => nupl ? .1 + .9 * Math.sin(index / 70) : 2.5 + 2.5 * Math.sin(index / 70));
  const metric = { source_key: nupl ? "nupl" : "mvrv_z_score", name: nupl ? "Net Unrealized Profit/Loss (NUPL)" : "MVRV Z-Score", type: "scatter", mode: "lines", axis: "y2", x, y: values, line: { color: "#c96442", width: 2 } };
  if (nupl) {
    metric.value_colored_line = true;
    metric.marker = { color: values.map((value) => value < 0 ? "#e54242" : value < .25 ? "#ef7f11" : value < .5 ? "#ebd249" : value < .75 ? "#24c813" : "#4467eb"), size: 0 };
  }
  return {
    id, x_value_type: "date",
    signal_view: { mode: "absolute", series_key: metric.source_key, min: nupl ? -.25 : 0, max: nupl ? .8 : 5 },
    value_zones: nupl ? [] : [{ seriesKey: "mvrv_z_score", greenBelow: .85, redAbove: 1.75 }],
    series: [
      { source_key: "price", name: "BTC price", type: "scatter", mode: "lines", axis: "y", x, y: x.map((_, index) => 1000 + index * 100), line: { color: "#eef3f8", width: 1.6 } },
      metric,
    ],
    layout: { xaxis: { range: [x[0], x.at(-1)] }, yaxis: { title: "BTC price (USD)", type: "log", tickprefix: "$" }, yaxis2: { title: metric.name, side: "right", overlaying: "y" } },
  };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 660 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setContent('<html data-theme="dark"><body><div id="plot" style="position:relative;width:1050px;height:600px"></div></body></html>');
    await page.addStyleTag({ path: path.resolve(__dirname, "../assets/site.css") });
    await page.addScriptTag({ url: "https://cdn.plot.ly/plotly-2.35.2.min.js" });
    await page.addScriptTag({ path: path.resolve(__dirname, "../assets/site.js") });
    const render = async (data, options = {}) => {
      const unchanged = await page.evaluate(async ({ data, options }) => {
        const before = JSON.stringify(data);
        await renderPlot(document.querySelector("#plot"), data, options);
        return before === JSON.stringify(data);
      }, { data, options });
      assert(unchanged, "the real renderer leaves canonical payloads unchanged");
    };
    const mvrv = payload("mvrv-z-score");
    const canonical = JSON.stringify(mvrv);
    const plot = page.locator("#plot");
    for (const compact of [false, true]) {
      await render(mvrv, { compact, maxPoints: 600 });
      const normal = await plot.evaluate((target) => ({
        traces: target.data.map((trace) => ({ name: trace.name, mode: trace.mode, marker: trace.marker })),
        rightAxis: Boolean(target._fullLayout.yaxis2),
        bands: target.layout.shapes.length,
      }));
      assert(normal.rightAxis, "normal MVRV retains its score axis");
      assert.equal(normal.traces.length, 2);
      assert(normal.traces.every((trace) => trace.mode === "lines" && !trace.marker), "normal MVRV has connected lines without artificial dots");
      assert.equal(normal.bands, 2);

      await render(mvrv, { compact, signalView: true, maxPoints: 600 });
      const signal = await plot.evaluate((target) => ({ traces: target.data.length, rightAxis: Boolean(target._fullLayout.yaxis2), mode: target.data[0].mode, points: target.data[0].x.length, size: target.data[0].marker.size }));
      assert.equal(signal.traces, 1);
      assert.equal(signal.rightAxis, false, "Signal view uses only the USD axis");
      assert.equal(signal.mode, "markers");
      assert.equal(signal.size, 8);
      assert.equal(signal.points, mvrv.series.find((series) => series.source_key === "price").x.length, "Signal view retains every source observation");
      const bounds = await plot.boundingBox();
      const hover = await plot.evaluate((target) => {
        const date = target.data[0].x[700];
        return { x: target._fullLayout.xaxis._offset + target._fullLayout.xaxis.d2p(date), y: target._fullLayout.yaxis._offset + target._fullLayout.yaxis._length / 2, expected: formatHoverMetricValue(target.data[0].signal_metric_name, target.data[0].signal_metric_values[700]) };
      });
      await page.mouse.move(bounds.x + hover.x, bounds.y + hover.y);
      await page.waitForTimeout(100);
      const selected = await plot.evaluate((target) => ({ index: target._hoverdata?.[0]?.pointNumber, date: target._hoverdata?.[0]?.x }));
      assert(Math.abs(selected.index - 700) <= 1, "dense source dates select the nearest pixel observation");
      const originalMetric = mvrv.series.find((series) => series.source_key === "mvrv_z_score");
      const originalIndex = originalMetric.x.findIndex((date) => new Date(date).getTime() === new Date(selected.date).getTime());
      const expectedReading = await page.evaluate(({ name, value }) => formatHoverMetricValue(name, value), { name: originalMetric.name, value: originalMetric.y[originalIndex] });
      const hoverText = await plot.locator(".hoverlayer").textContent();
      assert(hoverText.includes(`MVRV Z-Score: ${expectedReading}`), `Signal hover includes the original metric reading: expected ${expectedReading}; saw ${hoverText}`);
      await page.mouse.move(1090, 640);
    }
    assert.equal(JSON.stringify(mvrv), canonical);

    await render(payload("nupl"));
    const nupl = await plot.evaluate((target) => {
      const colors = target.data.filter((trace) => trace.source_key === "nupl" && !trace.meta?.fintechHelper);
      return { modes: colors.map((trace) => trace.mode), groups: [...new Set(colors.map((trace) => trace.legendgroup))], legends: colors.filter((trace) => trace.showlegend).length, pointMarkers: target.querySelectorAll(".scatterlayer .point").length };
    });
    assert(nupl.modes.length > 1 && nupl.modes.every((mode) => mode === "lines"));
    assert.equal(nupl.pointMarkers, 0, "normal NUPL is a continuous five-color line");
    assert.equal(nupl.groups.length, 1);
    assert.equal(nupl.legends, 1);
    assert.deepEqual(errors, []);
    if (process.env.FINTECH_SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.FINTECH_SCREENSHOT_DIR, { recursive: true });
      for (const [name, data, options] of [
        ["nupl-normal", payload("nupl"), {}],
        ["mvrv-normal", mvrv, {}],
        ["mvrv-signals", mvrv, { signalView: true }],
      ]) {
        await render(data, options);
        await plot.screenshot({ path: path.join(process.env.FINTECH_SCREENSHOT_DIR, `${name}.png`) });
      }
    }
    console.log("PASS: MVRV normal/signal modes match source semantics in compact and terminal views; NUPL is continuous and shares one legend group.");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
