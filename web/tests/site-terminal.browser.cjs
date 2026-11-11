const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");
const { serveTerminal, openTerminal, waitForChart } = require("./terminal-fixture.cjs");

const DAY = 86_400_000;
const params = (page) => Object.fromEntries(new URL(page.url()).searchParams);
const pressed = (page, selector) => page.locator(selector).getAttribute("aria-pressed");
const xSpanDays = (page) => page.locator("#terminal-plot").evaluate((plot) => {
  const [start, end] = plot._fullLayout.xaxis.range.map((value) => new Date(value).getTime());
  return (end - start) / 86_400_000;
});
const statusText = (page) => page.locator("#terminal-status").textContent();
const waitStatus = (page, pattern) => page.waitForFunction((source) => new RegExp(source).test(document.querySelector("#terminal-status")?.textContent || ""), pattern.source, { timeout: 5000 });

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("dialog", (dialog) => { errors.push(`dialog: ${dialog.message()}`); dialog.dismiss(); });
    await serveTerminal(page);

    // Shared links restore options after the first render.
    await openTerminal(page, "?chart=price&range=1y&ma=1&grid=0&scale=linear");
    assert.equal(await page.title(), "BTC Price | Fintech Charts");
    assert.equal(await pressed(page, '[data-range="1y"]'), "true");
    assert.equal(await pressed(page, '[data-range="all"]'), "false");
    assert.equal(await pressed(page, '[data-chart-action="moving-average"]'), "true");
    assert.equal(await pressed(page, '[data-chart-action="grid"]'), "false");
    assert.equal(await page.locator('[data-chart-action="grid"]').evaluate((node) => node.classList.contains("active")), false, "Grid is not highlighted while the grid is off");
    assert.equal(await pressed(page, "#scale-toggle"), "false", "linear scale leaves the log toggle unpressed");
    assert.equal(await page.locator("#terminal-plot").evaluate((plot) => plot._fullLayout.yaxis.type), "linear");
    assert(Math.abs(await xSpanDays(page) - 365) < 3, "1Y range is restored");
    assert.equal(await page.locator("#terminal-plot").evaluate((plot) => plot.data.some((trace) => /50 period MA/.test(trace.name))), true);
    assert.equal(await statusText(page), "Showing BTC Price, 1Y range");

    // One polite status line; lists and the chart are not live regions.
    assert.deepEqual(await page.evaluate(() => [...document.querySelectorAll("[aria-live], [role=status]")].map((node) => node.id)), ["terminal-status"]);
    assert.equal(await page.locator(".sidebar-chart-link .pin-mark[aria-label]").count(), 0);
    assert.equal(await page.getByRole("link", { name: "BTC Drawdown From ATH", exact: true }).count(), 1, "sidebar links keep their chart title as the accessible name");

    // Selecting a chart pushes history; option changes replace it.
    const startLength = await page.evaluate(() => history.length);
    await page.locator('#all-chart-list [data-chart-id="drawdown"]').click();
    await waitForChart(page, "drawdown");
    assert.deepEqual(params(page), { chart: "drawdown", grid: "0" }, "a new chart starts from its defaults; the grid preference carries over");
    assert.equal(await page.title(), "BTC Drawdown From ATH | Fintech Charts");
    assert.equal(await page.evaluate(() => history.length), startLength + 1);
    assert.match(await page.locator("#performance-list").textContent(), /pp/, "drawdown changes are percentage points");
    assert.match(await page.locator("#series-list").textContent(), /-?\d+(\.\d)?%/);
    await page.locator('[data-range="4y"]').click();
    await page.waitForTimeout(500);
    assert.equal(params(page).range, "4y");
    assert.equal(await page.evaluate(() => history.length), startLength + 1, "range changes replace the current entry");
    await page.locator('[data-chart-action="halvings"]').click();
    assert.equal(params(page).halvings, "1");
    assert.equal(await pressed(page, '[data-chart-action="halvings"]'), "true");
    await page.locator('[data-chart-action="halvings"]').click();
    assert.equal(params(page).halvings, undefined, "the default halvings state is not written to the URL");

    await page.goBack();
    await waitForChart(page, "price");
    assert.deepEqual(params(page), { chart: "price", range: "1y", scale: "linear", ma: "1", grid: "0" });
    assert.equal(await page.title(), "BTC Price | Fintech Charts");
    assert.equal(await pressed(page, '[data-chart-action="moving-average"]'), "true");
    assert(Math.abs(await xSpanDays(page) - 365) < 3, "Back restores the previous chart's range");
    await page.goForward();
    await waitForChart(page, "drawdown");
    assert.equal(params(page).range, "4y");
    assert.equal(await pressed(page, '[data-range="4y"]'), "true");
    assert(Math.abs(await xSpanDays(page) - 4 * 365.25) < 4);

    // Drag zoom records from/to on release and clears the shortcut state.
    const plot = page.locator("#terminal-plot");
    const box = await plot.boundingBox();
    const size = await plot.evaluate((node) => node._fullLayout._size);
    const y = box.y + size.t + size.h / 2;
    await page.mouse.move(box.x + size.l + size.w * 0.3, y);
    await page.mouse.down();
    await page.mouse.move(box.x + size.l + size.w * 0.6, y, { steps: 6 });
    assert.equal(params(page).from, undefined, "the URL changes on release, not on every pointer move");
    await page.mouse.up();
    await page.waitForFunction(() => new URL(location.href).searchParams.has("from"));
    await page.waitForTimeout(400);
    const zoomed = params(page);
    assert.match(zoomed.from, /^\d{4}-\d{2}-\d{2}$/);
    assert.match(zoomed.to, /^\d{4}-\d{2}-\d{2}$/);
    assert.equal(zoomed.range, undefined);
    assert.equal(await page.locator('[data-range][aria-pressed="true"]').count(), 0);
    await waitStatus(page, / to /);
    const zoomedSpan = (new Date(zoomed.to) - new Date(zoomed.from)) / DAY + 1;
    await page.reload();
    await waitForChart(page, "drawdown");
    assert.deepEqual([params(page).from, params(page).to], [zoomed.from, zoomed.to]);
    assert(Math.abs(await xSpanDays(page) - zoomedSpan) < 1.5, "reload restores the dragged window");

    // Sheet follows the visible window and downloads it as CSV.
    await page.locator('[data-chart-action="table"]').click();
    assert.equal(params(page).view, "sheet");
    assert.equal(await pressed(page, '[data-chart-action="table"]'), "true");
    assert(await page.locator("#data-sheet").isVisible());
    const sheetRows = await page.locator("#data-sheet tbody tr").count();
    const expectedRows = await page.evaluate(({ from, to }) => appState.currentPayload.series[0].x.filter((date) => date >= from && date <= to).length, zoomed);
    assert.equal(sheetRows, expectedRows);
    assert.match(await page.locator(".data-sheet-summary").textContent(), /in the visible range/);
    const [download] = await Promise.all([page.waitForEvent("download"), page.locator('[data-sheet-action="csv"]').click()]);
    const csv = fs.readFileSync(await download.path(), "utf8").trim().split(/\r\n/);
    assert.equal(csv[0], "Date,Drawdown");
    assert.equal(csv.length, expectedRows + 1);
    assert.match(download.suggestedFilename(), /^drawdown-\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.csv$/);
    await page.reload();
    await waitForChart(page, "drawdown");
    assert(await page.locator("#data-sheet").isVisible(), "view=sheet is restored");
    await page.locator('[data-chart-action="table"]').click();

    // Copy link writes the canonical URL (fallback without the async
    // Clipboard API, as on this non-secure test origin, then the API itself).
    assert.equal(await page.evaluate(() => Boolean(navigator.clipboard)), false);
    await page.locator('[data-chart-action="copy-link"]').click();
    await waitStatus(page, /Link to this chart view copied/);
    assert.equal(await page.locator('[data-chart-action="copy-link"]').textContent(), "✓ Copied");
    await page.evaluate(() => {
      Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async (text) => { window.copiedLink = text; } } });
      document.querySelector("#terminal-status").textContent = "";
    });
    await page.locator('[data-chart-action="copy-link"]').click();
    await waitStatus(page, /Link to this chart view copied/);
    assert.equal(await page.evaluate(() => window.copiedLink), page.url());

    // Unknown chart ids are reported instead of silently replaced.
    await openTerminal(page, "?chart=no-such-chart");
    assert(await page.locator("#chart-notice").isVisible());
    assert.match(await page.locator("#chart-notice").textContent(), /“no-such-chart” isn’t in the library\. Showing PlanB Composite instead\./);
    assert.equal(params(page).chart, "pb-various");

    // Search ranking, boilerplate exclusion, and keyboard control.
    const search = page.locator("#sidebar-search");
    await search.fill("score z mvrv");
    assert.deepEqual(await page.locator("#all-chart-list .sidebar-chart-link > span:first-child").allTextContents(), ["MVRV Z-Score"]);
    await waitStatus(page, /^1 chart matches “score z mvrv”$/);
    await search.fill("refreshed");
    assert.equal(await page.locator("#all-count").textContent(), "0", "shared import boilerplate is not searchable");
    await search.fill("mvrv");
    assert.equal(await page.locator("#all-heading").textContent(), "Best matches");
    const links = page.locator("#library-results .sidebar-chart-link");
    await search.press("ArrowDown");
    assert.equal(await links.nth(0).evaluate((node) => node === document.activeElement), true);
    await page.keyboard.press("ArrowDown");
    assert.equal(await links.nth(1).evaluate((node) => node === document.activeElement), true);
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("ArrowUp");
    assert.equal(await search.evaluate((node) => node === document.activeElement), true);
    await search.press("Escape");
    assert.equal(await search.inputValue(), "");
    await search.fill("sth");
    await search.press("Enter");
    await waitForChart(page, "sth-mvrv");
    assert.equal(await page.title(), "MVRV Short Term Supply | Fintech Charts");
    await search.fill("");

    // Section chips filter with counts and are reflected in the URL.
    const onchain = page.locator('#section-filters [data-section="onchain"]');
    assert.equal((await onchain.textContent()).replace(/\s+/g, " ").trim(), "On-Chain 5");
    await onchain.click();
    assert.equal(await pressed(page, '#section-filters [data-section="onchain"]'), "true");
    assert.equal(params(page).section, "onchain");
    assert.equal(await page.locator("#all-count").textContent(), "5");
    await waitStatus(page, /^5 On-Chain charts match$/);
    await search.fill("sharpe");
    assert.match(await page.locator("#all-chart-list").textContent(), /No On-Chain charts match\. 1 match is in other sections; choose All to see it\./);
    await waitStatus(page, /^No On-Chain charts match “sharpe”; 1 in other sections$/);
    await search.fill("");
    assert.equal(await page.locator("#related-heading").textContent(), "More in On-Chain");
    assert.equal(await page.locator("#related-list .related-chart-link").count(), 4);
    await page.locator('#related-list [data-chart-id="nupl"]').click();
    await waitForChart(page, "nupl");
    assert.equal(params(page).section, "onchain", "the section filter survives chart changes");
    await page.locator('#section-filters [data-section=""]').click();
    assert.equal(params(page).section, undefined);

    // Upstream colours cannot inject attributes into the detail panel.
    await openTerminal(page, "?chart=colour-check");
    assert.equal(await page.evaluate(() => document.querySelectorAll("[onmouseover], [data-x]").length), 0);
    await page.locator(".series-dot").first().hover();
    assert.equal(await page.evaluate(() => window.injected), undefined);
    assert.equal(await page.locator(".series-dot").first().evaluate((node) => node.style.background), "rgb(200, 95, 60)");

    // Projection charts read "latest" at the observed end.
    await openTerminal(page, "?chart=projection");
    assert.equal(await page.locator("#series-date").textContent(), "Oct 25, 26");
    assert.match(await page.locator("#chart-readout").textContent(), /^Latest · Oct 25, 2026/);

    // Keyboard stepping updates the readout without moving the range.
    await openTerminal(page, "?chart=price&range=1y");
    const before = await page.locator("#terminal-plot").evaluate((node) => node._fullLayout.xaxis.range.slice());
    await page.locator("#terminal-plot").focus();
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowLeft");
    assert.match(await page.locator("#chart-readout").textContent(), /^Oct 11, 2026BTC price \$[\d,]+/);
    await waitStatus(page, /^Oct 11, 2026: BTC price \$/);
    await page.keyboard.press("ArrowRight");
    assert.match(await page.locator("#chart-readout").textContent(), /^Oct 18, 2026/);
    await page.keyboard.press("Home");
    const first = await page.locator("#chart-readout").textContent();
    assert.match(first, /2025/, "Home jumps to the first visible observation");
    assert.deepEqual(await page.locator("#terminal-plot").evaluate((node) => node._fullLayout.xaxis.range.slice()), before);
    await page.keyboard.press("-");
    await page.waitForTimeout(500);
    assert(await xSpanDays(page) > 400, "existing - zoom shortcut still works");

    // Responsive checks: one exposed h1 and no horizontal page overflow.
    for (const width of [390, 768, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await page.waitForTimeout(200);
      const layout = await page.evaluate(() => ({
        h1: [...document.querySelectorAll("h1")].filter((node) => node.checkVisibility()).map((node) => node.id),
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        copy: document.querySelector('[data-chart-action="copy-link"]').checkVisibility(),
      }));
      assert.equal(layout.h1.length, 1, `exactly one visible h1 at ${width}px`);
      assert.equal(layout.h1[0], width <= 820 ? "chart-mobile-title" : "chart-title");
      assert(layout.overflow <= 0, `no horizontal overflow at ${width}px`);
      assert(layout.copy, `Copy link is reachable at ${width}px`);
    }

    assert.deepEqual(errors, []);
    console.log("PASS: terminal URL restore, push/replace history, Back/Forward, drag-zoom from/to, sheet + CSV, copy link, unknown-chart notice, search ranking/keyboard, section chips, safe colours, observed-end latest, keyboard readout, and one h1 per breakpoint.");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
