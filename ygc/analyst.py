"""Source-grounded, online-only analyst challenges for readers aged 12+."""
import base64
import hashlib
import json
import os
import re

from . import edition

ROOT = os.path.join(edition.ROOT, 'data', 'analyst')
PROMPT = '''**Analyst challenges (12+, online only).** `play.analyst` replaces the older reader's word-match and fact-or-fiction games when suitable content exists. Use `domino` and `call` independently; set a mode to null if this issue cannot support it. Never manufacture a dilemma or causal chain just to fill a slot.
`domino`: {story, question, qualification, steps:[{text,evidence}], links:[{why,evidence}]}. Exactly four different short steps in the correct causal order and three explanations of the arrows. Every evidence is a 5–45 word EXACT passage from the linked story's body/deck/why/connect/analyst. Every arrow must actually be supported, not merely chronologically adjacent. Qualification states assumptions and uncertainty; distinguish claims, risks and confirmed outcomes. Keep each step at most 18 words and explanations at most 60 words.
`call`: {story, question, premise, evidence, framing, options:[{label,benefit,cost}], reflection}. Link the lead story. Evidence is a 5–45 word EXACT passage from it supporting the factual premise. Pose a real policy trade-off raised by that story. If the options are proposed for learning rather than reported policy choices, framing MUST say 'Hypothetical decision based on this story'. Both options must be defensible and fairly worded, with a benefit and a cost each (at most 45 words each). Do not imply officials proposed an option unless the story says so. Neither choice is correct; don't invent poll results. reflection asks what evidence could change a reader's decision. Ages 12–14 use brief concrete language; 15+ can explore uncertainty and competing constraints. Facts and explanations must be checked against the issue and research pool.'''


def wants(ed):
    from .skeleton import reader_age
    return reader_age(ed) >= 12


def source_text(issue, bid):
    b = issue.get('blocks', {}).get(bid, {})
    return ' '.join([str(b.get('deck', '')), *b.get('body', []), *[str(b.get(k, '')) for k in ('why','connect','analyst')]])


def errors(issue, value):
    out=[]
    if not isinstance(value, dict):return ['play.analyst must be an object']
    def text(d,k,n,at):
        v=d.get(k)
        if not isinstance(v,str) or not v.strip() or len(v.split())>n or re.search(r'<|>|https?://',v):
            out.append(f'{at}.{k}: plain nonempty text, at most {n} words');return ''
        return v
    def evidence(d,source,at):
        v=text(d,'evidence',45,at)
        if len(v.split())<5 or ' '.join(v.split()) not in ' '.join(source.split()):out.append(f'{at}.evidence: quote 5–45 words exactly from the linked story')
    for mode in ('domino','call'):
        d=value.get(mode)
        if d is None:continue
        at='play.analyst.'+mode
        if not isinstance(d,dict):out.append(at+' must be an object or null');continue
        bid=d.get('story');b=issue.get('blocks',{}).get(bid,{})
        if not isinstance(b,dict) or not isinstance(b.get('body'),list) or not b.get('headline'):
            out.append(at+'.story: link a news story');continue
        source=source_text(issue,bid)
        text(d,'question',45,at)
        if mode=='domino':
            text(d,'qualification',60,at)
            steps=d.get('steps');links=d.get('links')
            if not isinstance(steps,list) or len(steps)!=4:out.append(at+'.steps: exactly four steps');continue
            if not isinstance(links,list) or len(links)!=3:out.append(at+'.links: exactly three causal explanations');continue
            labels=[]
            for i,s in enumerate(steps):
                if not isinstance(s,dict):out.append(at+'.steps: objects required');continue
                labels.append(text(s,'text',18,at+f'.steps[{i}]').casefold());evidence(s,source,at+f'.steps[{i}]')
            if len(set(labels))!=4:out.append(at+'.steps: four different steps')
            for i,s in enumerate(links):
                if not isinstance(s,dict):out.append(at+'.links: objects required');continue
                text(s,'why',60,at+f'.links[{i}]');evidence(s,source,at+f'.links[{i}]')
        else:
            if bid!='lead':out.append(at+'.story: use the lead story')
            evidence(d,source,at)
            for k,n in [('premise',75),('framing',35),('reflection',45)]:text(d,k,n,at)
            options=d.get('options')
            if not isinstance(options,list) or len(options)!=2:out.append(at+'.options: exactly two options');continue
            labels=[]
            for i,s in enumerate(options):
                if not isinstance(s,dict):out.append(at+'.options: objects required');continue
                labels.append(text(s,'label',12,at+f'.options[{i}]').casefold())
                for k in ('benefit','cost'):text(s,k,45,at+f'.options[{i}]')
            if len(set(labels))!=2:out.append(at+'.options: different labels')
    return out


