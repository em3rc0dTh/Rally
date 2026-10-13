/* Browser-like integration of live API data with the modular Rally shell. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const root=path.join(__dirname,'..','rally','web');
const file=n=>fs.readFileSync(path.join(root,n),'utf8');
const html=file('index.html')
  .replace('<script src="/static/app.js" defer></script>','<script>'+file('app.js')+'</script>')
  .replace('<script src="/static/shell.js" defer></script>','<script>'+file('shell.js')+'</script>');
const errors=[],vc=new VirtualConsole();
vc.on('jsdomError',e=>errors.push(e));vc.on('error',e=>errors.push(e));
const fixedAt='2026-10-13T17:00:00+00:00';
const payloads={
 'me':{id:'actor-01',name:'Pilot admin',role:'admin',tenant_id:'pilot-tenant'},
 'overview':{assets:1,jobs:1,active_custody:1,open_cases:1,evidence_events:1},
 'connectors':[{name:'Traccar test',source:'traccar',coverage:'current',detail:'1 mapped device',last_success:fixedAt}],
 'assets':[{id:'asset-01',tag:'CAM-001',name:'Thermal camera',status:'ready'}],
 'jobs':[{id:'job-01',external_ref:'WO-102',title:'Inspection',state:'completed'}],
 'custody':[{id:'custody-01',asset_id:'asset-01',job_id:'job-01',holder:'Technician A',state:'active'}],
 'cases':[{id:'case-01',severity:'critical',description:'Missing return',state:'open',fingerprint:'completed_job:custody-01',last_seen:fixedAt}],
 'evidence':[],
 'audit':[],
 'credentials':[],
 'geo/positions':[{asset_id:'asset-01',asset_tag:'CAM-001',device_id:'32',source:'traccar',
                   observed_at:fixedAt,latitude:-12.05,longitude:-77.04,quality:'unverified',valid:true,fresh:false}],
 'map/config':{public_tiles_enabled:false}
};
const dom=new JSDOM(html,{url:'http://localhost:8080/',runScripts:'dangerously',
  virtualConsole:vc,pretendToBeVisual:true,beforeParse(win){
    win.scrollTo=()=>{};
    win.AbortSignal.timeout=()=>undefined;
    win.HTMLDialogElement.prototype.close=function(){this.open=false;};
    win.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
    win.fetch=async (url)=>{
      const key=String(url).replace(/^\/api\//,'').split('?')[0];
      if(!Object.prototype.hasOwnProperty.call(payloads,key))throw new Error('Unknown route '+key);
      return {ok:true,status:200,json:async()=>payloads[key]};
    };
  }});
const doc=dom.window.document;
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
(async()=>{
  doc.getElementById('token').value='x'.repeat(48);
  doc.getElementById('connect').click();
  await tick();await tick();
  assert.equal(doc.getElementById('stat-assets').textContent,'1');
  assert.equal(doc.getElementById('stat-cases').textContent,'1');
  assert.match(doc.getElementById('asset-register').textContent,/Technician A/);
  assert.match(doc.getElementById('source-traccar').textContent,/Polling current/);
  doc.querySelector('[data-go="fleet"]').click();
  await tick();await tick();
  assert.match(doc.getElementById('geo-device-list').textContent,/CAM-001/);
  assert.equal(doc.querySelectorAll('.geo-marker').length,1);
  assert.equal(doc.getElementById('geo-tiles').disabled,true);
  doc.querySelector('[data-go="exceptions"]').click();
  const detail=doc.querySelector('button[data-case]');
  assert.ok(detail);
  detail.click();await tick();await tick();
  assert.match(doc.getElementById('case-detail').textContent,/WO-102/);
  assert.match(doc.getElementById('case-detail').textContent,/CAM-001/);
  assert.equal(errors.length,0,errors.map(x=>String(x)).join('\n'));
  console.log('Rally UI: login, linked records, mapped GPS observations and recovery detail passed.');
  dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;dom.window.close();});
