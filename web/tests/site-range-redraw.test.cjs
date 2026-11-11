const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function fixture() {
  const full = ['2020-01-01', '2026-01-01'];
  const target = { innerHTML: '', _fullLayout: { xaxis: { range: full.slice() } } };
  const buttons = ['all', '1y'].map(range => ({ dataset: { range }, classList: { toggle(_name, active) { this.active = active; } } }));
  const context = vm.createContext({
    window: { location: { search: '' }, Plotly: {} },
    document: { body: { dataset: {} }, addEventListener() {}, querySelector: () => target, querySelectorAll: () => buttons },
    URLSearchParams, Intl, Date,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../assets/site.js'), 'utf8'), context);
  context.target = target;
  context.full = full;
  vm.runInContext(`
    appState.currentPayload = { x_value_type: 'date', series: [{ name: 'Price', x: full, y: [10, 100] }] };
    terminalSeries = payload => payload.series;
    terminalLayout = () => ({});
    renderPlot = async () => {
      target._fullLayout.xaxis.range = full.slice();
      target._fintechNavigation = {
        zoomTo: async range => { target._fullLayout.xaxis.range = range.slice(); },
        reset: async () => { target._fullLayout.xaxis.range = full.slice(); }
      };
    };
  `, context);
  return { context, target, buttons };
}

test('selected shortcut survives option and theme redraws; All restores full history', async () => {
  const { context, target, buttons } = fixture();
  await context.renderTerminalPlot();
  await context.setChartRange('1y');
  const selected = Array.from(target._fullLayout.xaxis.range);
  for (const option of ['grid', 'movingAverage', 'halvings', 'scale', 'theme']) {
    vm.runInContext(`appState.chartOptions[${JSON.stringify(option)}] = true`, context);
    await context.renderTerminalPlot();
    assert.deepEqual(Array.from(target._fullLayout.xaxis.range), selected, option);
    assert.equal(buttons[1].classList.active, true);
  }
  await context.setChartRange('all');
  await context.renderTerminalPlot();
  assert.deepEqual(Array.from(target._fullLayout.xaxis.range), ['2020-01-01', '2026-01-01']);
});

test('manual viewport survives redraw but a different payload starts with full history', async () => {
  const { context, target } = fixture();
  await context.renderTerminalPlot();
  target._fullLayout.xaxis.range = ['2024-02-01', '2024-03-01'];
  await context.renderTerminalPlot();
  assert.deepEqual(Array.from(target._fullLayout.xaxis.range), ['2024-02-01', '2024-03-01']);
  vm.runInContext('appState.currentPayload = { ...appState.currentPayload }', context);
  await context.renderTerminalPlot();
  assert.deepEqual(Array.from(target._fullLayout.xaxis.range), ['2020-01-01', '2026-01-01']);
});

test('redraw waits for an in-flight shortcut to reach its final viewport', async () => {
  const { context, target } = fixture();
  await context.renderTerminalPlot();
  let finish;
  target._fintechNavigation.zoomTo = range => new Promise(resolve => {
    finish = () => { target._fullLayout.xaxis.range = range.slice(); resolve(); };
  });
  const transition = context.setChartRange('1y');
  const redraw = context.renderTerminalPlot();
  finish();
  await Promise.all([transition, redraw]);
  assert.deepEqual(Array.from(target._fullLayout.xaxis.range), ['2025-01-01T00:00:00.000Z', '2026-01-01T00:00:00.000Z']);
});