def get(ed, issue):
    if not wants(ed):return {}
    value=(issue.get('play') or {}).get('analyst')
    if value is None:
        path=os.path.join(ROOT,ed['id'],str(issue.get('date'))+'.json')
        if os.path.isfile(path):
            try:
                with open(path,encoding='utf-8') as f:value=json.load(f)
            except (OSError,ValueError):return {}
    if value is None or errors(issue,value):return {}
    return value


def poll_id(ed,issue,call):
    raw=json.dumps(call,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    return f"{ed['id']}:{issue['date']}:"+hashlib.sha256(raw.encode()).hexdigest()[:24]


def reader_data(ed, issue, at):
    value=get(ed,issue)
    result={}
    for mode,d in value.items():
        if mode not in ('domino','call') or not isinstance(d,dict):continue
        d=dict(d,card=at.get(d['story'],-1))
        if mode=='domino':
            d['steps']=[{'text':s['text']} for s in d['steps']]
            d['links']=[{'why':s['why']} for s in d['links']]
        else:
            d['poll_id']=poll_id(ed,issue,value['call'])
        d.pop('evidence',None)
        result[mode]=d
    return result


def endpoint(cfg):
    from urllib.parse import urlsplit
    base=(cfg.get('analyst_games') or {}).get('api_base_url','')
    try:
        u=urlsplit(base)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:return ''
    except (TypeError,ValueError):return ''
    return base64.b64encode((base.rstrip('/')+'/api/polls/vote').encode()).decode()


CSS = '''
.analyst-chain{list-style:none;padding:0;display:grid;gap:10px}.analyst-chain li{display:grid;grid-template-columns:24px 1fr auto;gap:10px;align-items:center;border:1px solid var(--line);border-radius:12px;padding:10px;background:var(--bg)}
.analyst-movers{display:flex;gap:5px}.analyst-movers button{min-width:44px;min-height:44px;padding:6px}.analyst-actions{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.analyst-tradeoffs{display:grid;gap:12px}.analyst-tradeoffs section{border-top:1px solid var(--line);padding-top:10px}.game .opts button[data-call-choice][aria-pressed=true]{border-color:var(--teal);background:var(--leaf-t)}
.menu button.analyst-new{border-color:var(--teal);background:color-mix(in srgb,var(--teal) 10%,var(--card))}.analyst-new-tag{margin-left:auto;color:var(--teal);font-size:12px;font-weight:bold}.analyst-movers button{border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}.analyst-results{margin:18px 0}.analyst-result-label{display:flex;justify-content:space-between;gap:14px}.analyst-result-track{height:8px;background:var(--line);border-radius:6px;overflow:hidden;margin:5px 0 12px}.analyst-result-track span{display:block;height:100%;background:var(--teal)}
@media(max-width:480px){.analyst-movers{flex-direction:column}.analyst-chain li{gap:7px}.analyst-chain .analyst-step{font-size:.95em}}
'''

# Inserted inside play.js's existing game closure, so rewards, local storage,
# reading links and age handling remain shared with the existing games.
JS = r'''
  const completed = (g) => g.id === "call" ? store.get("done-" + key + "-call", false) : best(g.id) > 0;
  function analystDomino() {
    const d = data.analyst.domino, g = {id:"domino",run:analystDomino};
    let ids = shuffle([0,1,2,3]), tries=0, shown=false, finished=false;
    if(ids.every((v,i)=>v===i))ids.push(ids.shift());
    function draw(message="") {
      box.innerHTML = `${back()}<h2>Domino Effect</h2><p class="q">${esc(d.question)}</p><p class="how">${esc(d.qualification)}</p><p>Drag the four steps, or use the up/down buttons.</p>
      <ol class="analyst-chain">${ids.map((n,i)=>`<li draggable="${!finished}" data-pos="${i}"><b>${i+1}</b><span class="analyst-step">${esc(d.steps[n].text)}</span>${finished?"":`<span class="analyst-movers"><button type="button" data-move="${i},-1" aria-label="Move ${esc(d.steps[n].text)} earlier" ${i===0?"disabled":""}>↑</button><button type="button" data-move="${i},1" aria-label="Move ${esc(d.steps[n].text)} later" ${i===3?"disabled":""}>↓</button></span>`}</li>`).join("")}</ol>
      <p class="fb" role="status">${esc(message)}</p>${finished?`<div class="analyst-links">${d.links.map((l,i)=>`<p><b>${i+1} → ${i+2}:</b> ${esc(l.why)}</p>`).join("")}</div><div class="analyst-finish"></div>`:`<div class="analyst-actions"><button type="button" class="big go" data-chain-check>Check my chain</button><button type="button" class="big" data-chain-show>Explain the chain</button></div>`}${readAgain(d.card)}`;
      wireBack();
      function move(from,to){if(finished||from<0||from>3||to<0||to>3||from===to)return;const [n]=ids.splice(from,1);ids.splice(to,0,n);draw();$(`[data-pos="${to}"] button:not(:disabled)`,box)?.focus({preventScroll:true});}
      $$("[data-move]",box).forEach(b=>b.onclick=()=>{const [i,v]=b.dataset.move.split(",").map(Number);move(i,i+v);});
      let dragged=null;
      $$("[draggable]",box).forEach(li=>{li.ondragstart=e=>{dragged=+li.dataset.pos;e.dataTransfer.setData("text/plain",String(dragged));};li.ondragover=e=>e.preventDefault();li.ondrop=e=>{e.preventDefault();if(dragged!==null)move(dragged,+li.dataset.pos);};});
      const finish=(reveal)=>{tries++;markTried();const ok=ids.every((n,i)=>n===i);if(!ok&&!reveal){hinted();draw("Not quite. Check which step causes the next one, rather than just happening near it.");return;}shown=reveal;if(reveal){ids=[0,1,2,3];hinted();}finished=true;logAnswer(d.card,ok&&tries===1&&!shown,{q:d.question,a:d.steps.map(s=>s.text).join(" → "),why:d.qualification});const rewards=keep("domino",shown?1:tries===1?3:2);draw(shown?"Here is the supported chain, with an explanation of each link.":"Chain complete. Here is why each link belongs here.");$(".analyst-finish",box).innerHTML=rewards;};
      $("[data-chain-check]",box)?.addEventListener("click",()=>finish(false));$("[data-chain-show]",box)?.addEventListener("click",()=>finish(true));
    }
    draw();
  }
  function analystCall(){
    const d=data.analyst.call;
    const saved=store.get("call-choice-"+d.poll_id,null);
    let choice=(saved===0||saved===1)?saved:null,busy=false,receipt=null;
    box.innerHTML=`${back()}<h2>You Make the Call</h2><p class="q">${esc(d.question)}</p><p>${esc(d.premise)}</p><p class="how">${esc(d.framing)}</p><div class="opts">${d.options.map((o,i)=>`<button type="button" data-call-choice="${i}" aria-pressed="${choice===i}">${esc(o.label)}</button>`).join("")}</div><div class="analyst-response" aria-live="polite"></div>${readAgain(d.card)}`;wireBack();
    function reveal(){
      if(choice===null)return;
      $$("[data-call-choice]",box).forEach(b=>b.setAttribute("aria-pressed",String(+b.dataset.callChoice===choice)));
      const first=!store.get("done-"+key+"-call",false);store.set("done-"+key+"-call",true);firstGo=false;
      // Reflection counts as completion, never as a correct/incorrect answer or stars.
      const rewards=first?keep("call",0):"";
      $(".analyst-response",box).innerHTML=`<p><b>Your choice: ${esc(d.options[choice].label)}</b></p><div class="analyst-tradeoffs">${d.options.map(o=>`<section><b>${esc(o.label)}</b><p><b>Benefit:</b> ${esc(o.benefit)}</p><p><b>Trade-off:</b> ${esc(o.cost)}</p></section>`).join("")}</div><p>${esc(d.reflection)}</p><p class="how">Both choices involve a trade-off. Your choice is ungraded.</p>${rewards}${data.poll_api?`<button type="button" class="big go" data-call-share>Add my response & see reader responses</button><p class="how">Optional. Sends this choice and a random receipt for this question. No name or account. In the kids app, a grown-up must unlock sharing.</p>`:""}<div class="analyst-results" role="status"></div>`;
      $("[data-call-share]",box)?.addEventListener("click",share);
    }
    $$("[data-call-choice]",box).forEach(b=>b.onclick=()=>{if(busy)return;choice=+b.dataset.callChoice;store.set("call-choice-"+d.poll_id,choice);reveal();});
    async function share(){
      if(busy||choice===null)return;busy=true;
      const button=$("[data-call-share]",box),status=$(".analyst-results",box);button.disabled=true;
      let timer;
      try{
        const gated=data.poll_gated===true;
        if(gated){if(typeof window.npGate!=="function")throw Error("gate_unavailable");const allowed=await new Promise(resolve=>window.npGate("grown",()=>resolve(true),()=>resolve(false)));if(!allowed)return;}
        receipt=receipt||store.get("call-receipt-"+d.poll_id,null);
        if(typeof receipt!=="string"||!(/^[a-f0-9]{64}$/).test(receipt)){receipt=Array.from(crypto.getRandomValues(new Uint8Array(32)),v=>v.toString(16).padStart(2,"0")).join("");store.set("call-receipt-"+d.poll_id,receipt);}
        const controller=new AbortController();timer=setTimeout(()=>controller.abort(),10000);status.textContent="Sending your response…";
        const response=await fetch(atob(data.poll_api),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({poll_id:d.poll_id,choice,receipt}),signal:controller.signal,credentials:"omit"});
        if(!response.ok)throw Error("unavailable");const tally=await response.json();
        if(!Number.isSafeInteger(tally.total)||tally.total<0||!Array.isArray(tally.counts)||tally.counts.length!==2||!tally.counts.every(n=>Number.isSafeInteger(n)&&n>=0)||tally.counts[0]+tally.counts[1]!==tally.total)throw Error("invalid_tally");
        if(tally.total<5){status.textContent="Response added. Results appear after at least five responses.";return;}
        status.innerHTML=`<h3>Reader responses</h3><p>${tally.total.toLocaleString()} responses · not a representative survey</p>${d.options.map((o,i)=>{const pct=Math.round(tally.counts[i]/tally.total*100);return `<div class="analyst-result-label"><span>${esc(o.label)}</span><b>${pct}%</b></div><div class="analyst-result-track" role="img" aria-label="${esc(o.label)}: ${pct}%"><span style="width:${pct}%"></span></div>`;}).join("")}<p class="how">One response per browser receipt, with limited duplicate protection. A majority does not make an option correct.</p>`;
      }catch(e){status.textContent="Reader responses are unavailable right now. Your reflection is saved on this device; you can try sharing again.";}
      finally{clearTimeout(timer);busy=false;button.disabled=false;}
    }
    reveal();
  }
'''
