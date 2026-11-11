const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise,resolve,reject}; };
const flush = () => new Promise(resolve => setImmediate(resolve));
function fixture() {
  const nodes = new Map();
  const node = selector => {
    if (!nodes.has(selector)) nodes.set(selector, {innerHTML:'', textContent:'', classList:{add(){},remove(){},toggle(){}}, removeAttribute(){},setAttribute(){}});
    return nodes.get(selector);
  };
  const listeners = new Map();
  const context = vm.createContext({URLSearchParams, CSS:{escape:x=>x}, console:{warn(){}}, window:{location:{search:'?chart=nupl'}}, document:{body:{dataset:{}},addEventListener:(name,fn)=>listeners.set(name,fn),querySelectorAll:()=>[],querySelector:selector=>selector.startsWith('[data-') || selector === '#sidebar-search' ? null : node(selector)}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../assets/site.js'),'utf8'),context);
  vm.runInContext(`appState.manifest = { generated_at:'2026-01-01', charts:['nupl','ohlc','unrelated'].map(id=>({id,title:id,kind:'interactive',data_path:id})) }; SIGNAL_DEFINITIONS.splice(0, SIGNAL_DEFINITIONS.length, {id:'nupl',chartId:'nupl'}, {id:'unrelated',chartId:'unrelated'}); renderSidebar = updateChartHeadings = updateChartControls = renderDataSheet = updateScaleButton = bindChartToolbar = () => {};`,context);
  const pending = deferred();
  const payloads = Object.fromEntries(['nupl','ohlc'].map(id=>[id,{id, updated_at:'2026-01-01',series:[{x:['2026-01-01','2026-01-02'],y:[1,2]}]}]));
  context.getPayload = id => id === 'unrelated' ? pending.promise : Promise.resolve(payloads[id]);
  const renders=[];
  context.renderTerminalPlot = async () => renders.push(vm.runInContext('appState.currentPayload.id',context));
  context.renderChartDetails = context.updateChartPhase;
  return {context,node,listeners,pending,payloads,renders,state:()=>vm.runInContext('appState',context)};
}
test('terminal renders and completes while unrelated signal is pending; late phase follows current selection', async()=>{
  const f=fixture();
  await f.context.renderChartTerminal();
  assert.deepEqual(f.renders,['nupl']);
  assert.ok(f.listeners.has('fintech-theme-change'));
  await f.context.selectTerminalChart('ohlc',{updateUrl:false});
  f.pending.resolve({id:'unrelated',series:[{x:['2026-01-01'],y:[2]}]});
  await flush();
  assert.deepEqual(f.renders,['nupl','ohlc']);
  assert.match(f.node('#chart-phase').innerHTML,/Data status/);
  await f.context.selectTerminalChart('nupl',{updateUrl:false});
  assert.match(f.node('#chart-phase').innerHTML,/Cycle signal/);
  const phase = f.node('#chart-phase').innerHTML;
  f.context.updateChartPhase(f.payloads.ohlc);
  assert.equal(f.node('#chart-phase').innerHTML,phase);
});
test('late signal applies phase without rendering chart again, and failed signals remain localized',async()=>{
  const f=fixture();
  await f.context.renderChartTerminal();
  assert.match(f.node('#chart-phase').innerHTML,/Data status/);
  f.pending.reject(new Error('offline'));
  await flush();
  assert.match(f.node('#chart-phase').innerHTML,/Cycle signal/);
  assert.deepEqual(f.renders,['nupl']);
});
test('dashboard starts cards before signals settle and isolates card fetch/render failures',async()=>{
  const f=fixture();
  const rendered=[];
  f.context.renderPlot=async(target,payload)=>{rendered.push(payload.id); if(payload.id==='ohlc') throw new Error('plot failed');};
  f.context.getPayload=id=>id==='unrelated'?f.pending.promise:id==='ohlc'?Promise.reject(new Error('offline')):Promise.resolve(f.payloads[id]);
  await f.context.renderDashboard();
  assert.deepEqual(rendered,['nupl']);
  assert.match(f.node('#dashboard-plot-ohlc').innerHTML,/offline/);
  assert.ok(f.listeners.has('fintech-theme-change'));
  f.pending.reject(new Error('signal offline'));
  await flush();
});
test('dashboard signal widget failures do not affect sibling widget or cards',async()=>{
  const f=fixture();
  let ribbon=0,heatmap=0,cards=0;
  f.context.renderMetricRibbon=()=>{ribbon++;throw new Error('ribbon');};
  f.context.renderSignalHeatmap=()=>{heatmap++;};
  f.context.renderPlot=async()=>{cards++;};
  await f.context.renderDashboard();
  assert.equal(cards,2);
  f.pending.resolve({id:'unrelated',series:[{x:['2026-01-01'],y:[1]}]});
  await flush();
  assert.equal(ribbon,1); assert.equal(heatmap,1);
});
test('dashboard catches rejected plot promises per card',async()=>{
  const f=fixture();
  f.context.renderPlot=async(target,payload)=>{if(payload.id==='ohlc') throw new Error('plot failed'); target.innerHTML='ready';};
  await f.context.renderDashboardCharts();
  assert.equal(f.node('#dashboard-plot-nupl').innerHTML,'ready');
  assert.match(f.node('#dashboard-plot-ohlc').innerHTML,/plot failed/);
});
