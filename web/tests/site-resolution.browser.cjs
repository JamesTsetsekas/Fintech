const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");
const { serveTerminal, openTerminal } = require("./terminal-fixture.cjs");

// The terminal fixture publishes weekly observations, like the imported charts.
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 860 }, hasTouch: width < 500 });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await serveTerminal(page);
      await openTerminal(page, "?chart=price&range=1m");
      const reason = "1M needs at least 8 weekly points";
      const layout = () => page.evaluate(() => {
        const box = (selector) => {
          const node = document.querySelector(selector);
          const rect = node.getBoundingClientRect();
          return { hidden: node.hidden, text: node.textContent, left: rect.left, right: rect.right, width: rect.width };
        };
        return {
          bar: box(".chart-rangebar"), chip: box("#chart-resolution"), note: box("#chart-range-note"),
          range: new URL(location.href).searchParams.get("range"),
          pressed: [...document.querySelectorAll("[data-range][aria-pressed=true]")].map((node) => node.dataset.range),
          active: document.activeElement?.dataset?.range || null,
          status: document.querySelector("#terminal-status").textContent,
          overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        };
      });
      let state = await layout();
      assert.equal(state.chip.text, "Weekly data", `${width}px: weekly charts are labelled`);
      assert.ok(!state.chip.hidden && state.chip.width > 0 && state.chip.right <= state.bar.right + 1, `${width}px: label sits in the range bar`);
      assert.equal(state.range, "3m", `${width}px: a shared 1M link opens three months`);
      assert.deepEqual(state.pressed, ["3m"]);
      assert.equal(state.overflow, false, `${width}px: no horizontal page scroll`);

      const oneMonth = page.locator('[data-range="1m"]');
      assert.equal(await oneMonth.getAttribute("aria-disabled"), "true");
      assert.equal(await oneMonth.evaluate((node) => node.disabled), false, "unavailable ranges stay in the tab order (no native disabled)");
      // Screen readers get the reason as the button's accessible description.
      const cdp = await page.context().newCDPSession(page);
      const { root } = await cdp.send("DOM.getDocument");
      const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: '[data-range="1m"]' });
      const { nodes } = await cdp.send("Accessibility.getPartialAXTree", { nodeId, fetchRelatives: false });
      const axButton = nodes.find((node) => node.role?.value === "button");
      assert.equal(axButton?.description?.value, reason, `${width}px: accessible description explains the limit`);
      assert.equal(axButton?.properties?.find((item) => item.name === "disabled")?.value?.value, true, "exposed as disabled");

      // Keyboard: Tab to the button; the reason becomes visible while focused.
      await page.locator('[data-range="3m"]').focus();
      await page.keyboard.press("Shift+Tab");
      state = await layout();
      assert.equal(state.active, "1m", `${width}px: keyboard focus reaches 1M`);
      assert.ok(!state.note.hidden && state.note.text === reason && state.note.width > 0, `${width}px: focused note is visible`);
      assert.ok(state.note.left >= state.bar.left - 1 && state.note.right <= state.bar.right + 1, `${width}px: note fits the range bar`);
      assert.equal(state.chip.hidden, true, "the note takes the label's place");
      assert.equal(state.overflow, false, `${width}px: note causes no horizontal scroll`);
      // Activation (Enter, Space, click or tap) does nothing but explain.
      for (const activate of [() => page.keyboard.press("Enter"), () => page.keyboard.press("Space"),
        () => (width < 500 ? oneMonth.tap({ force: true }) : oneMonth.click({ force: true }))]) {
        await activate();
        state = await layout();
        assert.equal(state.range, "3m", `${width}px: activation keeps the current range`);
        assert.deepEqual(state.pressed, ["3m"]);
        assert.equal(state.status, reason, `${width}px: activation announces the reason`);
        assert.equal(state.note.hidden, false);
      }
      // Leaving the button restores the label.
      await page.locator('[data-range="3m"]').focus();
      state = await layout();
      assert.equal(state.note.hidden, true);
      assert.equal(state.chip.hidden, false);
      if (process.env.RESOLUTION_SCREENSHOTS) {
        await oneMonth.focus();
        await page.locator(".chart-rangebar").screenshot({ path: path.join(process.env.RESOLUTION_SCREENSHOTS, `rangebar-note-${width}.png`) });
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log("PASS: weekly charts show a resolution label; 1M stays focusable with an accessible, visible reason; activation never zooms; shared 1M links open 3M at 1280/390.");
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
