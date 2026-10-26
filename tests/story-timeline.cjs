const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME?{executablePath:process.env.CHROME}:{})});
 try{
 for(const width of [390,768,1440]){
  const context=await browser.newContext({viewport:{width,height:900}});
  const page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]+'play/current-affairs-digest/2026-10-26.html');
  page.on('request',r=>requests.push(r.url()));
  const lead=page.locator('#s-lead .follow-thread'),world=page.locator('#s-world .follow-thread');
  assert.equal(await lead.getAttribute('open'),null);assert.equal(await world.getAttribute('open'),null);
  assert(await page.locator('#s-lead').isVisible());assert(await page.locator('#s-world').isVisible());
  const order=await page.locator('#read>.card').evaluateAll(cards=>cards.map(c=>c.id));
  await lead.locator(':scope > summary').click();await lead.locator('[data-thread-index="0"]').click();
  assert.equal(await lead.locator('[data-thread-index="0"]').getAttribute('aria-pressed'),'true');
  const date=await lead.locator('.thread-entry:not([hidden])').getAttribute('data-thread-date');
  const read=lead.locator('.thread-entry:not([hidden]) [data-thread-read]');
  await read.scrollIntoViewIfNeeded();const readingY=await page.evaluate(()=>scrollY);
  await read.click();
  assert(await lead.locator('.thread-entry:not([hidden]) [data-thread-report]').isVisible());
  assert(await page.evaluate(()=>document.querySelector('.thread-entry:not([hidden]) [data-thread-report]').getBoundingClientRect().top >= document.querySelector('header.bar').getBoundingClientRect().bottom));
  const report=lead.locator('.thread-entry:not([hidden]) [data-thread-report]');
  const fontBefore=await report.evaluate(el=>parseFloat(getComputedStyle(el).fontSize));
  await page.locator('[data-act="bigger"]').click();
  assert(await report.evaluate(el=>parseFloat(getComputedStyle(el).fontSize))>fontBefore,'Original report ignored bigger text');
  await page.locator('[data-act="smaller"]').click();
  await lead.locator('.thread-entry:not([hidden]) [data-thread-return]').first().click();
  assert(Math.abs(await page.evaluate(()=>scrollY)-readingY)<2,'Did not restore the reading position');
  assert.equal(await lead.locator('.thread-entry:not([hidden])').getAttribute('data-thread-date'),date);
  assert.equal(await lead.locator('.thread-entry:not([hidden]) [data-thread-report]').isVisible(),false);
  // Scrolling to later stories doesn't navigate, hide the first, or open the second thread automatically.
  await page.locator('#s-world').scrollIntoViewIfNeeded();assert.equal(await world.getAttribute('open'),null);
  await world.locator(':scope > summary').click();await world.locator('[data-thread-index="0"]').click();
  assert.equal(await lead.locator('.thread-entry:not([hidden])').getAttribute('data-thread-date'),date);
  await world.locator('[data-thread-next]').click();
  await world.locator('[data-thread-index="0"]').press('ArrowRight');
  assert.equal(await world.locator('[data-thread-index="2"]').getAttribute('aria-pressed'),'true');
  await world.locator('[data-thread-close]').click();
  assert.equal(await world.getAttribute('open'),null);
  assert.deepEqual(await page.locator('#read>.card').evaluateAll(cards=>cards.map(c=>c.id)),order);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert(requests.every(url=>url.startsWith(process.argv[2])),'Timeline made an outside request');
  await page.reload();await lead.locator(':scope > summary').click();
  assert.equal(await lead.locator('.thread-entry:not([hidden])').getAttribute('data-thread-date'),date);
  assert.equal(await world.getAttribute('open'),null);
  assert.deepEqual(errors,[]);
  console.log(width+': independent lead/secondary timelines, original reports, return position, keyboard, persistence and continuous scroll passed');
  await context.close();
 }
 // A horizontal touch gesture on a timeline must not turn the younger reader's story card.
 const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
 const page=await context.newPage();await page.goto(process.argv[2]+'play/breakfast-table/2026-10-26.html');
 const thread=page.locator('#s-lead .follow-thread');await thread.locator(':scope > summary').click();
 const before=await page.locator('#read>.card.on').getAttribute('id');
 await thread.locator('.thread-rail').evaluate(rail=>{
   const start=new Event('touchstart',{bubbles:true});Object.defineProperty(start,'touches',{value:[{clientX:250}]});rail.dispatchEvent(start);
   const end=new Event('touchend',{bubbles:true});Object.defineProperty(end,'changedTouches',{value:[{clientX:50}]});rail.dispatchEvent(end);
 });
 assert.equal(await page.locator('#read>.card.on').getAttribute('id'),before);
 await context.close();
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
