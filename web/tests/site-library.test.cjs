const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
function fixture(value, denied = false) {
  const nodes = new Map();
  for (const id of ['sidebar-search','all-chart-list','popular-list','pinned-list','pinned-count','popular-count','all-count','pin-status']) nodes.set('#'+id, {value:'alpha', textContent:'', innerHTML:'', classList:{remove(){}}});
  const context = {window:{location:{search:''}}, document:{body:{dataset:{}},addEventListener(){},querySelector:id=>nodes.get(id),querySelectorAll:()=>[]},URLSearchParams,Intl,localStorage:{getItem(){if(denied)throw Error(); return value;},setItem(k,v){if(denied)throw Error();value=v;}}};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../assets/site.js'),'utf8'),context);
  vm.runInContext(`appState.manifest={charts:[{id:'a',title:'Alpha',section:'',description:''},{id:'b',title:'Beta',section:'',description:''}]}; appState.currentChart={id:'a'};`,context);
  const button={classList:{toggle(){}},setAttribute(){}};
  return {context,nodes,button,get value(){return value;}};
}
test('pin reads tolerate malformed, invalid and denied storage and drop missing IDs',()=>{
  for(const value of ['{','null','{}','42','"a"']) assert.equal(fixture(value).context.readPinnedCharts().size,0);
  assert.deepEqual(Array.from(fixture('["a",4,null,"missing","a"]').context.readPinnedCharts()),['a']);
  assert.equal(fixture('[]',true).context.readPinnedCharts().size,0);
});
test('pin/unpin rerenders filtered sidebar without clearing search',()=>{
 const f=fixture('[]'); f.context.togglePinnedChart(f.button);
 assert.equal(f.value,'["a"]'); assert.match(f.nodes.get('#pinned-list').innerHTML,/Alpha/);
 assert.doesNotMatch(f.nodes.get('#all-chart-list').innerHTML,/Beta/);
 f.context.togglePinnedChart(f.button); assert.equal(f.value,'[]');
 assert.match(f.nodes.get('#pinned-list').innerHTML,/No pinned charts match/);
 assert.equal(f.nodes.get('#sidebar-search').value,'alpha');
});
test('denied write reports failure without changing button or rendering false success',()=>{
 const f=fixture('[]',true); f.context.togglePinnedChart(f.button);
 assert.match(f.nodes.get('#pin-status').textContent,/Could not save/);
 assert.equal(f.button.textContent,undefined);
});
