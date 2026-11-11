const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const read = (...parts) => fs.readFileSync(path.resolve(__dirname, ...parts), 'utf8');
const json = (...parts) => JSON.parse(read(...parts));
const source = read('../assets/site.js');
const fixture = {
  definitions: json('fixtures/signals/definitions.json'),
  charts: json('fixtures/signals/charts.json'),
  expected: json('fixtures/signals/expected.json'),
};
const production = json('../assets/signal-definitions.json');
const plain = (value) => JSON.parse(JSON.stringify(value));

function context(search = '') {
  const nodes = {};
  const node = (selector) => nodes[selector] ||= {
    innerHTML: '', textContent: '', title: '', hidden: false, value: '',
    classList: { remove() {}, add() {}, toggle() {} },
    querySelectorAll: () => [], insertAdjacentHTML() {}, addEventListener() {},
  };
  const scope = {
    window: { location: { search } },
    document: { body: { dataset: {} }, addEventListener() {}, querySelector: node },
    URL, URLSearchParams, Intl, console: { warn() {} },
    localStorage: { getItem: () => null, setItem() {} },
  };
  vm.createContext(scope);
  vm.runInContext(source, scope);
  vm.runInContext('appState.manifest = { generated_at: "2025-01-02T00:05:00+00:00", charts: [] }', scope);
  return { scope, nodes };
}

// Serve the fixture the way the site does: one artifact next to the manifest,
// definitions under web/assets and one payload per chart.
function serve(scope, { artifact = fixture.expected, definitions = fixture.definitions } = {}) {
  const requests = [];
  scope.fetchJson = async (file) => {
    requests.push(file);
    if (file.endsWith('signals.json')) {
      if (artifact instanceof Error) throw artifact;
      return plain(artifact);
    }
    if (file.endsWith('signal-definitions.json')) return plain(definitions);
    throw new Error(`unexpected request ${file}`);
  };
  scope.getPayload = async (chartId) => {
    requests.push(`chart:${chartId}`);
    if (!fixture.charts[chartId]) throw new Error(`No interactive data for ${chartId}`);
    return plain(fixture.charts[chartId]);
  };
  return requests;
}

function assertClose(actual, expected, where = 'artifact') {
  if (typeof expected === 'number' && typeof actual === 'number') {
    const tolerance = 1e-9 * Math.max(1, Math.abs(expected));
    assert.ok(Math.abs(actual - expected) <= tolerance, `${where}: ${actual} != ${expected}`);
    return;
  }
  if (Array.isArray(expected)) {
    assert.ok(Array.isArray(actual), `${where}: expected an array`);
    assert.equal(actual.length, expected.length, `${where}: length`);
    expected.forEach((item, index) => assertClose(actual[index], item, `${where}[${index}]`));
    return;
  }
  if (expected && typeof expected === 'object') {
    assert.ok(actual && typeof actual === 'object', `${where}: expected an object`);
    assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort(), `${where}: keys`);
    Object.keys(expected).forEach((key) => assertClose(actual[key], expected[key], `${where}.${key}`));
    return;
  }
  assert.equal(actual, expected, where);
}

test('browser fallback scoring reproduces the Python golden artifact', () => {
  const { scope } = context();
  const built = plain(scope.buildSignalsArtifact(plain(fixture.definitions), (id) => fixture.charts[id] ?? null, fixture.expected.generated_at));
  assertClose(built, fixture.expected);
  assert.deepEqual(built.unavailable.map((item) => item.id), ['too-short', 'renamed', 'no-chart']);
});

test('pages read one compact artifact instead of a payload per signal', async () => {
  const { scope } = context();
  const requests = serve(scope);
  const state = await scope.loadSignalState();
  assert.deepEqual(requests, ['web/data/bitcoin/signals.json']);
  assert.equal(state.source, 'artifact');
  assert.equal(state.signals.length, fixture.expected.signals.length);
  assert.equal(state.composite.score, fixture.expected.composite.score);
  assert.equal(state.dataThrough, fixture.expected.data_through);
  assert.equal(state.generatedAt, fixture.expected.generated_at);
  assert.equal((await scope.buildSignals()).length, state.signals.length);
  assert.equal(requests.length, 1, 'the artifact is requested once per page');
  for (const signal of state.signals) {
    const published = fixture.expected.signals.find((item) => item.id === signal.id);
    assert.equal(signal.phase.key, published.phase, `${signal.id} phase follows the published cut-offs`);
    assert.equal(signal.rawValue, published.value);
    assert.equal(signal.date, published.date);
    assert.ok(signal.points.length > 0 && signal.points.every((point) => Number.isFinite(point.score)));
  }
});

