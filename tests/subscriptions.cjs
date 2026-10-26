const assert=require('node:assert/strict');
const vm=require('node:vm');
let source='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>source+=chunk);
process.stdin.on('end',async()=>{
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1];
 function node(extra={}){return {value:'',hidden:false,textContent:'',attrs:{},handlers:{},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];},focus(){this.focused=true;},addEventListener(k,f){this.handlers[k]=f;},...extra};}
 function setup({kids=false,gate,selector=false,url='https://newspebbles.com/',valid=true,response,missing=false}={}){
  let timerCallback;
  const calls=[],historyCalls=[],fields=node({disabled:true}),button=node(),status=node(),error=node(),question=node(),share=node();
  const items={email:node({value:'parent@example.com'}),edition_slug:node({tagName:selector?'SELECT':'INPUT',value:'little-explorers',options:[{value:'little-explorers'},{value:'breakfast-table'}],selectedOptions:[{dataset:{shareUrl:'https://wa.me/?text=dated-issue'}}]}),cadence:node({value:'every_issue'}),website:node(),grownup_answer:node()};
  const form=node({dataset:{subscribeEndpoint:'https://subscribe.newspebbles.com/api/subscribe',subscribeKids:String(kids)},elements:{namedItem:k=>items[k]},reportValidity:()=>valid,
   querySelector:s=>({'.subscription-fields':fields,'button[type="submit"]':button,'.subscription-status':status,'.subscription-error':error,'[data-math-question]':question})[s],
   closest:()=>({querySelector:()=>share})});
  const confirmed=node({hidden:true}),removed=node({hidden:true}),dismiss=node(),banner=node({hidden:true,querySelector:s=>({'[data-subscription-confirmed]':confirmed,'[data-subscription-unsubscribed]':removed,'.subscription-dismiss':dismiss})[s]});
  const math=Object.create(Math);math.random=()=>0; // 12 × 3 = 36
  const ctx={window:{npGate:gate},document:{querySelectorAll:()=>missing?[]:[form],querySelector:()=>banner},Math:math,URL,location:{href:url},history:{replaceState:(...args)=>historyCalls.push(args)},AbortController,setTimeout:(fn,ms)=>{assert.equal(ms,20000);timerCallback=fn;return 1;},clearTimeout:()=>{},
   fetch:async(url,options)=>{calls.push({url,options});return response?response(options):{ok:true,status:202,json:async()=>({ok:true})};}};
  vm.runInNewContext(script,ctx);
  return {timeout:()=>timerCallback(),calls,items,form,fields,button,status,error,question,share,confirmed,removed,dismiss,banner,historyCalls,submit:()=>form.handlers.submit({preventDefault(){}})};
 }
 let f=setup();assert.equal(f.calls.length,0);assert.equal(f.fields.disabled,false);assert.equal(f.question.textContent,'12 × 3 = ?');assert.equal(f.banner.hidden,true);
 await f.submit();assert.equal(f.calls.length,0);assert.match(f.error.textContent,/grown-up/);assert.equal(f.items.grownup_answer.focused,true);
 f.items.grownup_answer.value='35';await f.submit();assert.equal(f.calls.length,0);
 f.items.grownup_answer.value='36';await f.submit();assert.equal(f.calls.length,1);assert.equal(f.calls[0].options.credentials,'omit');assert.equal(f.calls[0].options.redirect,'error');
 assert.deepEqual(JSON.parse(f.calls[0].options.body),{email:'parent@example.com',edition_slug:'little-explorers',cadence:'every_issue',website:''});
 assert.match(f.status.textContent,/Check your inbox to confirm/);assert.equal(f.items.email.value,'');assert.equal(f.items.grownup_answer.value,'');assert.equal(f.button.disabled,false);assert.equal(f.form.attrs['aria-busy'],undefined);
 f=setup({valid:false});f.items.grownup_answer.value='36';await f.submit();assert.equal(f.calls.length,0);
 for(const status of [400,429,503]){f=setup({response:()=>({ok:false,status})});f.items.grownup_answer.value='36';await f.submit();assert.equal(f.calls.length,1);assert.ok(f.error.textContent);assert.equal(f.status.textContent,'');assert.equal(f.button.disabled,false);}
 f=setup({response:()=>{throw Error('offline');}});f.items.grownup_answer.value='36';await f.submit();assert.match(f.error.textContent,/connection/);assert.equal(f.button.disabled,false);
 f=setup({response:options=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('timed out'))))});f.items.grownup_answer.value='36';const timed=f.submit();f.timeout();await timed;assert.match(f.error.textContent,/connection/);assert.equal(f.button.disabled,false);
 // Multiple forms never share a math-answer authorization or personal values.
 const other=setup();await other.submit();assert.equal(other.calls.length,0);
 // A future global capture gate can cancel this event before our handler runs.
 f=setup();f.items.grownup_answer.value='36';await f.form.handlers.submit({defaultPrevented:true,preventDefault(){}});assert.equal(f.calls.length,0);
 let release;f=setup({response:()=>new Promise(resolve=>release=resolve)});f.items.grownup_answer.value='36';const pending=f.submit();assert.equal(f.button.disabled,true);assert.equal(f.form.attrs['aria-busy'],'true');await f.submit();assert.equal(f.calls.length,1);release({ok:true,status:202,json:async()=>({ok:true})});await pending;assert.equal(f.button.disabled,false);
 f=setup({selector:true});assert.equal(f.calls.length,0);f.items.edition_slug.selectedOptions=[{dataset:{shareUrl:'https://wa.me/?text=second-issue'}}];f.items.edition_slug.handlers.change();assert.equal(f.share.href,'https://wa.me/?text=second-issue');assert.equal(f.calls.length,0);f.items.edition_slug.selectedOptions=[{dataset:{}}];f.items.edition_slug.handlers.change();assert.equal(f.share.hidden,true);
 for(const flag of ['subscribed','unsubscribed']){f=setup({missing:true,url:`https://newspebbles.com/?${flag}=true&other=keep#age`});assert.equal(f.calls.length,0);assert.equal(f.banner.hidden,false);assert.equal(flag==='subscribed'?f.confirmed.hidden:f.removed.hidden,false);f.dismiss.handlers.click();assert.equal(f.banner.hidden,true);const url=new URL(f.historyCalls[0][2]);assert.equal(url.searchParams.has(flag),false);assert.equal(url.searchParams.get('other'),'keep');assert.equal(url.hash,'#age');}
 for(const requested of ['breakfast-table','unknown','<script>']){f=setup({selector:true,url:'https://newspebbles.com/parents.html?edition='+encodeURIComponent(requested)});assert.equal(f.items.edition_slug.value,requested==='breakfast-table'?'breakfast-table':'little-explorers');assert.equal(f.calls.length,0);}
 f=setup({missing:true,url:'https://newspebbles.com/?subscribed=false'});assert.equal(f.banner.hidden,true);assert.equal(f.calls.length,0);
 f=setup({kids:true});f.items.grownup_answer.value='36';await f.submit();assert.equal(f.calls.length,0);assert.match(f.error.textContent,/grown-up check/);
 let grant,cancel;f=setup({kids:true,gate:(reason,yes,no)=>{assert.equal(reason,'link');grant=yes;cancel=no;}});f.items.grownup_answer.value='36';const gated=f.submit();assert.equal(f.calls.length,0);await f.submit();assert.equal(f.calls.length,0);grant();await gated;assert.equal(f.calls.length,1);
 f=setup({kids:true,gate:(reason,yes,no)=>{cancel=no;}});f.items.grownup_answer.value='36';const cancelled=f.submit();cancel();await cancelled;assert.equal(f.calls.length,0);
 console.log('Subscription UI: zero initial requests, scoped math gate, future gate cancellation, minimal payload, loading/double-submit, errors, share changes and banners passed.');
});
