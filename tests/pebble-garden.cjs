const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(0,'utf8');
const start=source.indexOf('  const ITEMS ='),end=source.indexOf('  // Moving things around the garden:');
assert(start>=0&&end>start);
const data={band:'Ages 9–11',garden:['daisy','tree','rabbit'],gpos:{daisy:[22,33,1],tree:[40,20,2]},peb:200,spent:0};
const original=JSON.stringify(data.gpos),events={},corner={innerHTML:''},badges={hidden:false,attrs:{},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]}},details={open:false},focus=[];
const store={get(k,d){return Object.hasOwn(data,k)?JSON.parse(JSON.stringify(data[k])):d},set(k,v){data[k]=JSON.parse(JSON.stringify(v))}};
const ctx={store,WD:null,esc:x=>String(x),count:()=>0,ymd:()=> '2026-10-26',streak:()=>0,tower:()=>'',levelHtml:()=>'',skill:()=>({l:0}),toast1:()=>{},earn:()=>{},addTo:()=>{},grownUp:()=>/12–14|15\+/.test(data.band),pebbles:()=>data.peb-data.spent,
 $:s=>s==='#corner'?corner:s==='#badges'?badges:s==='#badges details'?details:s.startsWith('#pebble-tab-')||s.startsWith('[data-buy=')?{focus:()=>focus.push(s)}:null,$$:()=>[],requestAnimationFrame:fn=>fn(),addEventListener:()=>{},document:{addEventListener:(type,fn)=>{(events[type]??=[]).push(fn)}}};
vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
function html(){return vm.runInContext('gardenHtml()',ctx)}
function click(type,value){const target={closest:s=>s===type?{dataset:value}:null};for(const fn of events.click)fn({target});}
vm.runInContext('corner()',ctx);
assert(!corner.innerHTML.includes('role="tablist"'),'Young readers keep their existing garden view');assert(corner.innerHTML.includes('My Pebble Garden'));assert.equal(badges.hidden,false);
assert(html().includes('data-g="daisy"'));assert(html().includes('left:22%;top:33%'));assert.equal(JSON.stringify(data.gpos),original);
click('[data-buy]',{buy:'daisy'});click('[data-buy]',{buy:'daisy'});
assert.equal(data.garden.filter(x=>x==='daisy').length,3);assert.equal(data.spent,6);assert(html().includes('data-g="daisy:2"'));assert(html().includes('data-g="daisy:3"'));assert(html().includes('3 in your garden · Buy another'));assert(html().includes('data-g="rabbit"'));assert.equal(JSON.stringify(data.gpos),original);
click('[data-buy]',{buy:'unicorn'});click('[data-buy]',{buy:'unicorn'});assert.equal(data.spent,106);assert.equal(data.garden.filter(x=>x==='unicorn').length,2);
assert.equal(vm.runInContext('Math.max(...ITEMS.map(x=>x[3]))',ctx),50);assert(vm.runInContext('ITEMS.length',ctx)>20);
data.peb=108;const before=JSON.stringify(data);click('[data-buy]',{buy:'daisy'});assert.equal(JSON.stringify(data),before,'Insufficient balance cannot spend or add an item');click('[data-buy]',{buy:'unknown'});assert.equal(JSON.stringify(data),before);
data.peb=109;click('[data-buy]',{buy:'daisy'});assert.equal(data.spent,109);assert.equal(ctx.pebbles(),0);assert.match(html(),/data-buy="daisy" class="have" disabled/);
data.band='Ages 12–14';vm.runInContext('corner()',ctx);let h=corner.innerHTML;assert(h.indexOf('Reading progress')<h.indexOf('>Badges<')&&h.indexOf('>Badges<')<h.indexOf('My garden'));assert(h.includes('📈 My progress'));assert.equal(badges.hidden,true);
click('[data-pebble-view]',{pebbleView:'badges'});assert.equal(badges.hidden,false);assert.equal(details.open,true);assert(corner.innerHTML.includes('class="pebble-panel" role="tabpanel" aria-labelledby="pebble-tab-badges" hidden'));
click('[data-pebble-view]',{pebbleView:'garden'});assert(corner.innerHTML.includes('My Pebble Garden'));assert.equal(badges.hidden,true);
vm.runInContext('corner()',ctx);assert(corner.innerHTML.includes('My Pebble Garden'),'Purchases preserve the selected garden tab');
const arrow=events.keydown[0];let prevented=false;arrow({key:'ArrowRight',target:{closest:()=>({dataset:{pebbleView:'garden'}})},preventDefault(){prevented=true}});assert(prevented);assert(corner.innerHTML.includes('📈 My progress'));
data.band='Ages 15+';vm.runInContext('corner()',ctx);assert(corner.innerHTML.includes('Reading progress'));
data.band='Ages 6–8';vm.runInContext('corner()',ctx);assert(!corner.innerHTML.includes('role="tablist"'));assert.equal(badges.hidden,false);assert.equal(badges.attrs.role,undefined);
// Each duplicate moves independently, and old saved positions keep working.
const move=source.slice(source.indexOf('  function gplace('),source.indexOf('  let drag = null;'));
vm.runInContext(move,ctx);
const el={dataset:{g:'daisy:2'},style:{},offsetWidth:30,offsetHeight:30,parentElement:{clientWidth:300,clientHeight:140}};
ctx.el=el;vm.runInContext('gsave(el,gplace(el,98,98))',ctx);assert(data.gpos['daisy:2'][0]<=90&&data.gpos['daisy:2'][1]<=79);assert.deepEqual(data.gpos.daisy,[22,33,1]);assert.deepEqual(data.gpos.tree,[40,20,2]);
console.log('Garden regressions passed: legacy positions/prizes, repeat purchases, 50-pebble items, insufficient balance, age-specific tabs, keyboard access and independent movement.');
