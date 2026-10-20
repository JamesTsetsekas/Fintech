const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function context(theme = 'dark') {
  let plotted;
  const plotly = { newPlot(_target, traces) { plotted = traces; return Promise.resolve({}); } };
  const result = {
    window: { location: { search: '' }, Plotly: plotly },
    Plotly: plotly,
    document: { body: { dataset: {} }, documentElement: { dataset: { theme } }, addEventListener() {} },
    URLSearchParams,
    Intl,
  };
  vm.createContext(result);
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../assets/site.js'), 'utf8'), result);
  return { result, traces: () => plotted };
}

test('cohort loss gap tooltips preserve percentage-point units', () => {
  const { result } = context();
  assert.equal(result.formatHoverMetricValue('Old minus new, 30-day average', -25, '%{y:,.4g} pp'), '-25 pp');
});

test('upstream black WMA lines retain contrast in dark and light themes', async () => {
  for (const theme of ['dark', 'light']) {
    const { result, traces } = context(theme);
    await result.renderPlot({}, {
      series: [{ name: '50WMA', type: 'scatter', x: ['2026-10-19'], y: [60000], line: { color: '#000000' } }],
      layout: {},
    }, { compact: true });
    assert.equal(traces()[0].line.color, theme === 'dark' ? '#eef3f8' : '#393732');
  }
});
