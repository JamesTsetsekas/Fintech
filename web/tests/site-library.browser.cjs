const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  for(const width of [390,768,1280]) {
   const page=await browser.newPage({viewport:{width,height:900}});
   const html=fs.readFileSync(path.resolve(__dirname,'../../charts/index.html'),'utf8').replace(/<script[\s\S]*?<\/script>/g,'').replace(/<link[^>]*>/g,'');
   await page.setContent(html);
   await page.addStyleTag({path:path.resolve(__dirname,'../assets/site.css')});
   await page.addScriptTag({path:path.resolve(__dirname,'../assets/site.js')});
   await page.evaluate(()=>{
    appState.manifest={charts:Array.from({length:60},(_,i)=>({id:'c'+i,title:i===0?'Alpha':'Beta '+i,section:'',description:''}))};
    bindKeyboardSearch(); renderSidebar();
    window.selectTerminalChart=id=>{window.selected=id;};
    window.handleChartAction=action=>{window.action=action;}; bindChartToolbar();
   });
   if(width<=820) {assert.equal(await page.locator('#library-results').isVisible(),false); await page.locator('#library-toggle').click();}
   assert(await page.locator('#library-results').isVisible());
   if(width<=820) {
    await page.locator('#sidebar-search').focus();
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#library-results').isVisible(),false);
    await page.keyboard.press('/');
    assert(await page.locator('#library-results').isVisible());
    assert(await page.locator('#sidebar-search').evaluate(n=>n===document.activeElement));
   }
   await page.locator('#sidebar-search').fill('Alpha');
   assert.equal(await page.locator('#all-count').textContent(),'1');
   await page.locator('#all-chart-list a').click();
   assert.equal(await page.evaluate(()=>window.selected),'c0');
   if(width<=820) {assert.equal(await page.locator('#library-results').isVisible(),false);assert(await page.locator('#library-toggle').evaluate(n=>n===document.activeElement));}
   await page.locator('#sidebar-search').fill('absent');
   assert.match(await page.locator('#all-chart-list').textContent(),/No charts match/);
   await page.locator('#sidebar-search').fill('');
   assert.equal(await page.locator('#all-count').textContent(),'60');
   if(width<=820) assert(await page.locator('#library-results').evaluate(n=>n.scrollHeight>n.clientHeight));
   for(const action of ['table','pin','download']) {await page.locator(`[data-chart-action="${action}"]`).click();assert.equal(await page.evaluate(()=>window.action),action);}
   assert(await page.locator('#chart-alert-link').isVisible());
   assert(await page.locator('#chart-alert-link').getAttribute('href'));
   await page.close();
  }
  console.log('PASS: library/search/select/clear and toolbar at 390/768/1280');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