test('a missing, invalid or outdated artifact falls back to chart payloads with the same result', async () => {
  const outdated = { ...fixture.expected, generated_at: '2024-12-25T00:00:00+00:00' };
  const cases = [
    new Error('Could not load signals.json'),
    { ...fixture.expected, schema_version: 99 },
    { ...fixture.expected, signals: [] },
    { ...fixture.expected, signals: [{ ...fixture.expected.signals[0], score: null }] },
    { ...fixture.expected, method: undefined },
    outdated,
    'not json',
  ];
  for (const artifact of cases) {
    const { scope } = context();
    const requests = serve(scope, { artifact });
    const state = await scope.loadSignalState();
    assert.equal(state.source, 'fallback');
    assert.ok(requests.includes('web/assets/signal-definitions.json'));
    assert.ok(requests.includes('chart:plain-chart'));
    assert.equal(state.composite.score, fixture.expected.composite.score);
    assert.deepEqual(plain(state.signals.map((signal) => [signal.id, signal.score])), fixture.expected.signals.map((signal) => [signal.id, signal.score]));
    assert.deepEqual(plain(state.unavailable.map((item) => item.id)), ['too-short', 'renamed', 'no-chart']);
  }
});

test('derived indicators join on the observation date, not the array position', () => {
  const { scope } = context();
  const definition = { chart_id: 'c', input: { type: 'ratio', numerator: { key: 'n' }, denominator: { key: 'd' } } };
  const resolve = (numerator, denominator) => plain(scope.resolveSignalObservations(definition, { series: [
    { source_key: 'n', x: numerator.map(([date]) => date), y: numerator.map(([, value]) => value) },
    { source_key: 'd', x: denominator.map(([date]) => date), y: denominator.map(([, value]) => value) },
  ] }));
  const days = (dates) => dates.map((date) => scope.signalDay(date));
  const numerator = [['2026-01-01', 10], ['2026-01-02', 20], ['2026-01-03', 30]];
  // Shifted by one day: only the two shared dates pair, each with its own day.
  assert.deepEqual(resolve(numerator, [['2026-01-02', 2], ['2026-01-03', 3], ['2026-01-04', 4]]),
    { days: days(['2026-01-02', '2026-01-03']), values: [10, 10] });
  // A missing or null denominator row drops that day instead of sliding the rest.
  assert.deepEqual(resolve(numerator, [['2026-01-01', 5], ['2026-01-02', null], ['2026-01-03', 6]]),
    { days: days(['2026-01-01', '2026-01-03']), values: [2, 5] });
  // A duplicated date keeps the later real value; a zero denominator is skipped.
  assert.deepEqual(resolve(numerator, [['2026-01-01', 1], ['2026-01-01', 4], ['2026-01-02', 0], ['2026-01-03', 3], ['2026-01-03', null]]),
    { days: days(['2026-01-01', '2026-01-03']), values: [2.5, 10] });
  // Unordered rows are sorted by date.
  assert.deepEqual(resolve([['2026-01-03', 30], ['2026-01-01', 10]], [['2026-01-01', 10], ['2026-01-03', 10]]),
    { days: days(['2026-01-01', '2026-01-03']), values: [1, 3] });

  const band = { chart_id: 'c', input: { type: 'band_position', value: { name: 'p' }, lower: { name: 'lo' }, upper: { name: 'hi' } } };
  const position = plain(scope.resolveSignalObservations(band, { series: [
    { name: 'p', x: ['2026-01-01', '2026-01-02', '2026-01-03'], y: [15, 30, 18] },
    { name: 'lo', x: ['2026-01-02', '2026-01-03'], y: [20, 10] },
    { name: 'hi', x: ['2026-01-03', '2026-01-02'], y: [20, 40] },
  ] }));
  assert.deepEqual(position, { days: days(['2026-01-02', '2026-01-03']), values: [0.5, 0.8] });
  assert.throws(() => scope.resolveSignalObservations(definition, { series: [{ source_key: 'n', x: [], y: [] }] }), /source key 'd' is missing from chart 'c'/);
});

