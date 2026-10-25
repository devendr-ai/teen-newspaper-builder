const assert = require('node:assert/strict');
const vm = require('node:vm');
let source = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => source += chunk);
process.stdin.on('end', () => {
  const events = {}, snapshots = [], positions = [], focus = [];
  const panels = ['today', 'explore', 'me'].map(id => ({id, hidden:false}));
  const nav = ['mobile','desktop'].flatMap(() => ['home','today','explore','me'].map(view => ({dataset:{view},attrs:{},
    setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}})));
  const badges = {open:false};
  const fig = {};
  const location = {hash:''};
  const stored = {'rp-band':'"Ages 9–11"','rp-read':'["breakfast-table-2026-10-24"]',
    'rp-garden':'["daisy"]','rp-gpos':'{"daisy":[22,33,1]}','rp-badges':'{"first":"2026-10-24"}'};
  const before = JSON.stringify(stored);
  const context = {location, root:{style:{setProperty(){}}}, requestAnimationFrame:fn=>fn(),
    addEventListener:(name,fn)=>events[name]=fn,
    window:{scrollTo:(x,y)=>positions.push([x,y])},
    document:{getElementById:id=>panels.find(p=>p.id===id)||(['stories','map','badges'].includes(id)?{scrollIntoView:()=>positions.push(id)}:null)},
    $:(selector,el)=>selector==='#badges details'?badges:selector==='svg'?{}:selector==='h2'?{focus:()=>focus.push(el.id)}:null,
    $$:selector=>selector==='.lobby-panel'?panels:selector==='.childnav [data-view]'?nav:selector==='.where.wide'?[fig]:[],
    lobbyPins:()=>snapshots.push('map refreshed'),
    localStorage:{getItem:k=>stored[k],setItem(){throw new Error('Navigation must not overwrite progress');},clear(){throw new Error('Must not clear progress');}}
  };
  const block = source.slice(source.indexOf('  function lobbyNavigation()'), source.indexOf("  // ---------------------------------------------------------------- the lobby: who's reading?"));
  assert(block.includes('hashchange'));
  vm.runInNewContext(block+'\nlobbyNavigation();',context);
  function visible(view){assert.deepEqual(panels.filter(p=>!p.hidden).map(p=>p.id),[view]);
    assert.deepEqual(nav.filter(a=>a.attrs['aria-current']==='page').map(a=>a.dataset.view),[view,view]);}
  visible('today');
  for(const [hash,view] of [['#explore','explore'],['#stories','explore'],['#map','explore'],['#me','me'],['#badges','me'],['#today','today'],['#unknown','today']]){
    location.hash=hash;events.hashchange();visible(view);
  }
  assert.equal(badges.open,true);
  assert(positions.includes('map')&&positions.includes('stories')&&positions.includes('badges'));
  assert(snapshots.length>=3);assert(focus.includes('me'));
  assert.equal(JSON.stringify(stored),before);
  console.log('Navigation routes, legacy links, map refresh and saved progress preserved');
});
