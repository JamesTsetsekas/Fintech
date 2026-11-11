const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
function context() {
  const scope = { window: { location: { search: '' } }, document: { body: { dataset: {} }, addEventListener() {} }, URL, URLSearchParams, Intl, console: { warn() {} } };
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../assets/site.js'), 'utf8'), scope);
  vm.runInContext('SIGNAL_DEFINITIONS.splice(0, SIGNAL_DEFINITIONS.length, { id: "nupl", chartId: "nupl", seriesKey: "nupl" });', scope);
  return scope;
}
const series = (key, y) => ({ source_key: key, x: y.map((_, i) => `2026-01-0${i + 1}`), y });
test('missing requested metric never falls back to price or enters composites and alerts', async () => {
  const s = context();
  s.getPayload = async () => ({ series: [series('price', [100, 200])] });
  const signals = await s.buildSignals();
  assert.equal(signals.length, 0);
  assert.equal(s.buildDashboardSignalSet(signals).length, 0);
  s.signals = signals;
  vm.runInContext('appState.signals = signals', s);
  assert.equal(s.evaluateAlert({ enabled: true, signalId: 'nupl', operator: 'below', threshold: 25 }), false);
});
test('empty and nonfinite observations produce no signal; real zero remains valid', async () => {
  const s = context();
  for (const values of [[], [null, undefined, '', NaN, Infinity], [' ', false, []]]) {
    s.getPayload = async () => ({ series: [series('nupl', values)] });
    assert.equal((await s.buildSignals()).length, 0);
  }
  s.getPayload = async () => ({ series: [series('nupl', [null, 0, 1])] });
  const signals = await s.buildSignals();
  assert.equal(signals.length, 1);
  assert.equal(signals[0].points.length, 2);
  assert.equal(signals[0].points[0].value, 0);
  assert.equal(signals[0].points[0].score, 0);
});
test('missing derived ratio observations do not create a signal', async () => {
  const s = context();
  vm.runInContext('SIGNAL_DEFINITIONS[0].build = ratioByKeys("price", "nupl")', s);
  s.getPayload = async () => ({ series: [series('price', [null, '']), series('nupl', [1, 2])] });
  assert.equal((await s.buildSignals()).length, 0);
});
test('raw formatting preserves unavailable values and dimensionless Sharpe', () => {
  const s = context();
  assert.equal(s.formatSignalRaw({ id: 'sharpe', rawValue: 1.25 }), '1.25');
  for (const rawValue of [null, undefined, '', ' ']) assert.equal(s.formatSignalRaw({ id: 'nupl', rawValue }), 'Unavailable');
  assert.equal(s.formatSignalRaw({ id: 'volatility', rawValue: 12 }), '12.0%');
});
test('unavailable supply displays no substitute value, trend label, or sparkline', async () => {
  const s = context();
  const ribbon = {};
  s.document.querySelector = () => ribbon;
  s.getPayload = async () => ({ series: [series('price', [100, 200]), series('average', [50, 50])] });
  for (const signals of [[], [{ id: 'supply-profit', rawValue: null, points: [], score: 50, phase: { key: 'bullish' } }]]) {
    await s.renderMetricRibbon(signals);
    const supply = ribbon.innerHTML.split('<article')[2].split('</article>')[0];
    assert.match(supply, /Unavailable/);
    assert.doesNotMatch(supply, /above trend|below trend|<svg|0\.0%/);
  }
});
