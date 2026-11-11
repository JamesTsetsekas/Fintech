const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
// One NUPL-style definition scored without a warm-up period, so these cases
// exercise resolution of the requested series rather than history length.
const method = {
  version: 2,
  scoring: { min_history_days: 0, min_observations: 1 },
  phases: [{ key: 'bottom', label: 'Bottom', below: 25 }, { key: 'bearish', label: 'Bearish', below: 50 }, { key: 'bullish', label: 'Bullish', below: 75 }, { key: 'top', label: 'Top', below: null }],
  change_windows_days: [7, 30, 90, 365],
  history: { step_days: 7, carry_forward_days: 14, value_significant_digits: 4 },
  freshness: { sources: { blockhorizon: { stale_after_days: 9 } } },
  composite: { id: 'cycle-index', label: 'Cycle Index', min_members: 1 },
};
const definitions = (input = { type: 'series', series: { key: 'nupl' } }) => ({
  method,
  signals: [{ id: 'nupl', chart_id: 'nupl', label: 'NUPL', category: 'Valuation', source: 'blockhorizon', composite: true, input }],
});
function context() {
  const scope = { window: { location: { search: '' } }, document: { body: { dataset: {} }, addEventListener() {} }, URL, URLSearchParams, Intl, console: { warn() {} } };
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../assets/site.js'), 'utf8'), scope);
  return scope;
}
const series = (key, y) => ({ source_key: key, x: y.map((_, i) => `2026-01-0${i + 1}`), y });
const build = (scope, payload, input) => JSON.parse(JSON.stringify(scope.buildSignalsArtifact(definitions(input), () => payload)));
test('missing requested metric never falls back to price or enters composites and alerts', () => {
  const s = context();
  const artifact = build(s, { series: [series('price', [100, 200])] });
  assert.equal(artifact.signals.length, 0);
  assert.deepEqual(artifact.unavailable.map((item) => [item.id, item.reason]), [['nupl', "source key 'nupl' is missing from chart 'nupl'"]]);
  assert.equal(artifact.composite, null);
  const state = s.hydrateSignalState(artifact, 'fallback');
  assert.equal(s.buildDashboardSignalSet(state).length, 0);
  s.state = state;
  vm.runInContext('appState.signalState = state; appState.signals = state.signals', s);
  assert.equal(s.evaluateAlert({ enabled: true, signalId: 'nupl', operator: 'below', threshold: 25 }), false);
});
test('empty and nonfinite observations produce no signal; real zero remains valid', () => {
  const s = context();
  for (const values of [[], [null, undefined, '', NaN, Infinity], [' ', false, []]]) {
    const artifact = build(s, { series: [series('nupl', values)] });
    assert.equal(artifact.signals.length, 0);
    assert.equal(artifact.unavailable[0].reason, 'no finite observations');
  }
  const artifact = build(s, { series: [series('nupl', [null, 0, 1])] });
  assert.equal(artifact.signals.length, 1);
  assert.equal(artifact.signals[0].observations, 2);
  assert.equal(artifact.signals[0].first_date, '2026-01-02');
  assert.equal(artifact.signals[0].value, 1);
  assert.equal(artifact.signals[0].history.values.at(-1), 1);
  const zero = build(s, { series: [series('nupl', [1, 0])] });
  assert.equal(zero.signals[0].value, 0);
  assert.equal(zero.signals[0].score, 25);
});
test('missing derived ratio observations do not create a signal', () => {
  const s = context();
  const ratio = { type: 'ratio', numerator: { key: 'price' }, denominator: { key: 'nupl' } };
  const artifact = build(s, { series: [series('price', [null, '']), series('nupl', [1, 2])] }, ratio);
  assert.equal(artifact.signals.length, 0);
  assert.equal(artifact.unavailable[0].reason, 'no finite observations');
});
test('a signal still inside its warm-up period is reported unavailable rather than scored', () => {
  const s = context();
  const warm = definitions();
  warm.method = { ...method, scoring: { min_history_days: 730, min_observations: 60 } };
  const artifact = JSON.parse(JSON.stringify(s.buildSignalsArtifact(warm, () => ({ series: [series('nupl', [1, 2, 3])] }))));
  assert.equal(artifact.signals.length, 0);
  assert.equal(artifact.unavailable[0].reason, 'history is shorter than the scoring minimum');
});
test('raw formatting preserves unavailable values and uses the published unit', () => {
  const s = context();
  assert.equal(s.formatSignalRaw({ id: 'sharpe', unit: 'index', decimals: 2, rawValue: 1.25 }), '1.25');
  for (const rawValue of [null, undefined, '', ' ']) assert.equal(s.formatSignalRaw({ id: 'nupl', unit: 'index', rawValue }), 'Unavailable');
  assert.equal(s.formatSignalRaw({ id: 'volatility', unit: 'percent', decimals: 1, rawValue: 12 }), '12.0%');
  assert.equal(s.formatSignalRaw({ id: 'mayer', unit: 'multiple', decimals: 2, rawValue: 1.00677 }), '1.01x');
  assert.equal(s.formatSignalRaw({ id: 'bollinger', unit: 'band_position', rawValue: 0.4321 }), '43% of band');
  assert.equal(s.formatSignalRaw({ id: 'ath-age', unit: 'days', rawValue: 400 }), '400 days');
  assert.equal(s.formatSignalRaw({ id: 'fees', unit: 'sat_per_vbyte', decimals: 2, rawValue: 1.888615 }), '1.89 sat/vB');
});
test('unavailable market and supply display no substitute value, trend label, or sparkline', () => {
  const s = context();
  const ribbon = {};
  s.document.querySelector = () => ribbon;
  const phase = { key: 'bullish', label: 'Bullish', className: 'phase-bullish' };
  for (const signals of [[], [{ id: 'supply-profit', rawValue: null, points: [], score: 50, phase, composite: true }]]) {
    s.renderMetricRibbon({ signals, composite: null, market: null, method });
    const [, price, supply, trend, index] = ribbon.innerHTML.split('<article').map((card) => card.split('</article>')[0]);
    for (const card of [price, supply, trend]) {
      assert.match(card, /Unavailable/);
      assert.doesNotMatch(card, /above trend|below trend|<svg|0\.0%|NaN/);
    }
    assert.match(index, /terminal-metric-value">—</);
    assert.doesNotMatch(ribbon.innerHTML, /NaN|undefined/);
  }
});
test('raw supply change is unavailable when history does not reach back far enough', () => {
  const s = context();
  const points = [{ date: '2026-01-01', value: 50, score: 40 }, { date: '2026-01-08', value: 55, score: 45 }];
  assert.ok(Number.isNaN(s.rawSignalDelta({ points }, 30)));
  assert.equal(s.rawSignalDelta({ points }, 7), 5);
  assert.ok(Number.isNaN(s.rawSignalDelta({ points: [points[0], { date: '2026-03-01', value: 70, score: 60 }] }, 30)));
  assert.ok(Number.isNaN(s.rawSignalDelta({ points: [] }, 30)));
});
