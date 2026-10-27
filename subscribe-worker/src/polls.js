// Optional aggregate responses. No email/subscriber lookup and no choice in logs.
import {SITE, hash, bounded} from './common.js';
const reply=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let cached=null;
export async function vote(request,env,s){
  if(env.POLLS_ENABLED!=='true')return reply({error:'unavailable'},503);
  if(!request.headers.get('Origin'))return reply({error:'origin_required'},403);
  if(!request.headers.get('Content-Type')?.toLowerCase().startsWith('application/json'))return reply({error:'json_required'},400);
  let data;
  try{data=JSON.parse(new TextDecoder().decode(await bounded(new Response(request.body),2049)));}catch{return reply({error:'invalid_payload'},400);}
  if(!data||Array.isArray(data)||Object.keys(data).some(k=>!['poll_id','choice','receipt'].includes(k))||!(/^[a-z0-9-]+:\d{4}-\d{2}-\d{2}:[a-f0-9]{24}$/).test(data.poll_id)||!Number.isInteger(data.choice)||![0,1].includes(data.choice)||!(/^[a-f0-9]{64}$/).test(data.receipt))return reply({error:'invalid_payload'},400);
  const now=s.now();
  // The public, generated manifest is the only authority for valid questions.
  if(!cached||cached.fetch!==s.fetch||now-cached.at>60000){
    const response=await s.fetch(`${SITE}/play/polls.json`,{headers:{Accept:'application/json'},redirect:'error'});
    const bytes=await bounded(response,500001);
    const manifest=JSON.parse(new TextDecoder().decode(bytes));
    if(!manifest||typeof manifest!=='object'||Array.isArray(manifest))throw Error('invalid_poll_manifest');
    cached={value:manifest,at:now,fetch:s.fetch};
  }
  const entry=cached.value[data.poll_id];
  if(!entry||typeof entry.date!=='string'||entry.date<new Date(now-90*86400000).toISOString().slice(0,10))return reply({error:'unknown_poll'},404);
  if(!env.DISPATCH_SECRET)throw Error('rate_limit_unavailable');
  const hour=Math.floor(now/3600000);
  const rateKey=await hash(`${env.DISPATCH_SECRET}/poll/${hour}/${request.headers.get('CF-Connecting-IP')||'unknown'}`);
  const rate=await env.DB.prepare('INSERT INTO rate_limits(key,count,expires_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1 RETURNING count').bind(rateKey,(hour+2)*3600000).first();
  if(rate.count>60)return reply({error:'too_many_requests'},429);
  const receiptHash=await hash(`${data.poll_id}/${data.receipt}`);
  await env.DB.prepare('INSERT INTO poll_votes(poll_id,receipt_hash,choice,created_at) VALUES(?,?,?,?) ON CONFLICT(poll_id,receipt_hash) DO UPDATE SET choice=excluded.choice').bind(data.poll_id,receiptHash,data.choice,now).run();
  const rows=await env.DB.prepare('SELECT choice,COUNT(*) AS count FROM poll_votes WHERE poll_id=? GROUP BY choice').bind(data.poll_id).all();
  const counts=[0,0];for(const r of rows.results)counts[r.choice]=r.count;
  const total=counts[0]+counts[1];
  // Small samples remain undisclosed until five responses have arrived.
  return reply({total:total<5?0:total,counts:total<5?[0,0]:counts});
}
