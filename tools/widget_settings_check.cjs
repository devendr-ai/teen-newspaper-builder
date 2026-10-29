// The installed-app bridge is simulated; the real app gate and parent page run unchanged.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({executablePath:process.env.CHROME,headless:true});try{
 const p=await b.newPage({viewport:{width:390,height:900}});const outside=[];
 const base=process.argv[2]||'http://127.0.0.1:8736/';p.on('request',r=>{if(!r.url().startsWith(base))outside.push(r.url())});
 await p.addInitScript(()=>{
  Object.defineProperty(window.crypto,'getRandomValues',{value:a=>a.fill(0)});
  window.widgetMessages=[];let on=false,edition='breakfast-table';
  function settings(){window.__np({t:'settings',reminder:{on:false,time:'07:00'},widgets:{available:true,on,edition,editions:[{id:'breakfast-table',name:'The Breakfast Table'},{id:'little-explorers',name:'The Little Explorer'}],note:'Shows the issue date.'}})}
  window.ReactNativeWebView={postMessage(raw){const m=JSON.parse(raw);window.widgetMessages.push(m);if(m.t==='settings?')setTimeout(settings,20);if(m.t==='widget-save'){on=m.on;edition=m.edition;setTimeout(settings,20)}}};
 });
 await p.goto(base+'parents.html');await p.locator('#np-widget-panel').waitFor({state:'visible'});
 await p.selectOption('#np-widget-edition','little-explorers');assert.equal(await p.locator('.np-gate').isVisible(),false,'Choosing before enabling needs no extra check');
 await p.locator('#np-widget-on').check();await p.locator('.np-gate').waitFor({state:'visible'});
 const saves=()=>p.evaluate(()=>window.widgetMessages.filter(m=>m.t==='widget-save').length);
 assert.equal(await saves(),0);await p.fill('#np-gate-answer','1');await p.click('.np-gate-ok');assert.equal(await saves(),0);
 await p.fill('#np-gate-answer','35');await p.click('.np-gate-ok');await p.waitForFunction(()=>window.widgetMessages.some(m=>m.t==='widget-save'));
 const saved=await p.evaluate(()=>window.widgetMessages.find(m=>m.t==='widget-save'));assert.equal(saved.edition,'little-explorers');assert.equal(saved.on,true);assert.equal(await saves(),1);
 assert.deepEqual(outside,[]);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 console.log('Parent widget setup: one gate when enabling, wrong answers blocked, chosen edition preserved, zero outside requests.');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
