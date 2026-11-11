const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

// Serves the real pages and assets from disk and the shared signal fixture as
// site data, so the test needs no network and no generated web/data.
const ROOT = path.resolve(__dirname, "../..");
const ORIGIN = "http://fintech.test";
const FIXTURES = path.resolve(__dirname, "fixtures/signals");
const fixture = (name) => fs.readFileSync(path.join(FIXTURES, name), "utf8");
const expected = JSON.parse(fixture("expected.json"));
const charts = JSON.parse(fixture("charts.json"));
// The manifest supplies the publication time and names the artifact it was
// built with; the artifact itself carries no clock reading.
const manifest = {
  generated_at: "2025-01-02T00:05:00+00:00",
  signals: { path: "web/data/bitcoin/signals.json", source_fingerprint: expected.source_fingerprint, data_through: expected.data_through, method_version: 2 },
  charts: [
    ...Object.keys(charts).map((id) => ({ id, title: id, section: "Fixture", description: "", kind: "interactive", data_path: `web/data/bitcoin/${id}.json` })),
    { id: "hodl-waves", title: "HODL Waves", section: "Fixture", description: "", kind: "interactive", data_path: "web/data/bitcoin/hodl-waves.json" },
  ],
};
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

async function open(browser, { width = 1280, artifact = true, storage = {} } = {}) {
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  await context.addInitScript((items) => {
    if (sessionStorage.getItem("seeded")) return;
    sessionStorage.setItem("seeded", "1");
    Object.entries(items).forEach(([key, value]) => localStorage.setItem(key, value));
  }, storage);
  const requests = [];
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== ORIGIN) return route.abort();
    requests.push(url.pathname);
    const json = (body) => route.fulfill({ contentType: "application/json", body: typeof body === "string" ? body : JSON.stringify(body) });
    if (url.pathname === "/web/data/bitcoin/site-manifest.json") return json(artifact ? manifest : { ...manifest, signals: null });
    if (url.pathname === "/web/data/bitcoin/signals.json") return artifact ? json(expected) : route.fulfill({ status: 404, body: "missing" });
    if (url.pathname === "/web/assets/signal-definitions.json") return json(fixture("definitions.json"));
    const chart = url.pathname.match(/^\/web\/data\/bitcoin\/(.+)\.json$/);
    if (chart) return charts[chart[1]] ? json(charts[chart[1]]) : route.fulfill({ status: 404, body: "missing" });
    let file = path.join(ROOT, decodeURIComponent(url.pathname));
    if (url.pathname.endsWith("/")) file = path.join(file, "index.html");
    if (!file.startsWith(ROOT) || !fs.existsSync(file)) return route.fulfill({ status: 404, body: "missing" });
    return route.fulfill({ contentType: TYPES[path.extname(file)] || "application/octet-stream", body: fs.readFileSync(file) });
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const visit = async (target, ready) => {
    requests.length = 0;
    await page.goto(`${ORIGIN}${target}`);
    await page.waitForSelector(ready, { state: "attached" });
  };
  const chartRequests = () => requests.filter((item) => /^\/web\/data\/bitcoin\/(?!site-manifest|signals\.json)/.test(item));
  return { context, page, requests, errors, visit, chartRequests };
}

