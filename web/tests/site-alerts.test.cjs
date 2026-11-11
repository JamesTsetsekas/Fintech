const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../assets/site.js'), 'utf8');
const RULES = 'fintech-alerts-v1';
const SEEN = 'fintech-alerts-seen-v1';
// `store` survives across harnesses, so a new harness is a page reload.
function harness(store = { value: '[]' }, search = '') {
  const controls = {};
  const nodes = {};
  const nav = { badge: null, title: undefined,
    querySelector() { return this.badge; },
    append(node) { this.badge = node; node.remove = () => { this.badge = null; }; },
    removeAttribute() { this.title = undefined; } };
  const node = id => id.startsWith('.terminal-nav') ? nav : nodes[id] ||= { innerHTML: '', textContent: '', value: '', hidden: false, querySelectorAll(selector) { return selector.includes('toggle') ? Object.values(controls) : []; } };
  const read = key => key === RULES ? store.value : key === SEEN ? store.seen ?? null : null;
  const scope = { window: { location: { search } }, document: { body: { dataset: {} }, addEventListener() {}, querySelector: node, createElement: () => ({ setAttribute(name, value) { this[name] = value; } }) }, URL, URLSearchParams, Intl, console: { warn() {} },
    localStorage: { getItem(key) { if (store.blocked) throw Error('denied'); return read(key); }, setItem(key, value) { if (store.fail || store.blocked) throw Error('quota'); if (key === RULES) store.value = value; if (key === SEEN) store.seen = value; } } };
  vm.createContext(scope); vm.runInContext(source, scope);
  scope.setSignals = (signals, version = 2, unavailable = []) => {
    scope.next = { signals, unavailable, method: { version } };
    vm.runInContext('appState.signalState = next; appState.signals = next.signals; appState.manifest = { charts: [{ id: "hodl-waves", title: "HODL Waves" }] }', scope);
  };
  scope.setScore = (score, version = 2) => scope.setSignals(score === null ? [] : [{ id: 's', chartId: 'chart-s', label: 'Signal', score, phase: { label: 'Top' }, points: [{ date: '2026-01-01', score: 10 }] }], version);
  scope.setScore(80);
  return { scope, store, nodes, controls, nav, rules: () => JSON.parse(store.value), list: () => nodes['#alert-list'].innerHTML };
}
const rule = overrides => ({ id: 'r', signalId: 's', enabled: true, operator: 'above', threshold: 75, cadence: 'once', ...overrides });
function seed(h, ...values) { h.store.value = JSON.stringify(values); }
const toggle = () => ({ dataset: { alertToggle: 'r' }, checked: true, addEventListener(type, fn) { this.change = fn; } });

