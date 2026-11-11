const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");
const { serveTerminal, openTerminal } = require("./terminal-fixture.cjs");

// The terminal fixture publishes weekly observations, like the imported charts.
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 860 } });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await serveTerminal(page);
      await openTerminal(page, "?chart=price&range=1m");
      const state = await page.evaluate(() => {
        const label = document.querySelector("#chart-resolution");
        const button = (range) => document.querySelector(`[data-range="${range}"]`);
        const labelBox = label.getBoundingClientRect();
        const bar = document.querySelector(".chart-rangebar").getBoundingClientRect();
        return {
          label: label.textContent,
          labelVisible: !label.hidden && labelBox.width > 0 && labelBox.right <= bar.right + 1 && labelBox.left >= bar.left - 1,
          oneMonthDisabled: button("1m").disabled,
          oneMonthAria: button("1m").getAttribute("aria-disabled"),
          threeMonthDisabled: button("3m").disabled,
          range: new URL(location.href).searchParams.get("range"),
          pressed: [...document.querySelectorAll("[data-range][aria-pressed=true]")].map((node) => node.dataset.range),
          overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        };
      });
      if (process.env.RESOLUTION_SCREENSHOTS) {
        await page.locator(".chart-rangebar").screenshot({ path: path.join(process.env.RESOLUTION_SCREENSHOTS, `rangebar-${width}.png`) });
      }
      assert.equal(state.label, "Weekly data", `${width}px: weekly charts are labelled`);
      assert.ok(state.labelVisible, `${width}px: the label sits inside the range bar`);
      assert.equal(state.oneMonthDisabled, true, `${width}px: 1M is disabled on weekly data`);
      assert.equal(state.oneMonthAria, "true");
      assert.equal(state.threeMonthDisabled, false);
      assert.equal(state.range, "3m", `${width}px: a shared 1M link opens three months`);
      assert.deepEqual(state.pressed, ["3m"]);
      assert.equal(state.overflow, false, `${width}px: no horizontal page scroll`);
      // Clicking the disabled button does nothing.
      await page.locator('[data-range="1m"]').click({ force: true });
      assert.equal(await page.evaluate(() => new URL(location.href).searchParams.get("range")), "3m");
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log("PASS: weekly charts show a resolution label, disable 1M with a reason, and open shared 1M links at 3M at 1280/390.");
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
