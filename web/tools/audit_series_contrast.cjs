#!/usr/bin/env node
// Audits every generated chart payload for series colours (lines, markers,
// per-point colour arrays, fills, candles, shapes, annotations) whose contrast
// against the plot surface is below the WCAG non-text threshold in either theme.
//
//   node tools/audit_series_contrast.cjs [--data DIR] [--min 3] [--json FILE] [--list]
//
// DIR is a directory holding site-manifest.json plus the chart payloads it points
// at (the generated `web/data/bitcoin`, or a mirror of the published site's
// `web/data/bitcoin`). The audit loads the real assets/site.js, so "before" is
// the previous palette-only mapping and "after" is the shipped adaptation.
// Exit status is 1 when any colour is still below the threshold after the fix.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};
const dataDir = path.resolve(option("--data", path.join(__dirname, "../data/bitcoin")));
const minContrast = Number(option("--min", "3"));
const jsonOut = option("--json", "");
const listAll = args.includes("--list");

const SURFACES = {
  dark: { "--surface (terminal)": "#181816", "--surface-raised (cards)": "#1d1d1a" },
  light: { "--surface (terminal)": "#fffefa", "--surface-raised (cards)": "#ffffff" },
};

const context = {
  window: { location: { search: "" } },
  document: { body: { dataset: {} }, documentElement: { dataset: { theme: "light" } }, addEventListener() {} },
  URLSearchParams, Intl,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, "../assets/site.js"), "utf8"), context);
const site = context;
const DECORATIVE_ALPHA = vm.runInContext("DECORATIVE_ALPHA", context);

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

const manifestFile = path.join(dataDir, "site-manifest.json");
if (!fs.existsSync(manifestFile)) {
  console.error(`No site-manifest.json in ${dataDir}. Generate the site or pass --data.`);
  process.exit(2);
}
const manifest = readJson(manifestFile);
const dataRoot = path.resolve(dataDir, "../../..");

// Every colour a chart can put on screen, as { where, color }. `overlay:` entries
// are UI additions (halving markers, moving-average line) rather than payload data.
function chartColors(payload) {
  const found = [];
  const collect = (where) => (color, at) => { found.push({ where: `${where}:${at}`, at, color }); return color; };
  (payload.series || []).forEach((series, index) => {
    site.mapSeriesColors(series, collect(`series[${index}] ${series.name}`));
  });
  site.mapLayoutSeriesColors(payload.layout || {}, collect("layout"));
  const overlays = site.halvingOverlayLayout(payload);
  const own = payload.layout || {};
  site.mapLayoutSeriesColors({
    shapes: overlays.shapes.slice((own.shapes || []).length),
    annotations: overlays.annotations.slice((own.annotations || []).length),
  }, collect("overlay:halving"));
  found.push({ where: "overlay:moving-average", at: "line.color", color: "#7c5ca8" });
  return found;
}

function paletteOnly(color) {
  return site.themePaletteColor(color);
}

function failing(color, surface) {
  const parsed = site.parseCssColor(color);
  if (!parsed || parsed.a < DECORATIVE_ALPHA) return false;
  const effective = parsed.a < 1 ? site.blendOver(parsed, site.parseCssColor(surface)) : parsed;
  return site.contrastRatio(effective, surface) < minContrast;
}

const report = { before: {}, after: {}, charts: manifest.charts.filter((chart) => chart.data_path).length };
const detail = [];
let scanned = 0;
let missing = 0;

for (const chart of manifest.charts) {
  if (!chart.data_path) continue;
  const file = path.join(dataRoot, chart.data_path);
  if (!fs.existsSync(file)) { missing += 1; continue; }
  const payload = readJson(file);
  scanned += 1;
  const colors = chartColors(payload);
  for (const [theme, surfaces] of Object.entries(SURFACES)) {
    site.document.documentElement.dataset.theme = theme;
    const adapters = Object.fromEntries(Object.values(surfaces).map((surface) => [surface, site.themeColorAdapter(site.parseCssColor(surface))]));
    for (const [surfaceName, surface] of Object.entries(surfaces)) {
      colors.forEach(({ where, at, color }) => {
        const before = paletteOnly(color);
        const after = adapters[surface](color, at);
        const record = { chart: chart.id, theme, surface: surfaceName, where, source: color, before, after };
        for (const stage of ["before", "after"]) {
          if (failing(record[stage], surface)) {
            const group = where.startsWith("overlay:") ? "overlay" : "payload";
            const bucket = (report[stage][`${group} ${theme} ${surfaceName}`] ||= { uses: 0, charts: new Set(), colors: new Map() });
            bucket.uses += 1;
            bucket.charts.add(chart.id);
            bucket.colors.set(record[stage], (bucket.colors.get(record[stage]) || 0) + 1);
            if (stage === "before") detail.push(record);
          }
        }
        if (listAll && failing(record.after, surface)) console.log("STILL FAILING", record);
      });
    }
  }
}

const summary = {};
for (const stage of ["before", "after"]) {
  summary[stage] = {};
  for (const group of ["payload", "overlay"]) {
    const charts = new Set();
    const uses = { dark: 0, light: 0 };
    const colors = new Map();
    for (const [key, bucket] of Object.entries(report[stage])) {
      const [bucketGroup, theme] = key.split(" ");
      if (bucketGroup !== group) continue;
      bucket.charts.forEach((id) => charts.add(id));
      uses[theme] += bucket.uses;
      bucket.colors.forEach((count, color) => colors.set(color, (colors.get(color) || 0) + count));
    }
    summary[stage][group] = { charts: [...charts].sort(), colorUses: uses, distinctColors: Object.fromEntries([...colors].sort((a, b) => b[1] - a[1])) };
  }
}

const byTheme = (stage, theme, group = "payload") => {
  const ids = new Set();
  for (const [key, bucket] of Object.entries(report[stage])) if (key.startsWith(`${group} ${theme}`)) bucket.charts.forEach((id) => ids.add(id));
  return [...ids].sort();
};

console.log(`Scanned ${scanned} chart payloads (${missing} missing) from ${dataDir}`);
console.log(`Threshold: ${minContrast}:1 against every plot surface in both themes`);
for (const stage of ["before", "after"]) {
  for (const group of ["payload", "overlay"]) {
    const entry = summary[stage][group];
    console.log(`
${stage.toUpperCase()} ${group} colours: ${entry.charts.length} charts affected; below-threshold uses dark=${entry.colorUses.dark} light=${entry.colorUses.light}`);
    console.log(`  dark-theme charts: ${byTheme(stage, "dark", group).length}; light-theme charts: ${byTheme(stage, "light", group).length}`);
    const top = Object.entries(entry.distinctColors).slice(0, 15);
    if (top.length) console.log(`  colours: ${top.map(([color, count]) => `${color}x${count}`).join(" ")}`);
  }
}
console.log(`
Payload charts affected before the fix, dark theme (${byTheme("before", "dark").length}):
${byTheme("before", "dark").join(", ")}`);
console.log(`
Payload charts affected before the fix, light theme (${byTheme("before", "light").length}):
${byTheme("before", "light").join(", ")}`);
if (jsonOut) {
  fs.writeFileSync(jsonOut, JSON.stringify({
    scanned, threshold: minContrast, summary,
    darkCharts: byTheme("before", "dark"), lightCharts: byTheme("before", "light"), detail,
  }, null, 2));
}
const stillFailing = summary.after.payload.charts.length + summary.after.overlay.charts.length;
process.exit(stillFailing ? 1 : 0);
