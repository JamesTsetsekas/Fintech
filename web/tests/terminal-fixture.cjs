// Serves the real chart terminal page with a small local manifest so browser
// checks exercise charts/index.html, site.js, and site.css end to end.
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "../..");
const ORIGIN = "http://fintech.test";
const BOILERPLATE = "Historical on-chain series, refreshed during the Fintech site build.";
const EVIL_COLOR = 'red" onmouseover="window.injected=1" data-x="';

const weekly = (() => {
  const dates = [];
  for (let time = Date.UTC(2016, 0, 3); time <= Date.UTC(2026, 9, 25); time += 7 * 86_400_000) {
    dates.push(new Date(time).toISOString().slice(0, 10));
  }
  return dates;
})();
const price = weekly.map((_, index) => Math.round(400 * Math.exp(index / 105) * (1 + 0.25 * Math.sin(index / 9))));

function payload(id, series, extra = {}) {
  return { id, title: id, x_value_type: "date", updated_at: "2026-10-26T00:00:00Z", show_range_selector: true, allow_scale_toggle: false, series, layout: { xaxis: { type: "date" }, yaxis: { type: "linear" } }, ...extra };
}

const metric = (name, values, extra = {}) => ({ type: "scatter", mode: "lines", name, x: weekly, y: values, hovertemplate: "%{x}<br>%{y:,.4g}<extra>%{fullData.name}</extra>", ...extra });
const btc = { type: "scatter", mode: "lines", name: "BTC price", source_key: "price", x: weekly, y: price, hovertemplate: "%{x}<br>$%{y:,.0f}<extra>BTC price</extra>", line: { color: "#f5c84b" } };
let peak = 0;
const drawdown = price.map((value) => { peak = Math.max(peak, value); return Math.round((value / peak - 1) * 1000) / 10; });
const projectionDates = [...weekly, "2030-01-01", "2039-12-27"];

const payloads = {
  "price": payload("price", [btc], { allow_scale_toggle: true, default_scale: "log", layout: { xaxis: { type: "date" }, yaxis: { type: "log", tickprefix: "$" } } }),
  "drawdown": payload("drawdown", [metric("Drawdown", drawdown, { hovertemplate: "%{x}<br>%{y:.1f}%<extra>Drawdown</extra>", line: { color: "#ff5f63" } })]),
  "sharpe": payload("sharpe", [metric("1Y Sharpe proxy", weekly.map((_, index) => Math.round(Math.sin(index / 20) * 150) / 100), { hovertemplate: "%{x}<br>%{y:.2f}<extra>Sharpe</extra>" })]),
  "mvrv-z-score": payload("mvrv-z-score", [btc, metric("MVRV Z-Score", weekly.map((_, index) => 1 + Math.sin(index / 30)), { axis: "y2" })]),
  "sth-mvrv": payload("sth-mvrv", [metric("STH MVRV", weekly.map((_, index) => 1 + Math.sin(index / 25) / 3))]),
  "lth-mvrv": payload("lth-mvrv", [metric("LTH MVRV", weekly.map((_, index) => 2 + Math.sin(index / 25)))]),
  "nupl": payload("nupl", [metric("NUPL", weekly.map((_, index) => Math.sin(index / 40) / 2))]),
  "colour-check": payload("colour-check", [metric("Injected colour", weekly.map((_, index) => index), { line: { color: EVIL_COLOR } })]),
  "projection": payload("projection", [
    { type: "scatter", mode: "lines", name: "Support projection", x: projectionDates, y: projectionDates.map((_, index) => 300 * Math.exp(index / 110)), hovertemplate: "%{x}<br>$%{y:,.0f}<extra>Support</extra>" },
    btc,
  ]),
  "pb-various": payload("pb-various", [btc]),
};

const chart = (id, title, section, sectionId, description = BOILERPLATE, order = 0) => ({ id, title, section, section_id: sectionId, description, kind: "interactive", data_path: `web/data/bitcoin/${id}.json`, order });
const manifest = {
  generated_at: "2026-10-26T00:00:00Z",
  sections: [
    { id: "cycle-models", name: "Cycle Models" },
    { id: "technical", name: "Technical" },
    { id: "returns", name: "Returns" },
    { id: "drawdowns", name: "Drawdowns" },
    { id: "onchain", name: "On-Chain" },
  ],
  charts: [
    chart("pb-various", "PlanB Composite", "Cycle Models", "cycle-models", "Stock-to-flow composite with realized price.", 1),
    chart("projection", "Power Law Projection", "Cycle Models", "cycle-models", "Long-range model with projected support.", 2),
    chart("price", "BTC Price", "Technical", "technical", "Bitcoin closing price.", 3),
    chart("drawdown", "BTC Drawdown From ATH", "Drawdowns", "drawdowns", "Distance below the running all-time high.", 4),
    chart("sharpe", "Risk-Adjusted Returns", "Returns", "returns", "Trailing one-year Sharpe proxy.", 5),
    chart("mvrv-z-score", "MVRV Z-Score", "On-Chain", "onchain", BOILERPLATE, 10),
    chart("sth-mvrv", "MVRV Short Term Supply", "On-Chain", "onchain", BOILERPLATE, 11),
    chart("lth-mvrv", "MVRV Long Term Supply", "On-Chain", "onchain", BOILERPLATE, 12),
    chart("nupl", "NUPL (Net Unrealized Profit Loss)", "On-Chain", "onchain", BOILERPLATE, 13),
    chart("colour-check", "Colour Injection Check", "On-Chain", "onchain", BOILERPLATE, 14),
  ],
};

const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

async function serveTerminal(page) {
  await page.route(`${ORIGIN}/**`, (route) => {
    let file = decodeURIComponent(new URL(route.request().url()).pathname).replace(/^\/+/, "");
    if (!file || file.endsWith("/")) file += "index.html";
    if (file === "web/data/bitcoin/site-manifest.json") return route.fulfill({ status: 200, contentType: types[".json"], body: JSON.stringify(manifest) });
    const data = file.match(/^web\/data\/bitcoin\/([\w-]+)\.json$/);
    if (data) {
      return payloads[data[1]]
        ? route.fulfill({ status: 200, contentType: types[".json"], body: JSON.stringify(payloads[data[1]]) })
        : route.fulfill({ status: 404, body: "missing" });
    }
    const absolute = path.join(ROOT, file);
    if (!absolute.startsWith(ROOT) || !fs.existsSync(absolute)) return route.fulfill({ status: 404, body: "missing" });
    return route.fulfill({ status: 200, contentType: types[path.extname(absolute)] || "application/octet-stream", body: fs.readFileSync(absolute) });
  });
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
}

async function openTerminal(page, query) {
  await page.goto(`${ORIGIN}/charts/${query}`);
  await waitForChart(page);
}

async function waitForChart(page, id) {
  await page.waitForFunction((expected) => {
    const plot = document.querySelector("#terminal-plot");
    return (!expected || new URL(location.href).searchParams.get("chart") === expected)
      && typeof appState !== "undefined" && appState.currentPayload
      && (!expected || appState.currentPayload.id === expected)
      && plot?._fullLayout
      && /^Showing /.test(document.querySelector("#terminal-status")?.textContent || "");
  }, id, { timeout: 30000 });
  await page.waitForTimeout(450);
}

module.exports = { ORIGIN, BOILERPLATE, manifest, payloads, serveTerminal, openTerminal, waitForChart };
