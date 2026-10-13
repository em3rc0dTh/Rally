'use strict';
/* Rally 0.3 application shell: navigation and geospatial read model.
 * Uses only authenticated Rally API data, never fabricated GPS readings.
 * Original form handlers and business rules remain in app.js.
 */
(() => {
  const el = (tag, className = '', html = '') => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (html) node.innerHTML = html; // Only static, authored template markup.
    return node;
  };
  const main = document.querySelector('main');
  if (!main || !document.getElementById('new-asset')) return;
  const pages = new Map();
  const names = {
    overview:'Overview', work:'Work orders', assets:'Equipment & custody',
    exceptions:'Exception recovery', evidence:'Evidence ledger',
    fleet:'Fleet & GPS', integrations:'Integrations', governance:'Audit & access'
  };
  const subtitle = {
    overview:'Business assurance at a glance',
    work:'From work intent to operational outcome',
    assets:'Know which equipment is assigned and where accountability sits',
    exceptions:'Prioritize discrepancies and coordinate human recovery',
    evidence:'Separate observations from business confirmation',
    fleet:'Device-reported coordinates linked to recorded equipment',
    integrations:'Source systems, connectivity and coverage',
    governance:'Accountable access, changes and source-of-truth history'
  };
  const mainBlocks = [...main.children];
  const byId = id => document.getElementById(id);
  const block = id => byId(id).closest('section.panel');
  const section = name => mainBlocks.find(n => n.classList?.contains('section') &&
    n.querySelector('h2')?.textContent.trim() === name);
  const panels = {
    auth:mainBlocks.find(n => n.contains(byId('token'))),
    hero:mainBlocks.find(n => n.querySelector('h1')),
    overviewHead:section('Operational state'),
    kpis:mainBlocks.find(n => n.classList?.contains('grid')),
    jobForm:block('new-job'), assetForm:block('new-asset'),
    issueForm:block('issue'), evidenceForm:block('new-evidence'),
    casesHead:section('Exception queue'), cases:block('cases'),
    custody:block('custody'), jobs:block('jobs'),
    evidenceHead:section('Evidence ledger'), evidence:block('evidence'),
    pagingHead:section('Browse more records'), paging:byId('paging'),
    connectorsHead:section('Connector coverage'), connectors:block('connectors'),
    auditHead:section('Audit trail'), audit:block('audit'),
    access:byId('access-panel'), dialog:byId('case-dialog')
  };
  const disclaimer = mainBlocks.find(n => n.tagName === 'P' && n.textContent.includes('QR observations'));
  main.replaceChildren();
  const wrapper = el('div');
  wrapper.id = 'rally-layout';
  const sidebar = el('aside');
  sidebar.id = 'rally-sidebar';
  sidebar.setAttribute('aria-label','Mission Control navigation');
  sidebar.innerHTML = `
    <div class="shell-brand"><strong>R<em>Λ</em>LLY</strong><small>Mission Control · Operations</small></div>
    <div>
      <div class="nav-group-title">Workspace</div>
      <nav class="shell-nav" aria-label="Modules">
        <button type="button" data-go="overview"><span class="nav-symbol">◫</span> Overview</button>
        <button type="button" data-go="work"><span class="nav-symbol">▤</span> Work orders</button>
        <button type="button" data-go="assets"><span class="nav-symbol">▣</span> Equipment</button>
        <button type="button" data-go="exceptions"><span class="nav-symbol">◇</span> Exceptions</button>
        <button type="button" data-go="evidence"><span class="nav-symbol">◎</span> Evidence</button>
        <button type="button" data-go="fleet"><span class="nav-symbol">⌖</span> Fleet & GPS</button>
        <button type="button" data-go="integrations"><span class="nav-symbol">⤨</span> Integrations</button>
        <button type="button" data-go="governance"><span class="nav-symbol">☷</span> Audit & access</button>
      </nav>
    </div>
    <div class="sidebar-footer"><span class="shell-label">Source transparency</span>
      <p>ERP intent ≠ field observation.<br>Observations ≠ verified business completion.</p>
      <div id="sidebar-status" class="signal"><span class="signal-dot off"></span> Not connected</div>
    </div>`;
  const workspace = el('div');
  workspace.id='rally-shell-main';
  const topbar = el('div','shell-topbar');
  topbar.innerHTML = `
    <div><div id="current-view" class="shell-topbar-title">Overview</div>
         <div id="current-sub" class="shell-topbar-sub">Business assurance at a glance</div></div>
    <div class="topbar-actions">
      <span id="tenant-chip" class="tenant-chip" title="Current tenant">Not connected</span>
      <span id="source-chip" class="source-chip">Sources · unknown</span>
      <button id="global-refresh" type="button" aria-label="Refresh data">↻ Refresh</button>
    </div>`;
  wrapper.append(sidebar,workspace);
  workspace.append(topbar,main);
  document.body.append(wrapper);
  const makePage = (key, title, text) => {
    const p = el('section','screen-stack');
    p.dataset.screen=key;
    const h=el('div','screen-head',`<div>
      <div class="screen-eyebrow">Rally / ${title}</div>
      <h1>${title}</h1><p>${text}</p></div>`);
    p.append(h);main.append(p);pages.set(key,p);return p;
  };
  const dual = (page, ...parts) => {
    const grid=el('div','screen-dual');
    parts.forEach(n=>n&&grid.append(n));
    page.append(grid);
  };
  const overview=makePage('overview','Operations overview',
    'One accountable picture of orders, people, equipment, observations and unresolved exceptions.');
  overview.append(panels.auth, panels.overviewHead, panels.kpis);
  const journey=el('section','command-section');
  journey.innerHTML = `<h2>Execution lifecycle</h2>
    <div class="product-journey">
      <button class="journey-step" data-go="work"><span class="sequence">01 / INTENT</span><strong>Register the job</strong><p>Capture what the customer or ERP committed to.</p></button>
      <button class="journey-step" data-go="assets"><span class="sequence">02 / ALLOCATION</span><strong>Assign custody</strong><p>Link accountable people and equipment to a job.</p></button>
      <button class="journey-step" data-go="fleet"><span class="sequence">03 / FIELD SIGNALS</span><strong>Observe reality</strong><p>Inspect device-reported GPS and integration coverage.</p></button>
      <button class="journey-step" data-go="exceptions"><span class="sequence">04 / DISCREPANCY</span><strong>Detect exceptions</strong><p>Identify outstanding return and work contradictions.</p></button>
      <button class="journey-step" data-go="evidence"><span class="sequence">05 / PROOF</span><strong>Verify resolution</strong><p>Reconcile against authoritative state and retain the audit.</p></button>
    </div>`;
  overview.append(journey);
  const boards=el('div','command-grid');
  boards.innerHTML=`
    <div class="command-box"><span class="screen-eyebrow">Attention queue</span>
      <h3 id="overview-attention">Connect a workspace to start</h3>
      <p id="overview-action-text">Exceptions remain open until the underlying condition is cleared. Acknowledgment alone does not resolve them.</p>
      <button data-go="exceptions" type="button">Open exception center ↗</button></div>
    <div class="command-box"><span class="screen-eyebrow">Integration reality</span>
      <h3>Know which systems are reporting</h3>
      <div class="metric-line"><span>Active connectors</span><strong id="overview-connector-count">—</strong></div>
      <div class="metric-line"><span>Recent GPS positions</span><strong id="overview-position-count">—</strong></div>
      <div class="metric-line"><span>Evidence ledger</span><strong id="overview-evidence-count">—</strong></div>
      <button data-go="integrations" type="button">Inspect source coverage ↗</button></div>`;
  overview.append(boards);

  const work=makePage('work','Work orders','Create operational intent, complete jobs and inspect business commitments.');
  dual(work,panels.jobForm,panels.jobs);
  const assets=makePage('assets','Equipment & custody','Register serialized equipment, issue it to a holder and account for each return.');
  dual(assets,panels.assetForm,panels.issueForm);assets.append(panels.custody);
  const exceptions=makePage('exceptions','Exception recovery','Acknowledge responsibility without prematurely closing the underlying discrepancy.');
  exceptions.append(panels.casesHead,panels.cases);
  const evidence=makePage('evidence','Evidence ledger','Review what was observed, when, and by which source—without claiming automatic proof.');
  dual(evidence,panels.evidenceForm);
  evidence.append(panels.evidenceHead,panels.evidence);
  if (disclaimer) evidence.append(disclaimer);
  evidence.append(panels.pagingHead,panels.paging);

  const fleet=makePage('fleet','Fleet & GPS',
    'A geographic view of recorded GPS/Traccar observations. No simulated vehicles or invented live locations.');
  const mapView=el('div','map-overview');
  mapView.innerHTML=`
    <div>
      <div class="geo-canvas" id="geo-canvas" role="region" aria-label="Geographic device overview">
        <span id="geo-map-head" class="geo-map-head">No live tracking connection</span>
        <div id="fleet-map"></div><div id="geo-overlays"></div>
        <div id="geo-empty"><div class="geo-empty-card"><span class="big-icon">⌖</span>
          <strong>No GPS positions yet</strong><p>Connect Traccar and map its device IDs to Rally assets. This view only displays actual stored observations.</p></div></div>
      </div>
      <div class="geo-legal">Coordinate preview uses recorded latitude/longitude only.
        Street basemap is optional and uses third-party map tiles. Coordinates and viewing area may be disclosed to the provider.</div>
    </div>
    <aside class="geo-list">
      <span class="screen-eyebrow">Field observations</span>
      <h3>Tracked devices</h3>
      <p>Reported position is not proof of technician activity or customer acceptance.</p>
      <div id="geo-device-list" aria-live="polite"><div class="shell-empty">Connect your tenant to load positions.</div></div>
      <div class="geo-actions">
        <button id="geo-reload" type="button">↻ Reload positions</button>
        <button id="geo-tiles" type="button" disabled>Show street map</button>
      </div>
      <p class="geo-legal" id="geo-tile-state">Public map tiles require explicit opt-in and must comply with provider terms.</p>
    </aside>`;
  fleet.append(mapView);
  const integrations=makePage('integrations','Integrations',
    'Connect established tools rather than rebuilding ERP or GPS infrastructure.');
  const integrationCards=el('div','integration-grid');
  integrationCards.innerHTML=`
    <div class="integration-card"><span class="shell-label">ERP · Business intent</span><h3>Odoo 19</h3>
      <span id="source-odoo" class="badge">Not connected</span>
      <p>Read confirmed, explicitly selected service orders from the customer's Odoo database. Restricted API credentials and instance scope required.</p>
      <a href="https://www.odoo.com/documentation/19.0/developer/reference/external_api.html" target="_blank" rel="noopener noreferrer">Official Odoo JSON-2 API ↗</a></div>
    <div class="integration-card"><span class="shell-label">GPS · Reported position</span><h3>Traccar</h3>
      <span id="source-traccar" class="badge">Not connected</span>
      <p>Ingest device positions with explicit asset mapping and freshness checks. Actual device state appears in Fleet & GPS.</p>
      <a href="https://www.traccar.org/api-reference/" target="_blank" rel="noopener noreferrer">Official Traccar API ↗</a></div>
    <div class="integration-card"><span class="shell-label">Physical · Device sighting</span><h3>RFID / QR</h3>
      <span id="source-rfid" class="badge">Not connected</span>
      <p>Edge readings and manual observations are evidence inputs, never an automatic custody handover or return.</p>
      <button type="button" data-go="evidence">Inspect evidence ↗</button></div>`;
  integrations.append(integrationCards,panels.connectorsHead,panels.connectors);
  const governance=makePage('governance','Audit & access','Review the chain of accountability and manage individual access permissions.');
  governance.append(panels.auditHead,panels.audit,panels.access);
  // The native <dialog> must not be inside a hidden screen.
  main.append(panels.dialog);
  // Restore a sensible no-JS experience if the shell fails to initialize.
  main.dataset.ready='true';
  document.body.classList.add('rally-shell');

  let selected = 'overview', geoRows = [], tileAllowed = false, map = null, markers = null, geoSerial = 0;
  const safe = v => String(v ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const asLocal = iso => {
    const d=new Date(iso);
    return Number.isNaN(d.getTime())?'unknown':d.toLocaleString();
  };
  const navigate = key => {
    if(!pages.has(key))key='overview';
    selected=key;
    pages.forEach((node,name)=>node.hidden=name!==key);
    document.querySelectorAll('[data-go]').forEach(b=>{
      if(b.closest('.shell-nav')){
        if(b.dataset.go===key)b.setAttribute('aria-current','page');
        else b.removeAttribute('aria-current');
      }
    });
    byId('current-view').textContent=names[key];
    byId('current-sub').textContent=subtitle[key];
    if(location.hash!=='#'+key)history.replaceState(null,'','#'+key);
    if(key==='fleet')loadGeo();
    window.scrollTo({top:0,behavior:'instant'});
  };
  document.addEventListener('click',event=>{
    const btn=event.target.closest('[data-go]');
    if(btn){event.preventDefault();navigate(btn.dataset.go);}
  });
  window.addEventListener('hashchange',()=>navigate(location.hash.slice(1)));
  byId('global-refresh').onclick=()=>{
    if(typeof identity!=='undefined' && identity){byId('refresh').click();if(selected==='fleet')loadGeo();}
    else navigate('overview');
  };

  function summarize(detail){
    const who=detail.identity;
    byId('tenant-chip').textContent=who ? who.name+' · '+who.role : 'Not connected';
    byId('sidebar-status').innerHTML='<span class="signal-dot '+(who?'good':'off')+'"></span> '+(who?'Tenant connected':'Not connected');
    const coverage=detail.coverage||[];
    const active=coverage.filter(x=>x.coverage==='current').length;
    byId('source-chip').textContent='Sources · '+active+'/'+coverage.length+' current';
    byId('overview-connector-count').textContent=coverage.length+' ('+active+' current)';
    byId('overview-evidence-count').textContent=detail.stats?.evidence_events??detail.evidence?.length??0;
    const open=detail.stats?.open_cases??0;
    byId('overview-attention').textContent=open?open+' exception'+(open===1?'':'s')+' require attention':'No unresolved exceptions';
    byId('overview-action-text').textContent=open?
      'Review the underlying condition, assign an owner, and verify recovery against custody.':
      'Operational conditions currently reconcile. Source outages still mean unknown coverage, not proof of completion.';
    for(const [source,ids] of [['odoo',['odoo']],['traccar',['traccar','gps']],['rfid',['rfid']]]){
      const rows=coverage.filter(x=>ids.includes(x.source));
      byId('source-'+source).textContent=rows.length?
        rows.some(x=>x.coverage==='current')?'Polling current':'Configured · '+rows[0].coverage:
        'Not connected';
    }
  }
  window.addEventListener('rally:state',event=>{
    summarize(event.detail);
    if(selected==='fleet')loadGeo();
  });
  window.addEventListener('rally:disconnect',()=>{
    geoRows=[];geoSerial++;tileAllowed=false;destroyMap();
    byId('tenant-chip').textContent='Not connected';
    byId('source-chip').textContent='Sources · unknown';
    byId('sidebar-status').innerHTML='<span class="signal-dot off"></span> Not connected';
    byId('overview-position-count').textContent='—';
    renderGeo();
  });
  const pointMarkup = row => `
    <div class="geo-device"><strong>${safe(row.asset_tag||'Unmapped device')} · ${safe(row.device_id)}</strong>
      <small>${safe(row.source)} · ${safe(asLocal(row.observed_at))}<br>
      ${Number(row.latitude).toFixed(5)}, ${Number(row.longitude).toFixed(5)}</small>
      <span class="geo-label ${row.quality==='current'?'':'stale'}">${row.quality==='current'?'Fresh reported fix':'Stale / unverified fix'}</span></div>`;
  function renderGeo(){
    const list=byId('geo-device-list'),blank=byId('geo-empty'),overlay=byId('geo-overlays');
    const button=byId('geo-tiles'),canvas=byId('geo-canvas');
    list.innerHTML=geoRows.length?geoRows.map(pointMarkup).join(''):
      '<div class="shell-empty">No GPS events for this tenant. Create a Traccar connector credential and configure device-to-asset mapping in the adapter.</div>';
    byId('overview-position-count').textContent=geoRows.length;
    blank.hidden=geoRows.length>0;
    overlay.replaceChildren();
    const limit=geoRows.slice(0,50);
    limit.forEach(row=>{
      const dot=el('span','geo-marker '+(row.quality==='current'?'':'bad'));
      dot.style.left=((row.longitude+180)/360*100)+'%';
      dot.style.top=((90-row.latitude)/180*100)+'%';
      dot.title=(row.asset_tag||row.device_id)+' · '+row.quality;
      overlay.append(dot);
    });
    byId('geo-map-head').textContent=geoRows.length?
      geoRows.length+' device fix'+(geoRows.length===1?'':'es')+' · stored observations':
      'No GPS data · source unverified';
    button.disabled=!geoRows.length||!tileAllowed;
    byId('geo-tile-state').textContent=tileAllowed?
      'Street tiles are loaded only when you choose Show street map. Map provider may receive approximate location.':
      'Street map disabled here; tenant locations remain in the private coordinate preview.';
    if(!map)canvas.classList.remove('has-tiles');
    else updateMapMarkers();
  }
  function destroyMap(){
    if(map){map.remove();map=null;markers=null;}
    byId('geo-canvas').classList.remove('has-tiles');
    byId('geo-overlays').hidden=false;
  }
  function updateMapMarkers(){
    if(!map || !window.L)return;
    markers.clearLayers();
    const bounds=[];
    geoRows.forEach(row=>{
      const latlng=[row.latitude,row.longitude];
      bounds.push(latlng);
      window.L.circleMarker(latlng,{radius:9,color:row.quality==='current'?'#79edcf':'#f2bd87',
        fillColor:row.quality==='current'?'#21a991':'#c17e47',fillOpacity:.92,weight:2})
        .bindPopup('<strong>'+safe(row.asset_tag||row.device_id)+'</strong><br>'+
          safe(row.source)+' · '+safe(row.quality)+'<br>'+safe(asLocal(row.observed_at))).addTo(markers);
    });
    if(bounds.length)map.fitBounds(bounds,{padding:[35,35],maxZoom:14});
    setTimeout(()=>map?.invalidateSize(),100);
  }
  async function loadLeaflet(){
    if(window.L)return true;
    if(!document.getElementById('leaflet-css')){
      const link=el('link');link.id='leaflet-css';link.rel='stylesheet';
      link.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      link.integrity='sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
      link.crossOrigin='anonymous';document.head.append(link);
    }
    await new Promise((resolve,reject)=>{
      const script=el('script');script.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.integrity='sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
      script.crossOrigin='anonymous';script.onload=resolve;script.onerror=reject;document.head.append(script);
    });
    return !!window.L;
  }
  byId('geo-tiles').onclick=async()=>{
    if(!geoRows.length||!tileAllowed)return;
    const btn=byId('geo-tiles');btn.disabled=true;btn.textContent='Loading map…';
    try{
      if(!map){
        await loadLeaflet();
        map=window.L.map('fleet-map',{scrollWheelZoom:false,zoomControl:true});
        window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
          maxZoom:18,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
        }).addTo(map);
        markers=window.L.layerGroup().addTo(map);
        byId('geo-canvas').classList.add('has-tiles');
        byId('geo-overlays').hidden=true;
      }
      updateMapMarkers();
      btn.textContent='Street map active';
    }catch(_){
      destroyMap();btn.textContent='Map unavailable · retry';
      byId('geo-tile-state').textContent='Map library could not be loaded. Private coordinates remain available.';
    }finally{btn.disabled=false;}
  };
  byId('geo-reload').onclick=()=>loadGeo();
  async function loadGeo(){
    if(typeof identity==='undefined'||!identity){geoRows=[];renderGeo();return;}
    const serial=++geoSerial,session=(typeof generation==='number'?generation:-1);
    byId('geo-device-list').innerHTML='<div class="shell-empty">Loading stored GPS observations…</div>';
    try{
      const [rows,config]=await Promise.all([api('geo/positions'),api('map/config')]);
      if(serial!==geoSerial||session!==generation)return;
      geoRows=Array.isArray(rows)?rows.filter(x=>Number.isFinite(x.latitude)&&Number.isFinite(x.longitude)):[];
      tileAllowed=!!config.public_tiles_enabled;renderGeo();
    }catch(error){
      if(serial!==geoSerial)return;
      geoRows=[];renderGeo();
      byId('geo-device-list').textContent='GPS read failed: '+error.message;
    }
  }
  navigate(location.hash.slice(1)||'overview');
})();