test('rank scoring is identical for rescalings of one quantity and never uses later data', () => {
  const { scope } = context();
  const scoring = { min_history_days: 0, min_observations: 1 };
  const mvrv = [1.2, 0.8, 2.5, 1.2, 3.1, 0.9, 1.7];
  const nupl = mvrv.map((value) => 1 - 1 / value);
  const days = mvrv.map((_, index) => index);
  const scores = plain(scope.expandingSignalScores(days, mvrv, scoring));
  assert.deepEqual(scores, plain(scope.expandingSignalScores(days, nupl, scoring)));
  assert.deepEqual(scores.slice(0, 4), [50, 25, 100 * 2.5 / 3, 50]);
  // Point-in-time: appending later observations leaves earlier scores alone.
  assert.deepEqual(plain(scope.expandingSignalScores([...days, 7], [...mvrv, 99], scoring)).slice(0, 7), scores);
  assert.deepEqual(plain(scope.expandingSignalScores(days, mvrv, scoring, true)), scores.map((score) => 100 - score));
  assert.deepEqual(plain(scope.expandingSignalScores([0, 10, 20], [1, 2, 3], { min_history_days: 20, min_observations: 1 })), [null, null, 100 * 2.5 / 3]);
});

test('a look-back window without scored history is unavailable, not measured from the first point', async () => {
  const { scope, nodes } = context();
  serve(scope);
  const state = await scope.loadSignalState();
  const young = state.signals.find((signal) => signal.id === 'young');
  assert.equal(scope.signalDelta(young, 30), -40.3);
  assert.equal(scope.signalDelta(young, 90), null);
  assert.equal(scope.signalDelta(young, 365), null);
  assert.equal(scope.signedScore(scope.signalDelta(young, 365)), '—');
  assert.equal(scope.signedScore(0.2), '0');
  assert.equal(scope.signedScore(-3.6), '-4');

  const only = (changes) => [{ ...young, changes }];
  scope.renderSignalInsights(only({ 30: null }));
  assert.match(nodes['#signal-insights'].innerHTML, /No shown signal has 30 days of scored history yet/);
  scope.renderSignalInsights([...only({ 30: null }), { ...young, id: 'mover', label: 'Mover', changes: { 30: 12 } }]);
  const movers = nodes['#signal-insights'].innerHTML.split('30D movers')[1];
  assert.match(movers, /Mover<\/span><strong class="">\+12/);
  assert.doesNotMatch(movers, /Young metric/);

  scope.renderSignalTable(only({ 7: 6.3, 30: -40.3, 90: null, 365: null }));
  const cells = nodes['#signal-table-body'].innerHTML.match(/<td class="signal-delta[^>]*>[^<]*<\/td>/g);
  assert.deepEqual(cells.map((cell) => cell.replace(/<[^>]+>/g, '')), ['+6', '-40', '—', '—']);
});

test('dashboard and signals page share one Cycle Index; filtered averages are labelled separately', async () => {
  const { scope, nodes } = context();
  serve(scope);
  const state = await scope.loadSignalState();
  const index = Math.round(fixture.expected.composite.score);
  scope.renderMetricRibbon(state);
  const ribbon = nodes['#metric-ribbon'].innerHTML;
  assert.match(ribbon.split('Cycle index')[1], new RegExp(`terminal-metric-value">${index}<`));
  assert.match(ribbon, /5 of 7 signals · equal weight/);

  const filtered = state.signals.filter((signal) => signal.category === 'Mining');
  assert.equal(filtered.length, 2);
  scope.renderSignalSummary(filtered, state);
  const summary = nodes['#signal-summary'].innerHTML;
  assert.match(summary, new RegExp(`<small>Cycle Index</small><strong>${index}</strong>`));
  assert.match(summary, /5 of 7 signals · equal weight/);
  scope.renderSignalTable(filtered);
  const average = Math.round(filtered.reduce((sum, signal) => sum + signal.score, 0) / filtered.length);
  assert.equal(nodes['#signal-table-count'].textContent, `2 signals · Average of 2 shown: ${average}`);
  assert.notEqual(average, index, 'the fixture must distinguish the filtered average from the index');
  scope.renderCycleSpectrum(filtered, state);
  assert.match(nodes['#cycle-spectrum'].innerHTML, new RegExp(`INDEX ${index}<`));

  const rows = scope.buildDashboardSignalSet(state);
  assert.equal(rows[0].id, 'cycle-index');
  assert.deepEqual(plain(rows.slice(1).map((signal) => signal.id)), fixture.expected.signals.filter((signal) => signal.composite).map((signal) => signal.id));
  assert.equal(scope.buildDashboardSignalSet({ signals: [] }).length, 0);
});

test('freshness separates publication time from data date and reports stale and unavailable signals', async () => {
  const { scope, nodes } = context();
  serve(scope);
  const state = await scope.loadSignalState();
  const lagging = state.signals.find((signal) => signal.id === 'lagging');
  const weekly = state.signals.find((signal) => signal.id === 'weekly-ratio');
  assert.equal(lagging.stale, true);
  assert.equal(lagging.lagDays, 5);
  assert.equal(weekly.stale, false, 'a weekly source one day behind is not stale');
  const target = scope.document.querySelector('#dashboard-updated');
  scope.renderFreshness(target, state);
  assert.equal(target.textContent, 'Published Jan 2, 2025, 00:00 UTC · Data through Dec 17, 2024 · 2 signals stale · 3 signals unavailable');
  assert.match(target.title, /Renamed upstream series: series 'Old metric name' is missing from chart 'plain-chart'/);
  scope.renderFreshness(target, state, { detail: true });
  assert.match(target.textContent, /3 signals unavailable: Too short, Renamed upstream series, Chart not generated/);
  scope.renderFreshness(target, null);
  assert.equal(target.textContent, 'Published Jan 2, 2025, 00:05 UTC');
  assert.deepEqual(plain(state.composite.missingMembers), ['abandoned', 'too-short']);
});

test('published definitions keep one representative per quantity in the Cycle Index', () => {
  const { scope } = context();
  assert.deepEqual(plain(vm.runInContext('DEFAULT_SIGNAL_PHASES', scope)), production.method.phases);
  const ids = production.signals.map((signal) => signal.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(new Set(production.signals.map((signal) => signal.chart_id)).size, ids.length);
  const members = production.signals.filter((signal) => signal.composite).map((signal) => signal.id);
  assert.ok(members.length >= production.method.composite.min_members);
  const duplicates = {
    nupl: 'mvrv', 'realized-price': 'mvrv',
    'sts-nupl': 'sth-mvrv', 'realized-price-sts': 'sth-mvrv',
    'lts-nupl': 'lth-mvrv', 'realized-price-lts': 'lth-mvrv',
    trend: 'mayer',
  };
  for (const [duplicate, representative] of Object.entries(duplicates)) {
    const signal = production.signals.find((item) => item.id === duplicate);
    assert.equal(signal.composite, false, `${duplicate} must not be double counted`);
    assert.deepEqual([signal.exclusion.reason, signal.exclusion.of], ['duplicate', representative]);
    assert.ok(members.includes(representative));
  }
  for (const id of ['hashprice', 'fees', 'thermocap']) {
    const signal = production.signals.find((item) => item.id === id);
    assert.deepEqual([signal.composite, signal.exclusion.reason], [false, 'structural_trend']);
  }
  // The "How scores work" copy states these numbers in prose.
  const page = read('../../signals/index.html');
  const sources = production.method.freshness.sources;
  assert.deepEqual(production.method.phases.map((phase) => phase.below), [25, 50, 75, null]);
  assert.match(page, /Bottom is below 25, Bearish 25 to 50, Bullish 50 to 75 and Top 75 or above/);
  assert.equal(production.method.scoring.min_history_days, 730);
  assert.match(page, /until an indicator has two years of history/);
  assert.deepEqual([sources.native.stale_after_days, sources.blockhorizon.stale_after_days], [2, 9]);
  assert.match(page, /by more than 2 days \(9 days for weekly on-chain sources\)/);
  for (const signal of production.signals) {
    assert.ok(production.method.freshness.sources[signal.source], `${signal.id} has a known source cadence`);
    assert.equal(Boolean(signal.exclusion), !signal.composite, `${signal.id} explains its exclusion`);
  }
});
