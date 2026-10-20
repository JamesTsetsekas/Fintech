const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

// Exercises the same renderer as both the dashboard and chart terminal, with
// sparse dates so hovering between candles is covered as well as on a candle.
const payload = {
  x_value_type: 'date',
  series: [{
    name: 'BTC OHLC',
    type: 'candlestick',
    x: ['2024-01-01', '2024-01-02', '2024-04-01', '2024-07-01', '2024-10-01'],
    open: [90, 100, 200, 300, 400],
    high: [110, 120, 240, 360, 480],
    low: [80, 90, 180, 270, 360],
    close: [100, 110, 220, 330, 440],
    increasing: { line: { color: '#16844d' } },
    decreasing: { line: { color: '#c91f50' } },
  }],
  layout: { xaxis: { type: 'date', rangeslider: { visible: false } } },
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1000, height: 650 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<div id="plot" style="width:900px;height:500px"></div>');
    await page.addScriptTag({ url: 'https://cdn.plot.ly/plotly-2.35.2.min.js' });
    await page.addScriptTag({ path: path.resolve(__dirname, '../assets/site.js') });
    const plot = page.locator('#plot');
    for (const compact of [true, false]) {
      for (const scale of ['log', 'linear']) {
        await page.evaluate(({ payload, compact, scale }) => {
          payload.layout.yaxis = { type: scale };
          return renderPlot(document.querySelector('#plot'), payload, { compact });
        }, { payload, compact, scale });
        const bounds = await plot.boundingBox();
        const size = await plot.evaluate(target => target._fullLayout._size);
        const observations = [];
        for (const date of ['2024-01-20', '2024-04-20', '2024-07-20']) {
          const plotX = await plot.evaluate((target, date) => target._fullLayout.xaxis.d2p(date), date);
          await page.mouse.move(bounds.x + size.l + plotX, bounds.y + size.t + size.h * 0.4);
          await page.waitForTimeout(100);
          observations.push(await plot.locator('.hoverlayer').textContent());
        }
        assert(observations.every(text => ['open', 'high', 'low', 'close'].every(label => text.toLowerCase().includes(label))), `all OHLC fields appear: compact=${compact}, scale=${scale}`);
        assert.equal(new Set(observations).size, 3, `OHLC date and values follow horizontal movement: compact=${compact}, scale=${scale}`);
        assert(observations[0].includes('Open: $100') && observations[1].includes('Open: $200') && observations[2].includes('Open: $300'), 'hover values belong to the nearest candle');
        await page.mouse.move(990, 640);
        await page.waitForTimeout(100);
        assert.equal(await plot.locator('.hoverlayer').textContent(), '', 'tooltip clears when the mouse leaves');
      }
    }
    assert.deepEqual(errors, [], 'no uncaught browser errors');
    console.log('PASS: OHLC hover changes date and values across dashboard/terminal and log/linear scales.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
