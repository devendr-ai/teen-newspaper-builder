const assert = require('node:assert/strict');
const vm = require('node:vm');
let source='';
process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>source+=chunk);
process.stdin.on('end',()=>{
 const {controls,reader}=JSON.parse(source);
 const script=controls.match(/<script>([\s\S]*?)<\/script>/)[1];
 function setup(blocked=false){
  const values=new Map([['rp-band','"Ages 9–11"'],['rp-listening','saved audio position'],['rp-garden','garden'],
    ['rp-badges','badges'],['rp-name','Sample'],['np-nocount','1'],['ygc-issue-my-paper','design counter'],['unrelated','keep']]);
  const nodes=Object.fromEntries(['reading-reset','reading-reset-confirm','reading-reset-yes','reading-reset-cancel','reading-reset-status'].map(id=>[id,
    {hidden:id==='reading-reset-confirm',textContent:'',handlers:{},addEventListener(e,f){this.handlers[e]=f;},focus(){this.focused=true;}}]));
  const storage={get length(){if(blocked)throw Error('Storage unavailable');return values.size;},key:i=>[...values.keys()][i],
    removeItem:k=>values.delete(k),setItem:(k,v)=>values.set(k,v),getItem:k=>values.get(k)||null};
  const ctx={localStorage:storage,document:{getElementById:id=>nodes[id]}};
  vm.runInNewContext(script,ctx);return {nodes,values,ctx};
 }
 const {nodes:n,values}=setup();const before=[...values];
 n['reading-reset'].handlers.click();assert.equal(n['reading-reset-confirm'].hidden,false);assert.deepEqual([...values],before);
 n['reading-reset-cancel'].handlers.click();assert.equal(n['reading-reset-confirm'].hidden,true);assert.deepEqual([...values],before);
 n['reading-reset'].handlers.click();n['reading-reset-yes'].handlers.click();
 assert.equal([...values.keys()].some(k=>k.startsWith('rp-')),false);
 assert.equal(values.get('np-nocount'),'1');assert.equal(values.get('ygc-issue-my-paper'),'design counter');assert.equal(values.get('unrelated'),'keep');
 assert(values.has('np-reading-reset'));assert.match(n['reading-reset-status'].textContent,/Reading data reset/);
 const blocked=setup(true);blocked.nodes['reading-reset'].handlers.click();blocked.nodes['reading-reset-yes'].handlers.click();
 assert.match(blocked.nodes['reading-reset-status'].textContent,/could not be cleared/);assert.equal(blocked.nodes['reading-reset'].hidden,false);
 // Open readers must stop and reload, without old callbacks recreating cleared progress.
 const events={},sent=[];let reloads=0;
 const rootBlock=reader.slice(reader.indexOf('  const store ='),reader.indexOf('  const SELF ='));
 const ctx={localStorage:{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)},
   window:{addEventListener:(k,f)=>events[k]=f},document:{dispatchEvent:e=>sent.push(e.type)},
   Event:function(type){this.type=type;},location:{reload(){reloads++;}}};
 vm.createContext(ctx);vm.runInContext(rootBlock,ctx);
 events.storage({key:'unrelated',newValue:'test'});assert.equal(reloads,0);
 events.storage({key:'np-reading-reset',newValue:'123'});assert.equal(reloads,1);assert.deepEqual(sent,['rp-reading-reset']);
 vm.runInContext('store.set("listening", {old:true});',ctx);assert.equal(values.has('rp-listening'),false);
 console.log('Reading reset: confirmation, cancellation, scoped deletion, preserved preferences, storage failure and open-reader reset passed');
});
