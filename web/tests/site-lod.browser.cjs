const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

const DAY = 86400000;
const iso = time => new Date(time).toISOString().slice(0, 10);
const dates = (count, start, step = DAY) => Array.from({length: count}, (_, i) => iso(start + i * step));
function walk(count, seed) {
  let state = seed;
  let value = 1000;
  return Array.from({length: count}, () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    value *= 1 + ((state / 2147483648) - 0.5) * 0.04;
    return Number(value.toFixed(2));
  });
}

// 6,245 daily observations (the size of the native price charts) with a
// one-day spike that stride decimation would skip.
const dailyX = dates(6245, Date.UTC(2009, 9, 6));
const dailyY = walk(6245, 11);
const spikeIndex = 6245 - 120;
dailyY[spikeIndex] = Math.max(...dailyY) * 3;
const daily = {
  title: 'LOD daily', x_value_type: 'date',
  series: [
    {type: 'scatter', mode: 'lines', name: 'BTC price', source_key: 'price', x: dailyX, y: dailyY, line: {color: '#2863a7'}},
    {type: 'scatter', mode: 'lines', name: 'Model', x: dailyX, y: walk(6245, 5), line: {color: '#c85f3c'}},
  ],
  layout: {xaxis: {type: 'date'}, yaxis: {type: 'linear'}},
};
// 800 weekly candles, like the imported OHLC chart once its partial week is gone.
const weeklyX = dates(800, Date.UTC(2011, 5, 5), 7 * DAY);
const weeklyOpen = walk(800, 3);
const weeklyClose = walk(800, 9);
const weekly = {
  title: 'LOD weekly OHLC', x_value_type: 'date',
  series: [{
    type: 'candlestick', name: 'BTC OHLC', source_key: 'ohlc', x: weeklyX, open: weeklyOpen, close: weeklyClose,
    high: weeklyOpen.map((v, i) => Math.max(v, weeklyClose[i]) * 1.03), low: weeklyOpen.map((v, i) => Math.min(v, weeklyClose[i]) * 0.97),
  }],
  layout: {xaxis: {type: 'date'}, yaxis: {type: 'linear'}},
};
// Largest native payload shape: 9,495 points across five lines.
const largeX = dates(9495, Date.UTC(2009, 0, 3));
const large = {
  title: 'LOD large', x_value_type: 'date',
  series: [1, 2, 3, 4, 5].map(seed => ({type: 'scatter', mode: 'lines', name: `S${seed}`, x: largeX, y: walk(9495, seed)})),
  layout: {xaxis: {type: 'date'}, yaxis: {type: 'log'}},
};

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 700}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'warning' && /detail/i.test(message.text())) errors.push(message.text()); });
    await page.setContent('<div id="plot" style="position:relative;width:950px;height:500px"></div>');
    await page.addStyleTag({path: path.resolve(__dirname, '../assets/site.css')});
    await page.addScriptTag({url: 'https://cdn.plot.ly/plotly-2.35.2.min.js'});
    await page.addScriptTag({path: path.resolve(__dirname, '../assets/site.js')});
    await page.evaluate(() => {
      window.settled = async () => {
        const target = document.querySelector('#plot');
        for (let attempt = 0; attempt < 150; attempt += 1) {
          const lod = target._fintechLod;
          if (lod && !lod.timer && !target._transitioning) {
            await lod.pending;
            if (!lod.timer) return;
          }
          await new Promise(resolve => setTimeout(resolve, 20));
        }
        throw new Error('level of detail never settled');
      };
      window.inRange = (trace) => {
        const target = document.querySelector('#plot');
        const [low, high] = target._fullLayout.xaxis.range.map(value => target._fullLayout.xaxis.r2l(value));
        return trace.x.filter(value => { const time = target._fullLayout.xaxis.r2l(value); return time >= low && time <= high; }).length;
      };
      window.state = () => {
        const target = document.querySelector('#plot');
        const [low, high] = target._fullLayout.xaxis.range.map(value => target._fullLayout.xaxis.r2l(value));
        return {
          range: [low, high],
          y: target._fullLayout.yaxis.range.slice(),
          traces: target.data.map(trace => ({
            type: trace.type || 'scatter', mode: trace.mode, visible: trace.visible, width: trace.line?.width, color: trace.line?.color,
            drawn: trace.x.length, visibleCount: window.inRange(trace), x: trace.x, y: trace.y, high: trace.high,
          })),
          bdPos: (target.calcdata || []).find(c => c[0]?.t?.bdPos !== undefined)?.[0].t.bdPos,
          refreshMs: target._fintechLod?.lastRefreshMs,
        };
      };
    });
    const nativeCount = ([low, high]) => dailyX.filter(value => { const time = Date.parse(value); return time >= low && time <= high; }).length;
    const end = Date.parse(dailyX.at(-1));

    for (const [compact, maxPoints] of [[false, 2200], [true, 600]]) {
      const label = compact ? 'dashboard' : 'terminal';
      await page.evaluate(({payload, compact, maxPoints}) => renderPlot(document.querySelector('#plot'), payload, {compact, maxPoints}), {payload: daily, compact, maxPoints});
      let state = await page.evaluate(() => window.state());
      assert(state.traces.every(t => t.drawn <= maxPoints), `${label}: full view stays within ${maxPoints} points`);
      assert(state.traces[0].y.includes(dailyY[spikeIndex]), `${label}: one-day spike survives the full-history view`);
      assert.equal(state.traces[0].mode, 'lines', `${label}: dense views stay plain lines`);

      // (a) programmatic zoom, as used by range shortcuts and URL restore.
      for (const days of [30, 91, 365]) {
        await page.evaluate(range => document.querySelector('#plot')._fintechNavigation.zoomTo(range, 'shortcut'),
          [new Date(end - days * DAY).toISOString(), new Date(end).toISOString()]);
        await page.evaluate(() => window.settled());
        state = await page.evaluate(() => window.state());
        const expected = nativeCount(state.range);
        assert.equal(state.traces[0].visibleCount, expected, `${label}: ${days}d zoom shows every native point`);
        assert.equal(state.traces[1].visibleCount, expected, `${label}: every series is refined`);
        assert(state.traces.every(t => t.drawn <= maxPoints + 4), `${label}: refined view stays within budget`);
        assert.equal(state.traces[0].mode, days === 30 ? 'lines+markers' : 'lines', `${label}: markers only when sparse`);
        console.log(JSON.stringify({label, zoom: `${days}d`, visible: state.traces[0].visibleCount, drawn: state.traces[0].drawn, refreshMs: Math.round(state.refreshMs)}));
      }

      // (b) mouse drag selection.
      await page.evaluate(() => document.querySelector('#plot')._fintechNavigation.reset());
      await page.evaluate(() => window.settled());
      const box = await page.locator('#plot').boundingBox();
      const size = await page.evaluate(() => document.querySelector('#plot')._fullLayout._size);
      await page.mouse.move(box.x + size.l + size.w * 0.93, box.y + size.t + size.h * 0.5);
      await page.mouse.down();
      await page.mouse.move(box.x + size.l + size.w * 0.97, box.y + size.t + size.h * 0.6, {steps: 6});
      await page.mouse.up();
      await page.waitForTimeout(450);
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      assert(nativeCount(state.range) < maxPoints * 0.7, 'drag window fits the visible budget');
      assert.equal(state.traces[0].visibleCount, nativeCount(state.range), `${label}: drag zoom shows every native point`);

      // (c) native relayout (modebar, touch zoom, other code paths).
      const nativeRange = [iso(end - 140 * DAY), iso(end - 100 * DAY)]; // contains the spike
      await page.evaluate(range => Plotly.relayout(document.querySelector('#plot'), {'xaxis.range': range}), nativeRange);
      await page.waitForTimeout(50);
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      assert.equal(state.traces[0].visibleCount, nativeCount(state.range), `${label}: relayout zoom shows every native point`);
      assert(state.y[1] >= dailyY[spikeIndex], `${label}: y axis refits to the spike drawn at full resolution`);

      // Zoom floor: never fewer than eight native observations.
      await page.evaluate(start => document.querySelector('#plot')._fintechNavigation.zoomTo([new Date(start).toISOString(), new Date(start + 3600000).toISOString()]), end - 400 * DAY);
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      assert(state.range[1] - state.range[0] >= 8 * DAY - 1, `${label}: zoom floor is eight days of daily data`);
      assert(state.traces[0].visibleCount >= 8, `${label}: at least eight observations stay visible`);
      await page.evaluate(range => Plotly.relayout(document.querySelector('#plot'), {'xaxis.range': range}), [iso(end - 300 * DAY), iso(end - 299 * DAY)]);
      await page.waitForTimeout(450);
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      assert(state.range[1] - state.range[0] >= 8 * DAY - 1, `${label}: native relayout also respects the floor`);

      // Attributes changed after the draw (legend toggles, theme restyles) survive refinement.
      await page.evaluate(() => Plotly.restyle(document.querySelector('#plot'), {visible: 'legendonly', 'line.width': 4}, [1]));
      await page.evaluate(range => document.querySelector('#plot')._fintechNavigation.zoomTo(range), [new Date(end - 60 * DAY).toISOString(), new Date(end).toISOString()]);
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      assert.equal(state.traces[1].visible, 'legendonly', `${label}: hidden series stay hidden`);
      assert.equal(state.traces[1].width, 4, `${label}: post-draw restyles are preserved`);
      assert.equal(state.traces[0].color, '#2863a7', `${label}: line colors unchanged`);

      await page.evaluate(() => document.querySelector('#plot')._fintechNavigation.reset());
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      assert.equal(state.traces[0].mode, 'lines', `${label}: reset drops the sparse markers`);
      assert(state.traces[0].drawn <= maxPoints, `${label}: reset returns to the budgeted overview`);
    }

    // Weekly candles: aggregated overview, native candles and width when zoomed.
    for (const [compact, maxPoints] of [[true, 600], [false, 2200]]) {
      const label = compact ? 'dashboard' : 'terminal';
      await page.evaluate(({payload, compact, maxPoints}) => renderPlot(document.querySelector('#plot'), payload, {compact, maxPoints}), {payload: weekly, compact, maxPoints});
      let state = await page.evaluate(() => window.state());
      const candles = state.traces.find(t => t.type === 'candlestick');
      if (compact) {
        assert(candles.drawn < 600 && candles.drawn > 150, 'dashboard overview merges weekly candles into months');
        assert.equal(Math.max(...candles.high), Math.max(...weekly.series[0].high), 'merged candles keep the highest high');
      } else {
        assert.equal(candles.drawn, 800, 'terminal overview keeps every weekly candle');
      }
      const weeklyEnd = Date.parse(weeklyX.at(-1));
      await page.evaluate(range => document.querySelector('#plot')._fintechNavigation.zoomTo(range), [new Date(weeklyEnd - 365 * DAY).toISOString(), new Date(weeklyEnd).toISOString()]);
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      const zoomed = state.traces.find(t => t.type === 'candlestick');
      assert.equal(zoomed.visibleCount, weeklyX.filter(v => Date.parse(v) >= state.range[0] && Date.parse(v) <= state.range[1]).length, `${label}: every weekly candle in view`);
      assert(state.bdPos / DAY >= 1.5, `${label}: weekly candles keep their width (half-width ${(state.bdPos / DAY).toFixed(2)}d)`);
      // A one-month request on weekly data is widened to eight weeks.
      await page.evaluate(range => document.querySelector('#plot')._fintechNavigation.zoomTo(range), [new Date(weeklyEnd - 30 * DAY).toISOString(), new Date(weeklyEnd).toISOString()]);
      await page.evaluate(() => window.settled());
      state = await page.evaluate(() => window.state());
      assert(state.range[1] - state.range[0] >= 56 * DAY - 1, `${label}: weekly zoom floor is eight weeks`);
      console.log(JSON.stringify({label, candles: {overview: candles.drawn, zoomedVisible: zoomed.visibleCount, halfWidthDays: Number((state.bdPos / DAY).toFixed(2))}}));
    }

    // Traces relying on Plotly's default mode lose the sparse markers on reset,
    // and a missing observation stays a visible gap in the drawn line.
    const gapIndex = 6245 - 400;
    const defaultMode = {
      title: 'LOD default mode', x_value_type: 'date',
      series: [{type: 'scatter', name: 'No mode', x: dailyX, y: dailyY.map((value, index) => (index === gapIndex ? null : value))}],
      layout: {xaxis: {type: 'date'}, yaxis: {type: 'linear'}},
    };
    for (const [compact, maxPoints] of [[false, 2200], [true, 600]]) {
      const label = compact ? 'dashboard' : 'terminal';
      await page.evaluate(({payload, compact, maxPoints}) => renderPlot(document.querySelector('#plot'), payload, {compact, maxPoints}), {payload: defaultMode, compact, maxPoints});
      const modes = () => page.evaluate(() => {
        const target = document.querySelector('#plot');
        return {data: target.data[0].mode, resolved: target._fullData[0].mode};
      });
      const before = await modes();
      assert.equal(before.resolved, 'lines', `${label}: dense default-mode trace draws plain lines`);
      const gapDate = dailyX[gapIndex];
      const drawnGap = await page.evaluate(date => { const t = document.querySelector('#plot').data[0]; const i = t.x.indexOf(date); return i >= 0 ? t.y[i] : 'absent'; }, gapDate);
      assert.equal(drawnGap, null, `${label}: overview keeps the missing observation as a gap`);
      await page.evaluate(range => document.querySelector('#plot')._fintechNavigation.zoomTo(range), [new Date(end - 30 * DAY).toISOString(), new Date(end).toISOString()]);
      await page.evaluate(() => window.settled());
      const zoomed = await modes();
      assert.equal(zoomed.resolved, 'lines+markers', `${label}: zoomed sparse view shows markers`);
      await page.evaluate(() => document.querySelector('#plot')._fintechNavigation.reset());
      await page.evaluate(() => window.settled());
      const after = await modes();
      assert.equal(after.resolved, before.resolved, `${label}: reset restores the original mode`);
      assert.equal(after.data, 'lines', `${label}: restored mode is explicit`);
    }

    // Performance on the largest payload shape.
    await page.evaluate(({payload}) => renderPlot(document.querySelector('#plot'), payload, {maxPoints: 2200}), {payload: large});
    const timings = [];
    for (const days of [30, 365, 4 * 365]) {
      const largeEnd = Date.parse(largeX.at(-1));
      await page.evaluate(range => document.querySelector('#plot')._fintechNavigation.zoomTo(range), [new Date(largeEnd - days * DAY).toISOString(), new Date(largeEnd).toISOString()]);
      await page.evaluate(() => window.settled());
      timings.push(Math.round((await page.evaluate(() => window.state())).refreshMs));
    }
    console.log(JSON.stringify({large: '9495 points x 5', refreshMs: timings}));
    assert(timings.every(ms => ms < 1500), 'refinement stays interactive on the largest charts');

    // Request race: a newer render wins over a refinement still pending for the old one.
    await page.evaluate(async ({first, second}) => {
      const target = document.querySelector('#plot');
      await renderPlot(target, first, {maxPoints: 600});
      const end = Date.parse(first.series[0].x.at(-1));
      void target._fintechNavigation.zoomTo([new Date(end - 30 * 86400000).toISOString(), new Date(end).toISOString()]);
      await renderPlot(target, second, {maxPoints: 600});
    }, {first: daily, second: weekly});
    await page.waitForTimeout(500);
    const raced = await page.evaluate(() => ({types: document.querySelector('#plot').data.map(t => t.type), source: document.querySelector('#plot')._fintechLod.source[0].name}));
    assert.equal(raced.source, 'BTC OHLC', 'the newer chart owns the level of detail');
    assert(raced.types.includes('candlestick') && !raced.types.includes(undefined), 'stale refinement never restyles the newer chart');

    assert.deepEqual(errors, []);
    console.log('PASS: zoomed windows show every native point (programmatic, drag, relayout), spikes and candle widths survive, zoom floor holds, restyles persist, and stale refinements are ignored.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
