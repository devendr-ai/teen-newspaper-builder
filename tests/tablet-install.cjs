const assert = require('node:assert/strict');
const http = require('node:http');
const {chromium} = require('playwright');
let component = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => component += chunk);
process.stdin.on('end', async () => {
  const html = '<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><header style="height:60px">News Pebbles</header>' + component + '<main>Paper</main>';
  const server = http.createServer((req, res) => {res.setHeader('Content-Type', 'text/html'); res.end(html);});
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true, ...(process.env.CHROME ? {executablePath:process.env.CHROME} : {})});
    const url = `http://127.0.0.1:${server.address().port}/`;
    const ipad = {ua:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Version/18.0 Safari/605.1.15', platform:'MacIntel', touch:5};
    const android = {ua:'Mozilla/5.0 (Linux; Android 14; Tablet) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36', platform:'Linux armv8l', touch:5};
    async function open(device, options={}) {
      const context = await browser.newContext({viewport:options.viewport || {width:1024,height:768}});
      await context.addInitScript(({device, options}) => {
        Object.defineProperty(navigator,'userAgent',{value:device.ua});
        Object.defineProperty(navigator,'platform',{value:device.platform});
        Object.defineProperty(navigator,'maxTouchPoints',{value:device.touch});
        if(options.standalone) Object.defineProperty(navigator,'standalone',{value:true});
        if(options.blockStorage) Object.defineProperty(window,'localStorage',{get(){throw Error('Storage blocked');}});
      }, {device, options});
      const page = await context.newPage();
      const errors = [], requests = [];
      page.on('pageerror', e=>errors.push(e.message)); page.on('request', r=>requests.push(r.url()));
      await page.goto(url);
      return {page, context, errors, requests};
    }
    const bar = '#np-tablet-install';
    for (const device of [
      {ua:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130',platform:'Win32',touch:0},
      {ua:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Safari/605.1',platform:'iPhone',touch:5},
      {ua:'Mozilla/5.0 (Linux; Android 14; Pixel) Mobile Safari/537',platform:'Linux',touch:5}
    ]) {
      const t = await open(device, {viewport:{width:390,height:844}});
      assert.equal(await t.page.locator(bar).isVisible(), false);
      assert.equal(await t.page.locator('main').evaluate(el=>el.offsetTop),68);
      assert.deepEqual(t.errors,[]); await t.context.close();
    }
    const i = await open(ipad);
    assert(await i.page.locator(bar).isVisible());
    assert.equal(await i.page.locator(bar).evaluate(el=>el.getBoundingClientRect().height),44);
    await i.page.locator('[data-install-open]').click();
    assert(await i.page.locator('[data-install-ipad]').isVisible());
    await i.page.locator('[data-installed]').click();
    await i.page.reload(); assert.equal(await i.page.locator(bar).isVisible(),false);
    assert.equal(await i.page.evaluate(()=>localStorage.getItem('np-app-installed')),'true');
    assert.deepEqual(i.errors,[]); assert(i.requests.every(r=>r.startsWith(url))); await i.context.close();
    const dismissed = await open(ipad);
    await dismissed.page.locator('.np-install-dismiss').click(); await dismissed.page.reload();
    assert.equal(await dismissed.page.locator(bar).isVisible(),false);
    await dismissed.page.evaluate(()=>localStorage.setItem('np-app-install-dismissed-until','1'));
    await dismissed.page.reload(); assert(await dismissed.page.locator(bar).isVisible());
    await dismissed.context.close();
    const installed = await open(ipad,{standalone:true});
    assert.equal(await installed.page.locator(bar).isVisible(),false); await installed.context.close();
    const a = await open(android);
    await a.page.locator('[data-install-open]').click(); assert(await a.page.locator('[data-install-android]').isVisible());
    await a.page.keyboard.press('Escape'); await a.context.close();
    const native = await open(android);
    async function offer(outcome) {
      await native.page.evaluate(outcome=>{
        const event = new Event('beforeinstallprompt',{cancelable:true});
        event.prompt = async()=>{window.promptCalls=(window.promptCalls||0)+1;};
        event.userChoice=Promise.resolve({outcome});window.dispatchEvent(event);
      },outcome);
      await native.page.locator('[data-install-open]').click();
    }
    await offer('dismissed'); assert(await native.page.locator(bar).isVisible());
    assert.equal(await native.page.evaluate(()=>localStorage.getItem('np-app-installed')),null);
    await offer('accepted'); await native.page.reload();
    assert.equal(await native.page.locator(bar).isVisible(),false); await native.context.close();
    const event = await open(android);
    await event.page.evaluate(()=>window.dispatchEvent(new Event('appinstalled'))); await event.page.reload();
    assert.equal(await event.page.locator(bar).isVisible(),false); await event.context.close();
    const blocked = await open(ipad,{blockStorage:true});
    await blocked.page.locator('[data-install-open]').click(); await blocked.page.locator('[data-installed]').click();
    assert.equal(await blocked.page.locator(bar).isVisible(),false); assert.deepEqual(blocked.errors,[]);
    await blocked.context.close();
    console.log('Tablet-only display, 44px strip, iPad acknowledgement, 30-day dismissal, Android fallback/native acceptance, standalone and install events passed.');
  } finally {
    if(browser) await browser.close(); await new Promise(resolve=>server.close(resolve));
  }
});
