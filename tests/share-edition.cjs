const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const script=fs.readFileSync(0,'utf8').replace(/^<script>\s*|\s*<\/script>$/g,'');
async function run(navigator){
 let click;const status={textContent:''},input={hidden:true,value:'',focus(){this.focused=true},select(){this.selected=true}},box={hidden:true,querySelector:s=>s==='input'?input:status};
 const link={href:'https://newspebbles.com/e/little-explorers/2026-10-24.html',dataset:{shareTitle:'The Little Explorer · Ages 6–8 · 2026-10-24'},closest:()=>({nextElementSibling:box})};
 vm.runInNewContext(script,{document:{addEventListener:(event,fn)=>{click=fn}},navigator});
 let prevented=false;await click({target:{closest:()=>link},preventDefault(){prevented=true}});
 return {status,input,box,link,prevented};
}
(async()=>{
 let shared,copied;let r=await run({share:async data=>{shared=data},clipboard:{writeText:async url=>{copied=url}}});
 assert.equal(shared.url,r.link.href);assert.match(shared.title,/6–8/);assert.equal(copied,undefined);assert.equal(r.box.hidden,true);assert.equal(r.prevented,true);
 r=await run({share:async()=>{throw {name:'AbortError'}},clipboard:{writeText:async()=>{throw Error('Must not copy after cancellation')}}});assert.equal(r.box.hidden,true);assert.equal(r.input.value,'');
 r=await run({clipboard:{writeText:async url=>{copied=url}}});assert.equal(copied,r.link.href);assert.match(r.status.textContent,/copied/);assert.equal(r.box.hidden,false);assert.equal(r.input.hidden,true);
 r=await run({share:async()=>{throw Error('Unavailable')},clipboard:{writeText:async()=>{throw Error('Permission denied')}}});assert.equal(r.input.value,r.link.href);assert.equal(r.input.hidden,false);assert.equal(r.input.focused,true);assert.equal(r.input.selected,true);
 r=await run({});assert.equal(r.input.value,r.link.href);assert.equal(r.box.hidden,false);
 console.log('Native sharing, cancellation, exact edition links, clipboard and manual fallback passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
