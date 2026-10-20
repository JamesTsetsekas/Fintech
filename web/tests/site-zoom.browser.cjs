const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

const dates = Array.from({length: 80}, (_, i) => new Date(Date.UTC(2024, 0, i + 1)).toISOString().slice(0, 10));
const payload = {
  title: 'Zoom regression', x_value_type: 'date',
  series: [{type: 'scatter', mode: 'lines', name: 'BTC price', source_key: 'price', x: dates, y: dates.map((_, i) => 1000 + i * 100)}],
  layout: {xaxis: {type: 'date'}, yaxis: {type: 'log', range: [0, 5]}},
};

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 700}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<div id="plot" style="position:relative;width:950px;height:500px"></div>');
    await page.addStyleTag({path: path.resolve(__dirname, '../assets/site.css')});
    await page.addScriptTag({url: 'https://cdn.plot.ly/plotly-2.35.2.min.js'});
    await page.addScriptTag({path: path.resolve(__dirname, '../assets/site.js')});
    for (const compact of [true, false]) {
      await page.evaluate(({payload, compact}) => renderPlot(document.querySelector('#plot'), payload, {compact}), {payload, compact});
      const plot = page.locator('#plot');
      const box = await plot.boundingBox();
      const size = await plot.evaluate(p => p._fullLayout._size);
      const start = {x: box.x + size.l + size.w * .3, y: box.y + size.t + size.h * .4};
      const end = {x: box.x + size.l + size.w * .65, y: box.y + size.t + size.h * .65};
      await page.mouse.move(start.x, start.y);
      await page.mouse.down();
      await page.mouse.move(end.x, end.y, {steps: 8});
      const selection = await plot.locator('.chart-zoom-selection').count();
      await page.evaluate(() => {
        window.zoomSamples = [];
        const started = performance.now();
        function sample() {
          const p = document.querySelector('#plot');
          window.zoomSamples.push({time: performance.now() - started, x: p._fullLayout.xaxis.range.slice(), y: p._fullLayout.yaxis.range.slice()});
          if (performance.now() - started < 600) requestAnimationFrame(sample);
        }
        requestAnimationFrame(sample);
      });
      await page.mouse.up();
      await page.waitForTimeout(650);
      const state = await plot.evaluate(p => ({x: p._fullLayout.xaxis.range, y: p._fullLayout.yaxis.range, samples: window.zoomSamples}));
      console.log(JSON.stringify({compact, selection, y: state.y, frames: new Set(state.samples.map(s => JSON.stringify(s.x))).size}));
      assert(state.y[0] > 3 && state.y[1] < 4, 'Y axis fits the visible price window instead of the drawn rectangle');
      assert.equal(selection, 1, 'drag shows the full-height time selection');
      assert(new Set(state.samples.map(s => JSON.stringify(s.x))).size >= 3, 'zoom passes through intermediate ranges');
      const badgeCount = await plot.locator('.chart-axis-badge').count();
      assert.equal(badgeCount, 2, 'dashboard and terminal both have moving axis labels');
      await page.mouse.dblclick(box.x + size.l + size.w * .5, box.y + size.t + size.h * .5);
      await page.waitForTimeout(450);
      const reset = await plot.evaluate(p => p._fullLayout.yaxis.range);
      assert.deepEqual(reset, [0, 5], 'double-click smoothly restores the original scale');
    }
    assert.deepEqual(errors, []);
    console.log('PASS: drag zoom animates, fits visible prices, updates both layouts, and resets.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