test('one shot persists completion, survives render and reload, and can be rearmed', () => {
  const h = harness(); seed(h, rule()); h.scope.renderAlertRules();
  const first = h.rules()[0].triggeredAt;
  assert.ok(first); assert.equal(h.rules()[0].enabled, false);
  h.scope.renderAlertRules(); assert.equal(h.rules()[0].triggeredAt, first);
  const loaded = harness(h.store); loaded.scope.renderAlertRules();
  assert.match(loaded.list(), /Completed/);
  assert.equal(loaded.scope.evaluateAlert(loaded.rules()[0]), false);
  loaded.controls.r = toggle();
  loaded.scope.setScore(50); loaded.scope.renderAlertRules(); loaded.controls.r.change();
  assert.equal(loaded.rules()[0].triggeredAt, undefined); assert.equal(loaded.rules()[0].enabled, true);
  loaded.scope.setScore(80); loaded.scope.renderAlertRules(); assert.ok(loaded.rules()[0].triggeredAt);
});
test('a one shot alert that just fired keeps its triggered styling until the next visit', () => {
  const h = harness(); seed(h, rule()); h.scope.renderAlertRules();
  assert.equal(h.rules()[0].enabled, false);
  assert.match(h.list(), /alert-rule triggered/);
  assert.match(h.list(), /title="Triggered since your last visit"/);
  h.scope.renderAlertRules();
  assert.match(h.list(), /alert-rule triggered/, 're-rendering for another rule keeps the highlight');
  // The alerts page records the visit; the next load shows it as completed.
  h.store.seen = new Date(Date.now() + 1000).toISOString();
  const later = harness(h.store);
  vm.runInContext(`alertSession.seenAt = ${JSON.stringify(h.store.seen)}`, later.scope);
  later.scope.renderAlertRules();
  assert.doesNotMatch(later.list(), /alert-rule triggered/);
  assert.match(later.list(), /title="Completed"/);
});
test('recurring crossings use prior observations and fire once per crossing', () => {
  const h = harness(); seed(h, rule({ cadence: 'refresh', operator: 'crosses-above' }));
  h.scope.setScore(50); h.scope.renderAlertRules();
  assert.equal(h.rules()[0].lastScore, 50); assert.equal(h.rules()[0].methodVersion, 2);
  assert.doesNotMatch(h.list(), /alert-rule triggered/, 'the first check only sets a baseline');
  h.scope.setScore(80); h.scope.renderAlertRules(); assert.equal(h.rules()[0].enabled, true);
  assert.match(h.list(), /alert-rule triggered/);
  const firedAt = h.rules()[0].firedAt; assert.ok(firedAt);
  h.scope.renderAlertRules(); assert.equal(h.rules()[0].firedAt, firedAt, 'an unchanged score is not a second crossing');
  assert.equal(h.rules()[0].triggeredAt, undefined);
  const reloaded = harness(h.store);
  vm.runInContext('alertSession.seenAt = "9999"', reloaded.scope);
  reloaded.scope.renderAlertRules();
  assert.doesNotMatch(reloaded.list(), /alert-rule triggered/, 'a crossing already seen is not shown as new');
  reloaded.scope.setScore(50); reloaded.scope.renderAlertRules(); reloaded.scope.setScore(80); reloaded.scope.renderAlertRules();
  assert.match(reloaded.list(), /alert-rule triggered/);
  assert.notEqual(reloaded.rules()[0].firedAt, undefined);
});
test('level rules show a met condition live but only count a new event on the transition', () => {
  const h = harness(); seed(h, rule({ cadence: 'refresh' }));
  h.scope.setScore(60); h.scope.renderAlertRules();
  assert.equal(h.rules()[0].conditionMet, false); assert.equal(h.rules()[0].firedAt, undefined);
  h.scope.setScore(80); h.scope.renderAlertRules();
  const firedAt = h.rules()[0].firedAt; assert.ok(firedAt);
  const reloaded = harness(h.store);
  vm.runInContext('alertSession.seenAt = "9999"', reloaded.scope);
  reloaded.scope.renderAlertRules();
  assert.equal(reloaded.rules()[0].firedAt, firedAt, 'staying above the threshold is not a new event');
  assert.match(reloaded.list(), /title="Condition met"/);
  assert.match(reloaded.nodes['#alert-overview'].innerHTML, /Conditions met<\/small><strong>1</);
});
test('missing signals do not consume rules or observations', () => {
  const h = harness(); seed(h, rule()); h.scope.setScore(null); h.scope.renderAlertRules();
  assert.equal(h.rules()[0].triggeredAt, undefined); assert.equal(h.rules()[0].lastScore, undefined);
  assert.match(h.list(), /Unknown signal/);
  h.scope.setSignals([], 2, [{ id: 's', label: 'Signal', reason: 'series missing' }]); h.scope.renderAlertRules();
  assert.match(h.list(), /<strong>Signal \(unavailable\)<\/strong>/);
  assert.equal(h.rules()[0].lastScore, undefined);
});
test('a scoring method change re-baselines saved observations instead of firing', () => {
  // Saved under the previous method (no version): 60 then, 90 under the new method.
  for (const operator of ['above', 'crosses-above']) {
    const h = harness(); seed(h, rule({ operator, cadence: 'once', lastScore: 60 }));
    h.scope.setScore(90, 2); h.scope.renderAlertRules();
    const saved = h.rules()[0];
    assert.equal(saved.triggeredAt, undefined, `${operator}: the method change itself must not fire`);
    assert.equal(saved.firedAt, undefined); assert.equal(saved.enabled, true);
    assert.deepEqual([saved.lastScore, saved.methodVersion], [90, 2]);
    assert.ok(saved.rebaselinedAt);
    assert.match(h.list(), /re-baselined for scoring method v2; review this threshold/);
    assert.doesNotMatch(h.list(), /Triggered since your last visit/);
    // Comparisons resume within the new method.
    h.scope.setScore(70, 2); h.scope.renderAlertRules(); assert.equal(h.rules()[0].triggeredAt, undefined);
    h.scope.setScore(95, 2); h.scope.renderAlertRules(); assert.ok(h.rules()[0].triggeredAt, `${operator}: fires on a real move`);
  }
  const next = harness(); seed(next, rule({ operator: 'crosses-below', cadence: 'refresh', lastScore: 80, methodVersion: 2 }));
  next.scope.setScore(20, 3); next.scope.renderAlertRules();
  assert.equal(next.rules()[0].firedAt, undefined); assert.equal(next.rules()[0].methodVersion, 3);
  const fresh = harness(); seed(fresh, rule());
  fresh.scope.renderAlertRules();
  assert.ok(fresh.rules()[0].triggeredAt, 'a rule that was never observed has nothing to re-baseline');
  assert.equal(fresh.rules()[0].rebaselinedAt, undefined);
});
test('storage failure is reported without claiming completion or throwing', () => {
  const h = harness(); seed(h, rule()); h.store.fail = true;
  assert.doesNotThrow(() => h.scope.renderAlertRules());
  assert.equal(h.rules()[0].triggeredAt, undefined);
  assert.match(h.nodes['#alert-save-status'].textContent, /could not be saved/i);
  assert.doesNotMatch(h.list(), /Completed/);
  assert.equal(h.scope.writeAlertRules([]), false);
  const blocked = harness(); blocked.store.blocked = true;
  assert.equal(blocked.scope.readAlertRules().length, 0);
  assert.equal(blocked.scope.readAlertsSeenAt(), '');
  assert.equal(blocked.scope.writeAlertsSeenAt('2026-01-01'), false);
  assert.doesNotThrow(() => blocked.scope.renderAlertRules());
});
test('failed creation preserves form input and failed toggles preserve saved rules', () => {
  const h = harness(); seed(h, rule({ enabled: false }));
  let reset = false;
  h.nodes['#alert-form'] = { reset() { reset = true; } };
  for (const [id, value] of Object.entries({ 'alert-signal': 's', 'alert-operator': 'above', 'alert-threshold': '75', 'alert-cadence': 'once', 'alert-label': 'Keep my input' })) h.nodes[`#${id}`] = { value };
  h.scope.crypto = { randomUUID: () => 'new' };
  h.store.fail = true;
  h.scope.saveAlertFromForm({ preventDefault() {} });
  assert.equal(reset, false); assert.equal(h.rules().length, 1);
  const control = toggle();
  h.controls.r = control;
  h.scope.renderAlertRules(); control.change();
  assert.equal(control.checked, false); assert.equal(h.rules()[0].enabled, false);
});
test('the preview and saved rule text read as sentences', () => {
  const h = harness();
  const field = (id, value) => { h.nodes[`#${id}`] = { value, innerHTML: '', textContent: '' }; };
  field('alert-signal', 's'); field('alert-threshold', '75');
  for (const [operator, phrase] of [['above', 'is above'], ['below', 'is below'], ['crosses-above', 'crosses above'], ['crosses-below', 'crosses below']]) {
    field('alert-operator', operator); field('alert-preview', '');
    h.scope.updateAlertPreview();
    assert.match(h.nodes['#alert-preview'].innerHTML, new RegExp(`will trigger when its cycle score ${phrase} 75\\.`));
    assert.match(h.scope.alertRuleText(rule({ operator, cadence: 'refresh' }), { score: 80 }), new RegExp(`^Score ${phrase} 75 · now 80 · every time the site is opened$`));
  }
  field('alert-signal', '');
  h.scope.updateAlertPreview();
  assert.equal(h.nodes['#alert-preview'].textContent, 'Choose a signal to preview this rule.');
});
test('a request the form cannot honour shows a notice instead of selecting another signal', () => {
  const cases = [
    ['', '', ''],
    ['?signal=s', 's', ''],
    ['?chart=chart-s', 's', ''],
    ['?signal=gone', '', /Gone signal is unavailable in the latest data \(series 'x' is missing from chart 'chart-gone'\), so it was not selected/],
    ['?chart=chart-gone', '', /Gone signal is unavailable in the latest data/],
    ['?signal=typo', '', /There is no cycle signal named “typo”\. Choose a signal below\./],
    ['?chart=hodl-waves', '', /HODL Waves does not have a cycle score, so an alert cannot watch it directly/],
  ];
  for (const [search, selected, notice] of cases) {
    const h = harness({ value: '[]' }, search);
    h.scope.setSignals(
      [{ id: 'first', chartId: 'chart-first', label: 'First signal', score: 10 }, { id: 's', chartId: 'chart-s', label: 'Signal', score: 80 }],
      2, [{ id: 'gone', chartId: 'chart-gone', label: 'Gone signal', reason: "series 'x' is missing from chart 'chart-gone'" }]);
    h.nodes['#alert-signal'] = { value: 'first' };
    h.nodes['#alert-request-notice'] = { textContent: '', hidden: true };
    h.scope.applyAlertRequest();
    assert.equal(h.nodes['#alert-signal'].value, selected, `${search}: selected signal`);
    if (notice) assert.match(h.nodes['#alert-request-notice'].textContent, notice);
    assert.equal(h.nodes['#alert-request-notice'].hidden, !notice, `${search}: notice visibility`);
  }
  const h = harness();
  for (const [id, value] of Object.entries({ 'alert-signal': '', 'alert-operator': 'above', 'alert-threshold': '75', 'alert-cadence': 'once', 'alert-label': '' })) h.nodes[`#${id}`] = { value };
  h.scope.saveAlertFromForm({ preventDefault() {} });
  assert.equal(h.rules().length, 0, 'a rule is never saved against an unchosen signal');
  assert.match(h.nodes['#alert-save-status'].textContent, /Choose a signal/);
});
test('chart alert links carry the signal, or the chart when it has no signal', () => {
  const h = harness();
  const link = h.nodes['#chart-alert-link'] = {};
  h.scope.updateChartAlertLink({ id: 'chart-s' });
  assert.equal(link.href, '../alerts/?signal=s');
  h.scope.updateChartAlertLink({ id: 'hodl-waves' });
  assert.equal(link.href, '../alerts/?chart=hodl-waves');
  assert.match(link.title, /no cycle signal/);
});
test('rules are checked on every page and new firings are counted on the Alerts link', async () => {
  const h = harness(); seed(h, rule({ cadence: 'refresh', operator: 'crosses-above', lastScore: 50, methodVersion: 2 }), rule({ id: 'quiet', operator: 'below', threshold: 10 }));
  h.scope.loadSignalState = async () => vm.runInContext('appState.signalState', h.scope);
  await h.scope.checkAlertsInBackground();
  assert.ok(h.rules()[0].firedAt, 'the crossing is recorded from a page other than Alerts');
  assert.equal(h.nav.badge.textContent, '1');
  assert.equal(h.nav.badge['aria-label'], '1 alert fired since you last opened Alerts');
  assert.match(h.nav.title, /checked when you open the site$/);
  // Another page load with the same score neither re-fires nor loses the count.
  const again = harness(h.store);
  again.scope.loadSignalState = async () => vm.runInContext('appState.signalState', again.scope);
  await again.scope.checkAlertsInBackground();
  assert.equal(again.rules()[0].firedAt, h.rules()[0].firedAt);
  assert.equal(again.nav.badge.textContent, '1');
  // Opening Alerts shows it as new; displaying it is what marks it seen.
  const alerts = harness(h.store);
  vm.runInContext('alertSession.seenAt = readAlertsSeenAt()', alerts.scope);
  alerts.scope.renderAlertRules();
  assert.match(alerts.list(), /title="Triggered since your last visit"/);
  assert.ok(h.store.seen >= h.rules()[0].firedAt, 'the displayed firing is acknowledged');
  alerts.scope.renderAlertRules();
  assert.match(alerts.list(), /title="Triggered since your last visit"/, 'it stays highlighted for the rest of this visit');
  const after = harness(h.store);
  after.scope.loadSignalState = async () => vm.runInContext('appState.signalState', after.scope);
  await after.scope.checkAlertsInBackground();
  assert.equal(after.nav.badge, null, 'the count clears once the firing has been seen');
  const none = harness();
  none.scope.loadSignalState = async () => { throw new Error('signals must not load when there are no rules'); };
  await none.scope.checkAlertsInBackground();
  assert.equal(none.nav.badge, null);
});
test('a firing shown on the Alerts page is never counted again elsewhere, including after creating or re-arming a rule', async () => {
  const badgeElsewhere = async (store) => {
    const page = harness(store);
    page.scope.loadSignalState = async () => vm.runInContext('appState.signalState', page.scope);
    await page.scope.checkAlertsInBackground();
    return page.nav.badge;
  };
  // The Alerts page is open with no rules, so the visit is recorded before anything fires.
  const h = harness();
  vm.runInContext('alertSession.seenAt = readAlertsSeenAt()', h.scope);
  h.scope.renderAlertRules();
  assert.equal(h.store.seen, undefined, 'nothing has fired, so there is nothing to acknowledge');
  // Create a rule whose condition already holds: it fires and is displayed at once.
  h.nodes['#alert-form'] = { reset() {} };
  for (const [id, value] of Object.entries({ 'alert-signal': 's', 'alert-operator': 'above', 'alert-threshold': '75', 'alert-cadence': 'once', 'alert-label': '' })) h.nodes[`#${id}`] = { value };
  h.scope.crypto = { randomUUID: () => 'created' };
  h.scope.saveAlertFromForm({ preventDefault() {} });
  const created = h.rules()[0];
  assert.ok(created.firedAt && created.triggeredAt);
  assert.match(h.list(), /alert-rule triggered/);
  assert.ok(h.store.seen >= created.firedAt, 'the firing was acknowledged when it was displayed');
  assert.equal(await badgeElsewhere(h.store), null, 'navigating away must not report the firing as unseen');
  // Re-arming a rule that immediately fires again is displayed too.
  h.controls.created = { dataset: { alertToggle: 'created' }, checked: true, addEventListener(type, fn) { this.change = fn; } };
  h.scope.renderAlertRules();
  await new Promise((resolve) => setTimeout(resolve, 5));
  h.controls.created.change();
  const rearmed = h.rules()[0];
  assert.ok(rearmed.firedAt > created.firedAt, 'the rule fired again after re-arming');
  assert.ok(h.store.seen >= rearmed.firedAt);
  assert.match(h.list(), /title="Triggered since your last visit"/, 'the highlight stays for this visit');
  assert.equal(await badgeElsewhere(h.store), null);
  // A firing recorded later on another page is still counted.
  h.store.value = JSON.stringify([...h.rules(), rule({ id: 'later', cadence: 'refresh', operator: 'crosses-above', lastScore: 50, methodVersion: 2 })]);
  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal((await badgeElsewhere(h.store)).textContent, '1');
  // A firing that could not be saved was not recorded, so it is not acknowledged.
  const failing = harness(); seed(failing, rule()); failing.store.fail = true;
  failing.scope.renderAlertRules();
  assert.equal(failing.store.seen, undefined);
});
