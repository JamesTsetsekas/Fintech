const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");

// Shape of the real "PlanB: Stock to Flow + RSI + MA + Realized" (pb-various)
// payload: near-black price/S2F lines, a pale dashed line, a grey MA and a
// per-point rainbow marker array. Near-black colours are invisible on the dark
// surface unless they are adapted at render time.
const dates = Array.from({ length: 12 }, (_, index) => `${2012 + index}-06-01`);
const rainbow = ["#ea5149", "#a9fc4e", "#75fbfd", "#0106f5", "#ffff54", "#24c813", "#ea5149", "#a9fc4e", "#75fbfd", "#0106f5", "#ffff54", "#24c813"];
const payload = {
  title: "PlanB: Stock to Flow + RSI + MA + Realized", x_value_type: "date",
  series: [
    { type: "scatter", mode: "lines+markers", name: "Price", x: dates, y: dates.map((_, i) => 10 ** (1 + i / 3)), line: { color: "#1f1e1c", width: 4 }, marker: { color: rainbow, size: 6 } },
    { type: "scatter", mode: "lines", name: "Realized Price", x: dates, y: dates.map((_, i) => 8 ** (1 + i / 3)), line: { color: "#b5b2aa", width: 1, dash: "dash" } },
    { type: "scatter", mode: "lines", name: "Stock-to-Flow Model (2024 refit)", x: dates, y: dates.map((_, i) => 10 ** (1.2 + Math.floor(i / 4))), line: { color: "#1f1e1c", width: 1.5, shape: "hv" } },
    { type: "scatter", mode: "lines", name: "200WMA", x: dates, y: dates.map((_, i) => 9 ** (1 + i / 3)), line: { color: "#6c6a64", width: 1.25 } },
  ],
  layout: {
    yaxis: { type: "log", tickprefix: "$" },
    shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: 100, y1: 100, line: { color: "#1f1e1c", dash: "dot", width: 1 } }],
    annotations: [{ x: dates[3], y: 1000, text: "note", showarrow: false, font: { color: "#1f1e1c" } }],
  },
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 700 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setContent(`<div id="surface" style="background:var(--surface);padding:8px">
      <div id="series-list"><span class="series-dot" id="dot" data-source-color="#1f1e1c"></span></div>
      <div id="plot" style="position:relative;width:1000px;height:520px"></div></div>`);
    await page.addStyleTag({ path: path.resolve(__dirname, "../assets/site.css") });
    await page.addScriptTag({ url: "https://cdn.plot.ly/plotly-2.35.2.min.js" });
    await page.addScriptTag({ path: path.resolve(__dirname, "../assets/site.js") });

    // Reads everything Plotly actually drew: full trace colours, shapes, annotations and legend swatches.
    const inspect = () => page.evaluate(() => {
      const plot = document.querySelector("#plot");
      const surface = plotSurfaceColor(plot);
      const ratio = (color) => {
        const parsed = parseCssColor(color);
        return contrastRatio(parsed.a < 1 ? blendOver(parsed, surface) : parsed, surface);
      };
      const traces = plot._fullData.map((trace) => ({
        name: trace.name,
        line: trace.line?.color,
        lineRatio: trace.line?.color ? ratio(trace.line.color) : null,
        markerRatios: Array.isArray(trace.marker?.color) ? trace.marker.color.map(ratio) : [],
      }));
      const legend = [...plot.querySelectorAll(".legend .traces")].map((item) => {
        const line = item.querySelector(".legendlines path.js-line");
        return { name: item.textContent.trim(), stroke: line ? getComputedStyle(line).stroke : null };
      });
      return {
        surface: formatCssColor(surface),
        traces, legend,
        shapeColor: plot._fullLayout.shapes[0].line.color,
        annotationColor: plot._fullLayout.annotations[0].font.color,
        dot: getComputedStyle(document.querySelector("#dot")).backgroundColor,
        minimum: MIN_SERIES_CONTRAST,
      };
    });
    const cssRgb = (hex) => {
      const value = parseInt(hex.slice(1), 16);
      return `rgb(${value >> 16}, ${(value >> 8) & 255}, ${value & 255})`;
    };
    // The page keeps one payload object across renders to prove it is never mutated.
    await page.evaluate((source) => { window.__payload = source; window.__frozen = JSON.stringify(source); }, payload);
    const render = (theme) => page.evaluate(async (theme) => {
      document.documentElement.dataset.theme = theme;
      document.dispatchEvent(new CustomEvent("fintech-theme-change"));
      await renderPlot(document.querySelector("#plot"), window.__payload, {});
    }, theme);
    const mutated = () => page.evaluate(() => JSON.stringify(window.__payload) !== window.__frozen);

    // Dark theme: nothing may fall below the threshold and legend swatches must match the traces.
    await render("dark");
    let state = await inspect();
    assert.equal(state.surface, "#181816", "plot surface is read from the actual --surface background");
    for (const trace of state.traces) {
      assert.ok(trace.lineRatio === null || trace.lineRatio >= state.minimum, `${trace.name} line ${trace.line} is ${trace.lineRatio} on dark`);
      trace.markerRatios.forEach((value, index) => assert.ok(value >= state.minimum, `${trace.name} marker ${index} is ${value} on dark`));
    }
    assert.equal(state.legend.length, 4, "legend lists every series");
    for (const trace of state.traces) {
      const item = state.legend.find((entry) => entry.name.startsWith(trace.name));
      assert.ok(item, `legend entry for ${trace.name}`);
      assert.equal(item.stroke.replace(/\s/g, ""), cssRgb(trace.line).replace(/\s/g, ""), `legend swatch for ${trace.name} matches its trace`);
    }
    const price = state.traces[0].line;
    assert.notEqual(price, "#1f1e1c", "near-black Price line was lifted");
    assert.equal(state.traces[0].line, state.traces[2].line, "series sharing a source colour share the adapted colour");
    assert.ok(state.traces[3].lineRatio >= state.minimum, "grey 200WMA is readable");
    assert.ok(parseInt(state.shapeColor.slice(1), 16) > 0x808080, `near-black shape line adapted, got ${state.shapeColor}`);
    assert.notEqual(state.annotationColor, "#1f1e1c", "annotation text adapted");
    assert.equal(state.dot, "rgb(227, 226, 224)", "sidebar dot follows the theme toggle event");
    assert.equal(await mutated(), false, "source payload is not mutated by the dark render");

    // Live toggle to light without reload: near-blacks are kept, pale colours are darkened.
    await render("light");
    state = await inspect();
    assert.equal(state.surface, "#fffefa");
    for (const trace of state.traces) {
      assert.ok(trace.lineRatio === null || trace.lineRatio >= state.minimum, `${trace.name} line ${trace.line} is ${trace.lineRatio} on light`);
      trace.markerRatios.forEach((value, index) => assert.ok(value >= state.minimum, `${trace.name} marker ${index} is ${value} on light`));
    }
    assert.equal(state.traces[0].line.toLowerCase(), "#1f1e1c", "near-black stays untouched on the light surface");
    assert.notEqual(state.traces[1].line.toLowerCase(), "#b5b2aa", "pale dashed line is darkened on light");
    assert.equal(state.dot, "rgb(31, 30, 28)", "sidebar dot returns to the source colour on light");
    for (const trace of state.traces) {
      const item = state.legend.find((entry) => entry.name.startsWith(trace.name));
      assert.equal(item.stroke.replace(/\s/g, ""), cssRgb(trace.line).replace(/\s/g, ""));
    }

    // And back to dark again.
    await render("dark");
    state = await inspect();
    assert.ok(state.traces[0].lineRatio >= state.minimum);
    assert.equal(await mutated(), false, "source payload never mutated across theme changes");
    assert.deepEqual(errors, []);
    console.log("PASS: dark-theme series, legend swatches, shapes and sidebar dots meet contrast; light theme keeps near-blacks; live toggle never mutates the payload.");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
