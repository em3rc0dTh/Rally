'use strict';
const $ = id => document.getElementById(id);
const state = {assets:[], jobs:[], custody:[], cases:[], evidence:[], audit:[]};
let bearer = '', identity = null, generation = 0, selectedCase = null;
const pages = {}, offsets = {}, pending = new Map();
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const displayTime = iso => {
 const date=new Date(iso);
 return Number.isNaN(date.getTime()) ? String(iso||'—') : date.toLocaleString();
};
const canOperate = () => ['admin','operator'].includes(identity?.role);
const canReview = () => ['admin','operator','reviewer'].includes(identity?.role);
function notice(message,bad=false){$('notice').textContent=message;$('notice').className='notice'+(bad?' error':'');}
function disconnect(message='Disconnected.'){
 bearer='';identity=null;generation++;pending.clear();credentialNames?.clear();evidenceDraft=null;selectedCase=null;
 document.querySelectorAll('form').forEach(f=>f.reset());$('token').value='';$('identity').textContent='';
 Object.keys(state).forEach(k=>{state[k]=[];pages[k]=false;offsets[k]=0;});
 ['assets','jobs','custody','cases'].forEach(k=>$('stat-'+k).textContent='—');
 $('credentials').replaceChildren();$('connectors').replaceChildren();$('secret-value').value='';$('new-secret').hidden=true;
 $('case-detail').textContent='';$('case-dialog').close();draw();notice(message);
 window.dispatchEvent(new Event('rally:disconnect'));
}
async function api(path,method='GET',payload=null,idempotent=false){
 if(!bearer)throw new Error('Connect with your personal access token.');
 const current=bearer;
 const headers={Authorization:'Bearer '+current};
 if(payload!==null)headers['Content-Type']='application/json';
 const signature=path+'|'+JSON.stringify(payload);
 if(idempotent){if(!pending.has(signature))pending.set(signature,crypto.randomUUID());headers['Idempotency-Key']=pending.get(signature);}
 let res;
 try{res=await fetch('/api/'+path,{method,headers,body:payload===null?undefined:JSON.stringify(payload),signal:AbortSignal.timeout(30000)});}
 catch(e){throw new Error('Connection interrupted. Retry the same action; its idempotency key is retained.');}
 const body=await res.json().catch(()=>({detail:'Unexpected server response'}));
 if(current!==bearer)throw new Error('Session changed; response discarded.');
 if(res.status===401){disconnect('Session expired or revoked.');throw new Error('Connect with an active credential.');}
 if(!res.ok)throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));
 if(idempotent)pending.delete(signature);
 return body;
}
async function busy(button,action){
 if(button.disabled)return;
 button.disabled=true;
 try{await action();}catch(e){notice(e.message,true);}finally{button.disabled=false;permissions();}
}
function permissions(){
 ['new-asset','new-job','issue','new-evidence'].forEach(id=>$(id).querySelectorAll('input,select,button').forEach(e=>e.disabled=!canOperate()));
 $('reconcile').disabled=!canReview();$('access-panel').hidden=identity?.role!=='admin';
 $('case-action').hidden=!canReview();
}
function fill(id,items,label,optional=false){
 const field=$(id), previous=field.value;field.replaceChildren();
 if(optional)field.add(new Option('None',''));
 items.forEach(x=>field.add(new Option(label(x),x.id)));
 if(items.some(x=>x.id===previous))field.value=previous;
}
function draw(){
 const active=new Set(state.custody.filter(x=>x.state==='active').map(x=>x.asset_id));
 fill('issue-asset',state.assets.filter(x=>x.status==='ready'&&!active.has(x.id)),x=>x.tag+' · '+x.name);
 fill('event-asset',state.assets,x=>x.tag+' · '+x.name,true);
 fill('issue-job',state.jobs.filter(x=>x.state!=='completed'),x=>x.external_ref+' · '+x.title,true);
 fill('event-job',state.jobs,x=>x.external_ref+' · '+x.title,true);
 const assets=new Map(state.assets.map(x=>[x.id,x.tag]));
 $('cases').innerHTML=state.cases.map(x=>`<tr><td><span class="badge ${x.severity==='critical'?'bad':'warn'}">${esc(x.severity)}</span></td><td>${esc(x.description)}<br><small>${esc(x.fingerprint)}</small></td><td>${esc(x.state)}</td><td>${esc(displayTime(x.last_seen))} <button class="small" data-case="${esc(x.id)}">Review</button></td></tr>`).join('')||'<tr><td colspan="4">No loaded exceptions.</td></tr>';
 $('custody').innerHTML=state.custody.map(x=>`<tr><td>${esc(assets.get(x.asset_id)||x.asset_id)}</td><td>${esc(x.holder)}</td><td>${esc(x.state)}</td><td>${x.state==='active'&&canOperate()?`<button class="small" data-return="${esc(x.id)}">Return</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="4">No loaded custody.</td></tr>';
 $('jobs').innerHTML=state.jobs.map(x=>`<tr><td>${esc(x.external_ref)}</td><td>${esc(x.title)}</td><td>${esc(x.state)}</td><td>${x.state!=='completed'&&canOperate()?`<button class="small" data-complete="${esc(x.id)}">Complete</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="4">No loaded work orders.</td></tr>';
 const jobRefs=new Map(state.jobs.map(x=>[x.id,x.external_ref]));
 $('evidence').innerHTML=state.evidence.map(x=>`<tr><td title="${esc(x.received_at)}">${esc(displayTime(x.received_at))}</td><td>${esc(assets.get(x.asset_id)||'—')}</td><td>${esc(jobRefs.get(x.job_id)||'—')}</td><td>${esc(x.source)}</td><td>${esc(x.event_type)}</td><td>${esc(x.source_event_id)}</td></tr>`).join('')||'<tr><td colspan="6">No loaded evidence.</td></tr>';
 $('audit').innerHTML=state.audit.map(x=>`<tr><td title="${esc(x.created_at)}">${esc(displayTime(x.created_at))}</td><td>${esc(credentialNames.get(x.actor_id)||(x.actor_id==='platform:local-recovery'?'Deployment operator':x.actor_id||'Legacy unattributed'))}</td><td>${esc(x.entity)} · ${esc(x.entity_id)}</td><td>${esc(x.action)}</td></tr>`).join('')||'<tr><td colspan="4">No loaded audit events.</td></tr>';
 $('paging').replaceChildren();
 Object.keys(state).forEach(k=>{const b=document.createElement('button');b.textContent=`More ${k} (${state[k].length} loaded)`;b.disabled=!pages[k]||!identity;b.onclick=()=>busy(b,async()=>{const rows=await api(k+'?limit=200&offset='+offsets[k]);offsets[k]+=rows.length;const known=new Set(state[k].map(x=>x.id));state[k].push(...rows.filter(x=>!known.has(x.id)));pages[k]=rows.length===200;draw();});$('paging').append(b);});
 permissions();
}
async function refresh(){
 const session=generation;
 const who=await api('me');
 if(who.role==='connector')throw new Error('Connector credentials are for ingestion. Use a personal credential for Mission Control.');
 const keys=Object.keys(state);
 const results=await Promise.all([api('overview'),api('connectors'),...keys.map(k=>api(k+'?limit=200'))]);
 if(session!==generation)return;
 identity=who;$('identity').textContent=who.name+' · '+who.role+' · '+who.tenant_id;
 const [stats,coverage,...rows]=results;
 keys.forEach((k,i)=>{state[k]=rows[i];pages[k]=rows[i].length===200;offsets[k]=rows[i].length;});
 ['assets','jobs','custody','cases'].forEach((k,i)=>$('stat-'+k).textContent=[stats.assets,stats.jobs,stats.active_custody,stats.open_cases][i]);
 $('connectors').innerHTML=coverage.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.source)}</td><td>${esc(x.coverage)}<br>${esc(x.detail)}</td><td>${esc(x.last_success||'Never')}</td></tr>`).join('')||'<tr><td colspan="4">No active connector credentials.</td></tr>';
 draw();
 if(identity.role==='admin')await loadCredentials();
 window.dispatchEvent(new CustomEvent('rally:state',{detail:{
   identity:who,stats,coverage,assets:state.assets,jobs:state.jobs,
   custody:state.custody,cases:state.cases,evidence:state.evidence,audit:state.audit
 }}));
 notice('Operational state loaded.');
}
const credentialNames=new Map();
async function loadCredentials(){
 const rows=await api('credentials');
 credentialNames.clear();rows.forEach(x=>credentialNames.set(x.id,x.name));
 $('credentials').innerHTML=rows.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.role)} ${esc(x.source||'')} ${esc(x.scope||'')}</td><td>${x.revoked_at?'Revoked':x.expires_at?'Expires '+esc(x.expires_at):'Active'}</td><td>${x.revoked_at?'—':`<button type="button" data-revoke="${esc(x.id)}">Revoke</button>`}</td></tr>`).join('');
 draw();
}
$('connect').onclick=()=>busy($('connect'),async()=>{const next=$('token').value.trim();disconnect('Connecting…');bearer=next;await refresh();});
$('logout').onclick=()=>disconnect();$('refresh').onclick=()=>busy($('refresh'),refresh);
$('reconcile').onclick=()=>busy($('reconcile'),async()=>{const r=await api('reconcile','POST');await refresh();notice(`Reconciled ${r.active_custody_scanned} assignments; ${r.open_conditions} conditions.`);});
document.addEventListener('click',event=>{
 const b=event.target.closest('button');if(!b)return;
 if(b.dataset.return)busy(b,async()=>{await api('custody/return','POST',{custody_id:b.dataset.return},true);await refresh();notice('Return recorded. Automatic reconciliation will clear resolved conditions.');});
 if(b.dataset.complete)busy(b,async()=>{await api('jobs/'+b.dataset.complete+'/complete','POST');await refresh();});
 if(b.dataset.case)busy(b,async()=>{
   selectedCase=b.dataset.case;
   const c=await api('cases/'+selectedCase);
   const displayActor=x=>credentialNames.get(x)||x||'Unassigned';
   const assignmentId=(c.fingerprint||'').split(':')[1];
   const assigned=state.custody.find(x=>x.id===assignmentId);
   const asset=state.assets.find(x=>x.id===assigned?.asset_id);
   const order=state.jobs.find(x=>x.id===assigned?.job_id);
   $('case-detail').textContent=[
      c.description,
      'State: '+c.state+' · '+c.severity,
      'Equipment: '+(asset?asset.tag+' · '+asset.name:'Unlinked / not loaded'),
      'Work order: '+(order?order.external_ref+' · '+order.title:'Unlinked / not loaded'),
      'Holder: '+(assigned?.holder||'Unknown'),
      'Custody: '+(assigned?.state||'Unknown'),
      'Owner: '+displayActor(c.owner_id),
      'First observed: '+c.first_seen,
      'Last observed: '+c.last_seen,
      ...(c.resolved_at?['Resolved: '+c.resolved_at]:[]),
      ...c.notes.map(n=>n.created_at+' · '+displayActor(n.actor_id)+'\n'+n.note)
   ].join('\n\n');
   $('case-action').hidden=c.state==='resolved'||!canReview();
   $('case-dialog').showModal();
 });
 if(b.dataset.revoke&&confirm('Revoke this credential?'))busy(b,async()=>{const id=b.dataset.revoke;await api('credentials/'+id+'/revoke','POST');if(id===identity.id)disconnect('Your credential was revoked.');else await loadCredentials();});
});
$('close-case').onclick=()=>$('case-dialog').close();
$('case-action').onsubmit=event=>{event.preventDefault();busy(event.target.querySelector('button'),async()=>{await api('cases/'+selectedCase+'/acknowledge','POST',{note:$('case-note').value});$('case-note').value='';$('case-dialog').close();await refresh();});};
function form(id,path,transform,idempotent=false){
 $(id).onsubmit=event=>{event.preventDefault();const f=event.target;busy(f.querySelector('button'),async()=>{const body=transform(Object.fromEntries(new FormData(f)));await api(path,'POST',body,idempotent);f.reset();await refresh();notice('Saved.');});};
}
form('new-asset','assets',r=>r);
form('new-job','jobs',r=>r);
form('issue','custody/issue',r=>({asset_id:r.asset_id,job_id:r.job_id||null,holder:r.holder,due_at:r.due_at?new Date(r.due_at).toISOString():null}),true);
let evidenceDraft=null;
form('new-evidence','evidence',r=>{const signature=JSON.stringify(r);if(evidenceDraft?.signature!==signature)evidenceDraft={signature,body:{asset_id:r.asset_id||null,job_id:r.job_id||null,source:r.source,source_event_id:crypto.randomUUID(),event_type:r.event_type,observed_at:new Date().toISOString(),payload:{entered_via:'Rally Cockpit',unverified:true}}};return evidenceDraft.body;});
$('new-evidence').addEventListener('reset',()=>{evidenceDraft=null;});
$('new-credential').onsubmit=event=>{event.preventDefault();busy(event.target.querySelector('button'),async()=>{const r=Object.fromEntries(new FormData(event.target));const result=await api('credentials','POST',{...r,source:r.source||null,scope:r.scope||null,expires_at:r.expires_at?new Date(r.expires_at).toISOString():null});$('secret-value').value=result.api_token;$('new-secret').hidden=false;event.target.reset();await loadCredentials();notice('Credential issued. Save the token now.');});};
$('hide-secret').onclick=()=>{$('secret-value').value='';$('new-secret').hidden=true;};
// Remove legacy MK0 browser storage. New credentials remain only in memory.
sessionStorage.removeItem('rally_token');
draw();