const text = (page, selector) => page.locator(selector).innerText();
const index = String(Math.round(expected.composite.score));
const headline = new RegExp(`CYCLE INDEX\\s+${index}(?!\\d)`, "i");

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    // Signals page: one compact request, canonical index, freshness and method.
    for (const width of [1280, 390]) {
      const site = await open(browser, { width });
      await site.visit("/signals/", "#signal-table-body tr[data-signal-id]");
      assert.deepEqual(site.chartRequests(), [], "no per-signal chart payload is requested");
      assert.equal(site.requests.filter((item) => item.endsWith("/signals.json")).length, 1);
      assert.equal(await page_rows(site.page), expected.signals.length);
      const summary = await text(site.page, "#signal-summary");
      assert.match(summary, headline);
      assert.match(summary, /5 of 7 signals · equal weight/);
      const freshness = await text(site.page, "#signals-freshness");
      assert.match(freshness, /^Published Jan 2, 2025, 00:05 UTC · Data through Dec 17, 2024 · 2 signals stale: .+ · 3 signals unavailable: Too short, Renamed upstream series, Chart not generated$/);
      assert.equal(await text(site.page, "#signal-method-version"), "Method v2");
      const membership = await text(site.page, "#signal-method-membership");
      assert.match(membership, /In the Cycle Index \(7, equal weight\)/);
      assert.match(membership, /Weekly ratio rescaled — Same quantity as another member \(Weekly price ratio\)/);
      assert.match(await text(site.page, ".method-points"), /percentile rank/);
      assert.match(await text(site.page, "#signal-table-count"), /^11 signals · Average of 11 shown: \d+$/);
      // An outage in a signal's history stays empty on the timeline; the
      // score from before it is never painted across the gap.
      const outage = await site.page.evaluate(() => {
        const labels = [...document.querySelectorAll("#signal-page-heatmap .heatmap-label")];
        const label = labels.find((node) => node.textContent === "Metric with an outage");
        const cells = [];
        for (let node = label.nextElementSibling; node && node.classList.contains("heatmap-cell"); node = node.nextElementSibling) {
          cells.push({ title: node.title, scored: /phase-/.test(node.className) });
        }
        return cells;
      });
      const october = outage.filter((cell) => / · Oct \d+, 2024 · /.test(cell.title));
      assert.ok(october.length >= 10, "the timeline has columns inside the outage");
      assert.ok(october.every((cell) => !cell.scored && / · No data$/.test(cell.title)), "outage columns are unavailable");
      assert.ok(outage.filter((cell) => / · (Aug|Dec) \d+, 2024 · /.test(cell.title)).every((cell) => cell.scored));
      const young = site.page.locator('tr[data-signal-id="young"] .signal-delta');
      assert.deepEqual(await young.allInnerTexts(), ["+6", "-40", "—", "—"]);
      assert.equal(await site.page.locator('tr[data-signal-id="lagging"] .stale-flag').count(), 1);
      assert.match(await site.page.locator("#signal-page-heatmap .heatmap-label").first().innerText(), /Cycle Index/);

      await site.page.selectOption("#signal-category-filter", "Mining");
      assert.match(await text(site.page, "#signal-table-count"), /^2 signals · Average of 2 shown: 40$/);
      assert.match(await text(site.page, "#signal-summary"), headline, "a filter never changes the headline index");
      assert.match(await text(site.page, "#cycle-spectrum"), new RegExp(`INDEX ${index}`));
      const overflow = await site.page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(overflow <= 1, `signals page must not scroll sideways at ${width}px (overflow ${overflow})`);
      assert.deepEqual(site.errors, []);
      await site.context.close();
    }

    // Dashboard shows the same index and separates publication from data date.
    const dashboard = await open(browser);
    await dashboard.visit("/", "#metric-ribbon .metric-phase");
    assert.deepEqual(dashboard.chartRequests(), []);
    const ribbon = await text(dashboard.page, "#metric-ribbon");
    assert.match(ribbon, new RegExp(`CYCLE INDEX\\s+${index}\\s*Bottom`, "i"));
    assert.match(ribbon, /\$58,535/);
    assert.match(await text(dashboard.page, "#dashboard-updated"), /^Published Jan 2, 2025, 00:05 UTC · Data through Dec 17, 2024 · 2 signals stale · 3 signals unavailable$/);
    await dashboard.page.waitForSelector("#dashboard-signal-heatmap .heatmap-label");
    assert.deepEqual((await dashboard.page.locator("#dashboard-signal-heatmap .heatmap-label").allInnerTexts()).slice(0, 2), ["Cycle Index", "Plain daily metric"]);
    assert.deepEqual(dashboard.errors, []);
    await dashboard.context.close();

    // Without the artifact the pages score chart payloads and agree with it.
    const fallback = await open(browser, { artifact: false });
    await fallback.visit("/signals/", "#signal-table-body tr[data-signal-id]");
    assert.ok(fallback.chartRequests().length >= 8, "the fallback reads chart payloads");
    assert.equal(fallback.requests.filter((item) => item.endsWith("/signals.json")).length, 0, "a manifest that records no artifact causes no request for one");
    assert.equal(await text(fallback.page, "#signal-method-version"), "Method v2 · computed in this browser");
    assert.match(await text(fallback.page, "#signal-summary"), headline);
    assert.match(await text(fallback.page, "#signals-freshness"), /Data through Dec 17, 2024 · 2 signals stale: .+ · 3 signals unavailable/);
    assert.deepEqual(fallback.errors, []);
    await fallback.context.close();

    // Alerts: explicit notices, readable preview, and firing from any page.
    const alerts = await open(browser);
    await alerts.visit("/alerts/?chart=hodl-waves", "#alert-signal option[value='plain']");
    assert.deepEqual(alerts.chartRequests(), []);
    assert.equal(await alerts.page.locator("#alert-signal").inputValue(), "", "an unsupported chart never preselects another signal");
    assert.match(await text(alerts.page, "#alert-request-notice"), /HODL Waves does not have a cycle score/);
    assert.equal(await text(alerts.page, "#alert-preview"), "Choose a signal to preview this rule.");
    assert.equal(await alerts.page.locator("#alert-signal option:disabled").count(), 3);
    await alerts.page.click("#alert-form button[type=submit]");
    assert.equal(await alerts.page.locator(".alert-rule").count(), 0, "the form cannot be saved without a signal");

    await alerts.visit("/alerts/?signal=renamed", "#alert-signal option[value='plain']");
    assert.match(await text(alerts.page, "#alert-request-notice"), /Renamed upstream series is unavailable in the latest data/);
    assert.equal(await alerts.page.locator("#alert-signal").inputValue(), "");

    await alerts.visit("/alerts/?signal=lagging", "#alert-signal option[value='plain']");
    assert.equal(await alerts.page.locator("#alert-request-notice").isHidden(), true);
    assert.equal(await alerts.page.locator("#alert-signal").inputValue(), "lagging");
    await alerts.page.fill("#alert-threshold", "50");
    assert.match(await text(alerts.page, "#alert-preview"), /Lagging metric is currently 66 \(Bullish\)\. This rule will trigger when its cycle score is above 50\. Rules are checked when you open the site\./);
    await alerts.page.selectOption("#alert-cadence", "once");
    await alerts.page.click("#alert-form button[type=submit]");
    const fired = alerts.page.locator(".alert-rule");
    assert.equal(await fired.count(), 1);
    assert.match(await fired.getAttribute("class"), /triggered/, "a one-shot alert that just fired keeps its triggered styling");
    assert.match(await fired.innerText(), /Score is above 50 · now 66 · Completed/);
    assert.equal(await alerts.page.locator("#alert-signal").inputValue(), "lagging", "the requested signal stays selected after saving");
    // That firing was displayed here, so another page must not count it as unseen.
    await alerts.visit("/signals/", "#signal-table-body tr[data-signal-id]");
    await alerts.page.waitForTimeout(150);
    assert.equal(await alerts.page.locator(".terminal-nav .nav-badge").count(), 0, "a firing already shown on Alerts is not re-announced");
    assert.deepEqual(alerts.errors, []);
    await alerts.context.close();

    // A crossing recorded while browsing another page is counted on the nav.
    const rule = { id: "r1", signalId: "lagging", operator: "crosses-above", threshold: 50, cadence: "refresh", enabled: true, lastScore: 20, methodVersion: 2 };
    const legacy = { id: "r2", signalId: "plain", operator: "below", threshold: 50, cadence: "once", enabled: true, lastScore: 80 };
    const visitor = await open(browser, { storage: { "fintech-alerts-v1": JSON.stringify([rule, legacy]) } });
    await visitor.visit("/signals/", ".terminal-nav .nav-badge");
    assert.equal(await text(visitor.page, ".terminal-nav .nav-badge"), "1");
    assert.match(await visitor.page.locator('.terminal-nav a[href$="alerts/"]').getAttribute("title"), /1 alert fired since you last opened Alerts · checked when you open the site/);
    await visitor.visit("/alerts/", ".alert-rule");
    const rows = visitor.page.locator(".alert-rule");
    assert.match(await rows.nth(0).getAttribute("class"), /triggered/);
    assert.equal(await rows.nth(0).locator(".alert-rule-status").getAttribute("title"), "Triggered since your last visit");
    assert.match(await rows.nth(1).innerText(), /re-baselined for scoring method v2; review this threshold/);
    const stored = await visitor.page.evaluate(() => JSON.parse(localStorage.getItem("fintech-alerts-v1")));
    assert.equal(stored[1].triggeredAt, undefined, "a legacy observation is re-baselined, not fired");
    assert.equal(stored[1].methodVersion, 2);
    await visitor.visit("/signals/", "#signal-table-body tr[data-signal-id]");
    await visitor.page.waitForTimeout(100);
    assert.equal(await visitor.page.locator(".terminal-nav .nav-badge").count(), 0, "the count clears after Alerts was opened");
    assert.deepEqual(visitor.errors, []);
    await visitor.context.close();

    console.log("PASS: signals artifact, canonical index, freshness, fallback, alert notices and nav badge at 1280/390");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });

function page_rows(page) {
  return page.locator("#signal-table-body tr[data-signal-id]").count();
}
