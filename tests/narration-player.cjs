const assert = require('node:assert/strict');
const vm = require('node:vm');
let source = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => source += chunk);
process.stdin.on('end', async () => {
  const block = source.slice(source.indexOf('  // ---------------------------------------------------------------- read aloud'), source.indexOf('  const main = $(".issue");'));
  function setup({saved = {}, key = 'paper-2026-10-24', audio = true, speechAvailable = true, twoCards = false} = {}) {
    const events = {}, utterances = [], audios = [];
    const node = () => ({attrs:{}, hidden:false, textContent:'', lastChild:{}, handlers:{},
      setAttribute(k,v){this.attrs[k]=v;}, addEventListener(k,fn){this.handlers[k]=fn;},
      getBoundingClientRect(){return {top:500,bottom:530};},
      classList:{add(){},remove(){}}, insertAdjacentHTML(){}});
    const words = ['Original headline.', 'Easier headline.', 'Body.'].map((textContent,index) => {
      const n = node(); n.textContent=textContent; n.hidden=index===1;
      n.closest=()=>n.hidden?{}:null; n.scrollIntoView=()=>{};
      n.classList={add(){n.marked=true;},remove(){n.marked=false;}}; return n;
    });
    const card = Object.assign(node(), {id:'s-lead',dataset:{i:'0'}});
    const cards = [card]; if(twoCards) cards.push(Object.assign(node(),{id:'s-second',dataset:{i:'1'}}));
    const button = node(); button.closest=()=>card;
    const easy = {on:false,getAttribute(){return String(this.on);}};
    const player=node(), prompt=node(), range=node(); prompt.hidden=true;
    const controls = Object.fromEntries(['toggle','restart','close','previous','next','follow'].map(k=>[`[data-listen=${k}]`,node()]));
    const playerNodes={...controls,input:range,'.listen-time':node(),'.listen-title':node(),'.listen-status':node()};
    const tracks={'0':{original:{src:'original.mp3',segments:[{index:0,start:0,end:1},{index:2,start:1,end:2}]},
      easy:{src:'easy.mp3',segments:[{index:1,start:0,end:1},{index:2,start:1,end:2}]}}};
    if(twoCards) tracks['1']={original:{...tracks['0'].original,src:'second.mp3'}};
    class Audio {
      constructor(){audios.push(this);this.currentTime=0;this.duration=2;}
      play(){this.paused=false;return Promise.resolve();}
      pause(){this.paused=true;} load(){} removeAttribute(){}
    }
    const speech={getVoices:()=>[],cancel(){},speak(u){utterances.push(u);}};
    const ctx={assert, Audio:audio?Audio:undefined, utterances,audios,card,cards,button,easy,words,events,player,range,controls,prompt,saved,
      SpeechSynthesisUtterance:function(text){this.text=text;},location:{pathname:'/play/paper/2026-10-24.html'},
      window:{...(speechAvailable?{speechSynthesis:speech}:{}),innerHeight:800,scrollY:50,scrollTo(){},scrollBy(){},addEventListener(k,fn){events[k]=fn;}},navigator:{},
      document:{body:node(),addEventListener(k,fn){events[k]=fn;}},
      store:{get:(k,d)=>k==='rate'?1.2:k==='listening'?saved:d,set(k,v){if(k==='listening'){Object.keys(saved).forEach(k=>delete saved[k]);Object.assign(saved,v);}}},
      award(){},calm:()=>true,
      $:(selector, parent)=>parent===player?playerNodes[selector]:selector==='#narration'?{textContent:JSON.stringify(tracks)}:
        selector==='#listen-player'?player:selector==='#listen-resume'?prompt:selector==='.issue'?{dataset:{key,mode:'scroll'}}:
        selector==='.easy'?easy:selector==='.read'?button:selector==='h2:not([hidden])'?{textContent:'Headline'}:null,
      $$:(selector)=>selector==='.card'?cards:selector==='.s'?words:selector==='.s.now'?words.filter(w=>w.marked):selector==='.read'?[button]:[]};
    vm.createContext(ctx);vm.runInContext(block,ctx);return ctx;
  }
  const run=(ctx,code)=>vm.runInContext(code,ctx);
  const ctx=setup();
  run(ctx,`readCard(card,button); assert.equal(audios[0].src,'original.mp3'); assert.equal(audios[0].playbackRate,1.2);
    audios[0].onloadedmetadata(); audios[0].currentTime=1.5; audios[0].ontimeupdate();
    assert.equal(words[2].marked,true); assert.equal(saved['paper-2026-10-24'].time,1.5);
    assert.equal(range.value,'1.5'); assert.equal(range.max,'2');
    const stale=audios[0].onended;
    readCard(card,button); assert.equal(audios[0].paused,true); assert.equal(reading,card);
    assert.equal(controls['[data-listen=toggle]'].textContent,'Resume');
    toggleListening(); assert.equal(audios[0].paused,false); assert.equal(audios[0].currentTime,1.5);
    stop(); assert.equal(reading,null); assert.equal(prompt.hidden,false);
    readCard(card,button); audios[1].onloadedmetadata(); assert.equal(audios[1].currentTime,1.5);
    stale(); assert.equal(reading,card); // stale completion cannot clear a newer session
    stop(); easy.on=true;words[0].hidden=true;words[1].hidden=false;
    readCard(card,button);audios[2].onloadedmetadata();assert.equal(audios[2].src,'easy.mp3');assert.equal(audios[2].currentTime,0);
    audios[2].onerror();assert.equal(utterances[0].text,'Easier headline.');
    const staleSpeech=utterances[0].onend;toggleListening();staleSpeech();assert.equal(utterances.length,1);
    toggleListening();assert.equal(utterances.length,2);assert.equal(utterances[1].text,'Easier headline.');
    stop();readCard(card,button,true);audios[3].onloadedmetadata();assert.equal(audios[3].currentTime,0);
    audios[3].onended();assert.equal(saved['paper-2026-10-24'],undefined);assert.equal(prompt.hidden,true);`);
  // A fresh page resumes at the saved time, while another edition starts independently.
  const saved={'paper-2026-10-24':{card:'s-lead',variant:'original',src:'original.mp3',time:1.3,sentence:1,updated:1}};
  const restored=setup({saved});
  run(restored,`assert.equal(prompt.hidden,false);readCard(card,button);audios[0].onloadedmetadata();assert.equal(audios[0].currentTime,1.3);
    events.pagehide();assert.equal(saved['paper-2026-10-24'].time,1.3);assert.equal(audios[0].paused,true);`);
  run(setup({saved,key:'paper-2026-10-25'}),`assert.equal(prompt.hidden,true);readCard(card,button);audios[0].onloadedmetadata();assert.equal(audios[0].currentTime,0);`);
  // No speech API is needed for generated audio; browser-only narration saves a sentence boundary.
  run(setup({speechAvailable:false}),`readCard(card,button);assert.equal(audios[0].src,'original.mp3');`);
  const fallback=setup({audio:false});
  run(fallback,`readCard(card,button);utterances[0].onend();assert.equal(utterances[1].text,'Body.');stop();
    readCard(card,button);assert.equal(utterances[2].text,'Body.');`);
  // Seeking while paused changes the saved position without resuming playback.
  run(setup(),`readCard(card,button);audios[0].onloadedmetadata();toggleListening();
    range.handlers.change({target:{value:'1.2'}});assert.equal(audios[0].paused,true);
    assert.equal(saved['paper-2026-10-24'].time,1.2);assert.equal(words[2].marked,true);`);
  // Sentence controls stay paused when skipping, and manual scrolling disables following until requested.
  run(setup(),`readCard(card,button);audios[0].onloadedmetadata();toggleListening();skipSentence(1);
    assert.equal(audios[0].currentTime,1);assert.equal(audios[0].paused,true);assert.equal(words[2].marked,true);
    events.touchmove({target:{closest(){return null;}}});assert.equal(listening.follow,false);
    controls['[data-listen=follow]'].handlers.click();assert.equal(listening.follow,true);
    skipSentence(-1);assert.equal(audios[0].currentTime,0);`);
  // Whole-edition playback reuses the audio element across sections and stops at the end.
  run(setup({twoCards:true}),`readCard(card,button,true,true);audios[0].onloadedmetadata();listening.follow=false;audios[0].onended();assert.equal(listening.follow,false);
    assert.equal(reading,cards[1]);assert.equal(audios.length,1);assert.equal(audios[0].src,'second.mp3');
    audios[0].onloadedmetadata();audios[0].currentTime=1;audios[0].ontimeupdate();assert.equal(saved['paper-2026-10-24'].edition,true);
    audios[0].onended();assert.equal(reading,null);assert.equal(saved['paper-2026-10-24'],undefined);`);
  console.log('Narration: pause/resume, progress, seeking, persistence, edition/version isolation, completion, fallback, and cancellation passed');
});
