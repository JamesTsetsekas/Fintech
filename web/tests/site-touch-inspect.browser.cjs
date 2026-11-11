const assert = require("node:assert/strict");
const { chromium } = require("playwright");
const { serveTerminal, openTerminal } = require("./terminal-fixture.cjs");

// Emulated touch only: this cannot prove real-device gesture feel, but it
// checks the coarse-pointer controls and that a scrub reads values without
// changing the visible range.
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await serveTerminal(page);
    await openTerminal(page, "?chart=price&range=4y");
    assert.equal(await page.evaluate(() => matchMedia("(pointer: coarse)").matches), true, "emulated device reports a coarse pointer");
    assert(await page.locator("#chart-touch-mode").isVisible(), "Inspect/Zoom toggle is shown on touch screens");
    assert.equal(await page.locator('[data-touch-mode="inspect"]').getAttribute("aria-pressed"), "true", "touch defaults to inspect");
    const plot = page.locator("#terminal-plot");
    assert.equal(await plot.evaluate((node) => node._fullLayout.dragmode), false, "a one-finger drag does not draw a zoom box");
    await plot.scrollIntoViewIfNeeded();
    const range = () => plot.evaluate((node) => node._fullLayout.xaxis.range.slice());
    const before = await range();
    const geometry = await plot.evaluate((node) => {
      const bounds = node.getBoundingClientRect();
      const { _size: size } = node._fullLayout;
      return { left: bounds.left + size.l, width: size.w, y: bounds.top + size.t + size.h / 2 };
    });
    const readout = () => page.locator("#chart-readout").textContent();
    assert.match(await readout(), /^Latest · /);

    const cdp = await context.newCDPSession(page);
    const touch = (type, x) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: type === "touchEnd" ? [] : [{ x, y: geometry.y, id: 1 }] });
    const x1 = geometry.left + geometry.width * 0.25;
    const x2 = geometry.left + geometry.width * 0.75;
    await touch("touchStart", x1);
    await touch("touchMove", x1 + 2);
    await page.waitForTimeout(60);
    const first = await readout();
    for (let step = 1; step <= 6; step += 1) await touch("touchMove", x1 + ((x2 - x1) * step) / 6);
    await page.waitForTimeout(60);
    const second = await readout();
    await touch("touchEnd");
    await page.waitForTimeout(300);
    assert.doesNotMatch(first, /^Latest/);
    assert.notEqual(first, second, "two touch positions produce different readouts");
    assert.match(second, /BTC price \$[\d,]+/);
    assert.deepEqual(await range(), before, "scrubbing never changes the visible range");
    assert.equal(params(page).from, undefined);
    assert.equal(await readout(), second, "the readout stays pinned after lifting the finger");
    const readoutBox = await page.locator(".chart-readout-bar").boundingBox();
    assert(readoutBox.y + readoutBox.height <= geometry.y, "the readout sits above the touched plot area");

    await page.locator('[data-touch-mode="zoom"]').tap();
    assert.equal(await page.locator('[data-touch-mode="zoom"]').getAttribute("aria-pressed"), "true");
    assert.equal(await plot.evaluate((node) => node._fullLayout.dragmode), "zoom");
    await page.locator('[data-touch-mode="inspect"]').tap();
    assert.equal(await plot.evaluate((node) => node._fullLayout.dragmode), false);

    const desktop = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const desktopPage = await desktop.newPage();
    await serveTerminal(desktopPage);
    await openTerminal(desktopPage, "?chart=price");
    assert.equal(await desktopPage.locator("#chart-touch-mode").isVisible(), false, "fine pointers keep drag-to-zoom without the toggle");
    assert.equal(await desktopPage.locator("#terminal-plot").evaluate((node) => node._fullLayout.dragmode), "zoom");
    await desktop.close();
    assert.deepEqual(errors, []);
    console.log("PASS: touch inspect is the coarse-pointer default, scrubbing updates a fixed readout without zooming, and Zoom mode restores the drag box.");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });

function params(page) {
  return Object.fromEntries(new URL(page.url()).searchParams);
}
