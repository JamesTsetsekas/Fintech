#!/usr/bin/env node
// Renders every chart in a real browser, in both themes, and reports each colour
// Plotly actually drew (resolved trace colours, named colour scales, shapes,
// annotations) whose contrast against the surface behind the plot is below the
// threshold. Complements audit_series_contrast.cjs, which reads payloads only.
//
//   python -m http.server 8765          # from the repo root, with web/data generated
//   node tools/audit_rendered_contrast.cjs --base http://127.0.0.1:8765 [--min 3] [--charts a,b,c]
//
// Exit status is 1 when anything is below the threshold.
const { chromium } = require("playwright");

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};
const base = option("--base", "http://127.0.0.1:8765").replace(/\/$/, "");
const minimum = Number(option("--min", "3"));
const only = option("--charts", "") ? option("--charts", "").split(",") : null;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const failures = [];
  let rendered = 0;
  try {
    for (const theme of ["dark", "light"]) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      await context.addInitScript((value) => { try { localStorage.setItem("fintech-theme", value); } catch (error) { /* ignore */ } }, theme);
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(`${base}/charts/?chart=price`, { waitUntil: "networkidle" });
      await page.waitForSelector("#terminal-plot .main-svg", { timeout: 30000 });
      const ids = await page.evaluate(() => appState.manifest.charts.filter((chart) => chart.data_path).map((chart) => chart.id));
      for (const id of only || ids) {
        const found = await page.evaluate(async ({ id, minimum }) => {
          const chart = appState.manifest.charts.find((item) => item.id === id);
          const payload = await fetchJson(assetPath(chart.data_path));
          const target = document.querySelector("#terminal-plot");
          await renderPlot(target, payload, {});
          const surface = plotSurfaceColor(target);
          const bad = [];
          const check = (where, color) => {
            const parsed = parseCssColor(color);
            if (!parsed || parsed.a < DECORATIVE_ALPHA) return;
            const ratio = contrastRatio(parsed.a < 1 ? blendOver(parsed, surface) : parsed, surface);
            if (ratio < minimum) bad.push({ where, color, ratio: Math.round(ratio * 100) / 100 });
          };
          (target._fullData || []).forEach((trace, index) => {
            const label = `trace[${index}] ${trace.name || trace.type}`;
            const mode = String(trace.mode || "");
            const visible = trace.visible !== false && trace.visible !== "legendonly";
            if (!visible || trace.hoverinfo === "skip" && !trace.showlegend) return;
            if (trace.type === "scatter" || trace.type === "scattergl") {
              if (mode.includes("lines") && trace.line?.width !== 0) check(`${label} line`, trace.line?.color);
              if (mode.includes("markers")) {
                const color = trace.marker?.color;
                if (Array.isArray(color)) {
                  const strings = color.filter((value) => typeof value === "string");
                  new Set(strings).forEach((value) => check(`${label} marker`, value));
                  if (color.some((value) => typeof value === "number") && Array.isArray(trace.marker.colorscale)) {
                    trace.marker.colorscale.forEach(([, stop]) => check(`${label} marker colourscale`, stop));
                  }
                } else check(`${label} marker`, color);
              }
              if (trace.fill && trace.fill !== "none") check(`${label} fill`, trace.fillcolor);
            } else if (trace.type === "bar") {
              const color = trace.marker?.color;
              (Array.isArray(color) ? [...new Set(color)] : [color]).forEach((value) => check(`${label} bar`, value));
            } else if (trace.type === "candlestick" || trace.type === "ohlc") {
              check(`${label} increasing`, trace.increasing?.line?.color);
              check(`${label} decreasing`, trace.decreasing?.line?.color);
            }
          });
          (target._fullLayout.shapes || []).forEach((shape, index) => check(`shape[${index}] line`, shape.line?.color));
          (target._fullLayout.annotations || []).forEach((note, index) => check(`annotation[${index}] text`, note.font?.color));
          return bad;
        }, { id, minimum });
        rendered += 1;
        found.forEach((item) => failures.push({ theme, chart: id, ...item }));
      }
      if (errors.length) console.log(`[${theme}] page errors: ${[...new Set(errors)].join(" | ")}`);
      await context.close();
    }
  } finally {
    await browser.close();
  }
  const charts = new Set(failures.map((item) => item.chart));
  console.log(`Rendered ${rendered} chart/theme combinations; ${failures.length} colours below ${minimum}:1 across ${charts.size} charts`);
  failures.slice(0, 60).forEach((item) => console.log(`  ${item.theme} ${item.chart}: ${item.where} ${item.color} = ${item.ratio}:1`));
  process.exit(failures.length ? 1 : 0);
})();
