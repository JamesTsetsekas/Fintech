const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../assets/site.js'), 'utf8');
function harness(store = { value: '[]' }) {
  const controls = {};
  const nodes = {};
  const node = id => nodes[id] ||= { innerHTML: '', textContent: '', querySelectorAll(selector) { return selector.includes('toggle') ? Object.values(controls) : []; } };
  const scope = { window: { location: { search: '' } }, document: { body: { dataset: {} }, addEventListener() {}, querySelector: node }, URL, URLSearchParams, Intl,
    localStorage: { getItem: () => store.value, setItem(key, value) { if (store.fail) throw Error('quota'); store.value = value; } } };
  vm.createContext(scope); vm.runInContext(source, scope);
  scope.setScore = score => vm.runInContext(`appState.signals = ${JSON.stringify(score === null ? [] : [{ id: 's', label: 'Signal', score, points: [{ date: '2026-01-01', score: 10 }] }])}`, scope);
  scope.setScore(80);
  return { scope, store, nodes, controls, rules: () => JSON.parse(store.value) };
}
const rule = overrides => ({ id: 'r', signalId: 's', enabled: true, operator: 'above', threshold: 75, cadence: 'once', ...overrides });
function seed(h, value) { h.store.value = JSON.stringify([value]); }
test('one shot persists completion, survives render and reload, and can be rearmed', () => {
  const h = harness(); seed(h, rule()); h.scope.renderAlertRules();
  const first = h.rules()[0].triggeredAt;
  assert.ok(first); assert.equal(h.rules()[0].enabled, false);
  h.scope.renderAlertRules(); assert.equal(h.rules()[0].triggeredAt, first);
  const loaded = harness(h.store); loaded.scope.renderAlertRules();
  assert.match(loaded.nodes['#alert-list'].innerHTML, /Completed/);
  assert.equal(loaded.scope.evaluateAlert(loaded.rules()[0]), false);
  loaded.controls.r = { dataset: { alertToggle: 'r' }, checked: true, addEventListener(type, fn) { this.change = fn; } };
  loaded.scope.setScore(50); loaded.scope.renderAlertRules(); loaded.controls.r.change();
  assert.equal(loaded.rules()[0].triggeredAt, undefined); assert.equal(loaded.rules()[0].enabled, true);
  loaded.scope.setScore(80); loaded.scope.renderAlertRules(); assert.ok(loaded.rules()[0].triggeredAt);
});
test('recurring rules stay reusable and crossings use prior observations', () => {
  const h = harness(); seed(h, rule({ cadence: 'refresh', operator: 'crosses-above' }));
  h.scope.setScore(50); h.scope.renderAlertRules(); assert.equal(h.rules()[0].lastScore, 50);
  h.scope.setScore(80); h.scope.renderAlertRules(); assert.equal(h.rules()[0].enabled, true);
  assert.match(h.nodes['#alert-list'].innerHTML, /alert-rule triggered/);
  h.scope.renderAlertRules(); assert.doesNotMatch(h.nodes['#alert-list'].innerHTML, /alert-rule triggered/);
  h.scope.setScore(50); h.scope.renderAlertRules(); h.scope.setScore(80); h.scope.renderAlertRules();
  assert.match(h.nodes['#alert-list'].innerHTML, /alert-rule triggered/);
  assert.equal(h.rules()[0].triggeredAt, undefined);
});
test('missing signals do not consume rules or observations', () => {
  const h = harness(); seed(h, rule()); h.scope.setScore(null); h.scope.renderAlertRules();
  assert.equal(h.rules()[0].triggeredAt, undefined); assert.equal(h.rules()[0].lastScore, undefined);
});
test('storage failure is reported without claiming completion or throwing', () => {
  const h = harness(); seed(h, rule()); h.store.fail = true;
  assert.doesNotThrow(() => h.scope.renderAlertRules());
  assert.equal(h.rules()[0].triggeredAt, undefined);
  assert.match(h.nodes['#alert-save-status'].textContent, /could not be saved/i);
  assert.doesNotMatch(h.nodes['#alert-list'].innerHTML, /Completed/);
  assert.equal(h.scope.writeAlertRules([]), false);
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
  const control = { dataset: { alertToggle: 'r' }, checked: true, addEventListener(type, fn) { this.change = fn; } };
  h.controls.r = control;
  h.scope.renderAlertRules(); control.change();
  assert.equal(control.checked, false); assert.equal(h.rules()[0].enabled, false);
});

