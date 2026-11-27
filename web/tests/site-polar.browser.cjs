const assert = require("node:assert/strict");
const { chromium } = require("playwright");
const { manifest, payloads, serveTerminal, openTerminal } = require("./terminal-fixture.cjs");

// A polar payload shaped like build_bitcoin_spiral(): log price on a clockwise
// four-year clock. The terminal must render it without cartesian-only helpers.
const dates = [];
const prices = [];
for (let day = 0; day <= 4 * 365 * 3; day += 7) {
  dates.push(new Date(Date.UTC(2014, 0, 1) + day * 86_400_000).toISOString().slice(0, 10));
  prices.push(Math.round(300 * Math.exp(day / 700) * (1 + 0.3 * Math.sin(day / 120))));
}
const theta = dates.map((date) => ((Date.parse(date) - Date.UTC(2009, 0, 1)) / (4 * 365.25 * 86_400_000) * 360) % 360);
const custom = dates.map((date, index) => [date, `$${prices[index].toLocaleString("en-US")}`]);
payloads.spiral = {
  id: "spiral",
  title: "Bitcoin Spiral",
  x_value_type: "polar",
  updated_at: dates.at(-1),
  show_range_selector: false,
  allow_scale_toggle: false,
  series: [
    { type: "scatterpolar", name: "2026 (current year)", mode: "lines", theta: [90, 90, 180, 180], r: [0.1, 1e6, 1e6, 0.1], fill: "toself", fillcolor: "rgba(255,159,67,0.10)", line: { width: 0 }, hoverinfo: "skip" },
    { type: "scatterpolar", name: "Bitcoin", mode: "lines", theta, r: prices, customdata: custom, line: { color: "#ff9f43", width: 2.4 }, hovertemplate: "%{customdata[0]}<br>%{customdata[1]}<extra>Bitcoin</extra>" },
    { type: "scatterpolar", name: "Now", mode: "markers", theta: theta.slice(-1), r: prices.slice(-1), customdata: custom.slice(-1), marker: { color: "#eef3f8", size: 14 }, hovertemplate: "%{customdata[0]}<br>%{customdata[1]}<extra>Latest close</extra>" },
  ],
  layout: {
    hovermode: "closest",
    polar: {
      angularaxis: { rotation: 90, direction: "clockwise", tickmode: "array", tickvals: [0, 90, 180, 270], ticktext: ["2009", "2010", "2011", "2012"] },
      radialaxis: { type: "log", range: [-1, 6], tickmode: "array", tickvals: [1, 10, 100, 1e3, 1e4, 1e5, 1e6], ticktext: ["$1", "$10", "$100", "$1k", "$10k", "$100k", "$1M"] },
    },
  },
};
manifest.charts.push({ id: "spiral", title: "Bitcoin Spiral", section: "Cycle Models", section_id: "cycle-models", description: "Polar fixture.", kind: "interactive", data_path: "web/data/bitcoin/spiral.json", order: 20 });

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const [theme, width] of [["dark", 1280], ["light", 1280], ["dark", 390]]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      await context.addInitScript((value) => localStorage.setItem("fintech-theme", value), theme);
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await serveTerminal(page);
      await openTerminal(page, "?chart=spiral");

      const state = await page.locator("#terminal-plot").evaluate((plot) => ({
        polar: Boolean(plot._fullLayout.polar?._subplot),
        cartesian: Boolean(plot._fullLayout.xaxis || plot._fullLayout.yaxis),
        radialType: plot._fullLayout.polar?.radialaxis?.type,
        direction: plot._fullLayout.polar?.angularaxis?.direction,
        bgcolor: plot._fullLayout.polar?.bgcolor,
        gridcolor: plot._fullLayout.polar?.radialaxis?.gridcolor,
        rails: plot.querySelectorAll(".chart-scale-rail").length,
        badges: plot.querySelectorAll(".chart-axis-badge").length,
        yaxisOnTraces: plot.data.some((trace) => "yaxis" in trace),
        ticks: plot._fullLayout.polar?.radialaxis?.tickvals?.map((value, index) => [value, plot._fullLayout.polar.radialaxis.ticktext[index]]),
      }));
      assert.equal(state.polar, true, `${theme}: renders a polar subplot`);
      assert.equal(state.cartesian, false, `${theme}: no empty cartesian axes behind the spiral`);
      assert.equal(state.radialType, "log");
      assert.equal(state.direction, "clockwise");
      assert.equal(state.bgcolor, "rgba(0, 0, 0, 0)", `${theme}: polar background follows the page surface`);
      assert.equal(state.gridcolor, theme === "dark" ? "#34332e" : "#e8e6df", `${theme}: polar grid uses the theme grid color`);
      assert.equal(state.rails, 0, "no cartesian scale rails");
      assert.equal(state.badges, 0, "no cartesian crosshair badges");
      assert.equal(state.yaxisOnTraces, false, "polar traces are not bound to a cartesian y axis");
      assert.match(await page.locator("#terminal-status").textContent(), /^Showing Bitcoin Spiral/);
      // Narrow screens thin the radial labels to every other decade, keeping
      // each label paired with its own value and the outermost ring labelled.
      assert.deepEqual(state.ticks, width < 640
        ? [[1, "$1"], [100, "$100"], [1e4, "$10k"], [1e6, "$1M"]]
        : [[1, "$1"], [10, "$10"], [100, "$100"], [1e3, "$1k"], [1e4, "$10k"], [1e5, "$100k"], [1e6, "$1M"]]);

      // Hovering the latest point shows its date and price.
      await page.locator("#terminal-plot").evaluate((plot) => {
        const curveNumber = plot._fullData.findIndex((item) => item.name === "Now");
        Plotly.Fx.hover(plot, [{ curveNumber, pointNumber: 0 }], "polar");
      });
      await page.waitForSelector(".hoverlayer .hovertext", { timeout: 5000 });
      const hover = await page.locator(".hoverlayer .hovertext").first().textContent();
      assert.match(hover, new RegExp(`${dates.at(-1)}.*\\$${prices.at(-1).toLocaleString("en-US").replace(/,/g, ",")}`), `${theme} ${width}px: hover shows date and price`);

      assert.deepEqual(errors, [], `${theme}: no page errors`);
      await context.close();
    }
    console.log("site-polar.browser: ok");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
