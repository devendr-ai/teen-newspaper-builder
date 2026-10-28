// Usage: NODE_PATH=... CHROME=... node tools/weekend_check.cjs http://localhost:8000
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME,headless:true});
 try{
  for(const width of [390,820,1440]){
   const context=await browser.newContext({viewport:{width,height:950}});
   const page=await context.newPage();
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(process.argv[2]+'/');
   await page.locator('.agebar button[data-v="Ages 6–8"]').click();
   const card=page.locator('.recommended[data-edition="little-explorers"]');
   assert.equal(await card.isVisible(),true);
   await card.locator('input[value=puzzles]').check();
   assert.match(await card.locator('[data-weekend-pdf]').getAttribute('href'),/-puzzles.pdf$/);
   assert.match(await card.locator('.weekend-note').innerText(),/^3 pages/);
   const bounds=await card.locator('.weekend-choice').boundingBox();
   assert.ok(bounds.x>=0 && bounds.x+bounds.width<=width+1,'chooser fits viewport');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.screenshot({path:'/private/tmp/np-weekend-home-'+width+'.png',fullPage:true});
   await page.goto(process.argv[2]+'/e/little-explorers/index.html');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'archive fits viewport');
   assert.equal(await page.locator('input[value=puzzles]').first().isChecked(),true);
   await page.locator('input[value=news]').first().check();
   for(const href of await page.locator('[data-weekend-pdf]').evaluateAll(a=>a.map(x=>x.href)))assert.ok(!href.endsWith('-puzzles.pdf'));
   await page.goto(process.argv[2]+'/e/little-explorers/2026-10-24.html');
   await page.locator('input[value=puzzles]').check();
   assert.match(await page.locator('[data-weekend-pdf]').getAttribute('href'),/-puzzles.pdf$/);
   await page.screenshot({path:'/private/tmp/np-weekend-'+width+'.png',fullPage:true});
   assert.deepEqual(errors,[]);await context.close();
   console.log(width+'px: choice, persistence, PDF links, sync and layout passed');
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
