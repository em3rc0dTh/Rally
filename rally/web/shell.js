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
  dual(assets,panels.assetForm,panels.issueForm);
  const assetRegister=el('section','panel',`<h2>Asset register</h2><p class="muted">Operational inventory linked to handover history.</p>
    <div class="scroll"><table><thead><tr><th>Tag</th><th>Equipment</th><th>Availability</th><th>Current holder</th></tr></thead>
    <tbody id="asset-register"><tr><td colspan="4">Connect to view equipment.</td></tr></tbody></table></div>`);
  assets.append(assetRegister,panels.custody);
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
    <div class="integration-card"><span class="shell-label">ERP · Business context</span><h3>Odoo 19</h3>
      <span id="source-odoo" class="badge">Not connected</span>
      <p>Odoo covers CRM, sales, procurement, stock, workforce, accounting and payments when licensed/installed. <strong>Current Rally connector only imports explicitly selected confirmed sales as work-order candidates.</strong> No HR, invoice or payment-state sync is connected.</p>
      <a href="https://www.odoo.com/documentation/19.0/developer/reference/external_api.html" target="_blank" rel="noopener noreferrer">Official Odoo JSON-2 API ↗</a></div>
    <div class="integration-card"><span class="shell-label">GPS · Reported position</span><h3>Traccar</h3>
      <span id="source-traccar" class="badge">Not connected</span>
      <p>Ingest device positions with explicit asset mapping and freshness checks. Actual device state appears in Fleet & GPS.</p>
      <a href="https://www.traccar.org/api-reference/" target="_blank" rel="noopener noreferrer">Official Traccar API ↗</a></div>
    <div class="integration-card"><span class="shell-label">Physical · Device sighting</span><h3>RFID / QR</h3>
      <span id="source-rfid" class="badge">Not connected</span>
      <p>Edge readings and manual observations are evidence inputs, never an automatic custody handover or return.</p>
      <button type="button" data-go="evidence">Inspect evidence ↗</button></div>`;

  const setupGuides=el('section','panel');
  setupGuides.innerHTML=`<h2>Connector activation — deployment controlled</h2>
    <p>Rally does not ask for Odoo or Traccar secrets in the browser. Use restricted provider credentials on the deployment host and associate them with a dedicated connector identity.</p>
    <div class="screen-dual">
      <details class="shell-setup"><summary>Odoo → work-order import <span class="muted">3 steps</span></summary>
        <ol><li>Issue a credential with role <code>connector</code>, source <code>odoo</code>, and an exact instance namespace.</li>
        <li>Configure <code>ODOO_URL</code>, <code>ODOO_DATABASE</code>, <code>ODOO_API_KEY</code>,
        <code>ODOO_INSTANCE</code>, <code>ODOO_COMPANY_IDS</code> and a customer-approved <code>ODOO_WORKORDER_DOMAIN_JSON</code>.</li>
        <li>Set <code>RALLY_URL</code> and the connector <code>RALLY_TENANT_TOKEN</code>; run <code>python -m adapters.odoo_sync_cli</code> in the deployment environment.</li></ol>
        <p>Only explicitly selected confirmed sales are candidates. No automatic writes back to Odoo.</p>
      </details>
      <details class="shell-setup"><summary>Traccar → Fleet & GPS <span class="muted">3 steps</span></summary>
        <ol><li>Issue a source-scoped <code>traccar</code> connector credential in Audit & access.</li>
        <li>Configure <code>TRACCAR_URL</code>, <code>TRACCAR_TOKEN</code> and <code>TRACCAR_DEVICE_ASSET_MAP</code> on the host.</li>
        <li>Set <code>RALLY_URL</code> and <code>RALLY_TENANT_TOKEN</code>; run <code>python -m adapters.ingest_cli</code>, then open Fleet & GPS.</li></ol>
        <p>Poller sends latest reported positions. Real-time Traccar WebSocket is not implemented here.</p>
      </details>
      <details class="shell-setup"><summary>RFID edge → evidence <span class="muted">2 steps</span></summary>
        <ol><li>Provision a device-scoped reader identity and explicitly map EPC values through <code>RFID_EPC_ASSET_MAP</code>.</li>
        <li>Supply authenticated normalized events to <code>python -m adapters.rfid_ingest_cli</code>.</li></ol>
        <p>Readings are observations, not automatic custody transfers. Verify the physical reader.</p>
      </details>
    </div>`;
  const erpDomains=el('section','panel erp-domain-catalog');
  erpDomains.innerHTML=`<h2>Odoo business domains — expansion reference</h2>
    <p>ERP applications are broader than work orders. These are <strong>integration candidates</strong> derived from the Odoo reference repository and native Odoo capabilities. They are not connected, imported, or monitored by Rally today. The current Odoo connector covers only explicitly selected confirmed sales.</p>
    <div class="erp-domain-grid" aria-label="Planned Odoo domain coverage">
      <article class="erp-domain"><span class="shell-label">CRM &amp; customers</span><h3>Leads, contacts and customer handoffs</h3><p>Track the transition from commercial commitment to accountable execution.</p><span class="erp-domain-status">Reference only · not wired</span></article>
      <article class="erp-domain"><span class="shell-label">Sales &amp; field work</span><h3>Sales, work orders and services</h3><p>Current scope: selected sales imported as jobs; service correlation remains planned.</p><span class="erp-domain-status">Partial · selected-sale importer only</span></article>
      <article class="erp-domain"><span class="shell-label">Procurement</span><h3>Orders, suppliers and receipts</h3><p>Planned detection of expected versus verified procurement outcomes.</p><span class="erp-domain-status">Reference only · not wired</span></article>
      <article class="erp-domain"><span class="shell-label">Inventory</span><h3>Stock, locations and serialized assets</h3><p>Compare ERP inventory obligations with physical observations and custody.</p><span class="erp-domain-status">Reference only · not wired</span></article>
      <article class="erp-domain"><span class="shell-label">Workforce</span><h3>Employees, attendance and leave</h3><p>Candidate exception workflow for unjustified absence, late attendance and approvals.</p><span class="erp-domain-status">Reference only · sensitive HR</span></article>
      <article class="erp-domain"><span class="shell-label">Payroll &amp; expenses</span><h3>Payslips, reimbursements and approvals</h3><p>Future approval and exception states, not payroll calculations or payment execution.</p><span class="erp-domain-status">Reference only · sensitive HR</span></article>
      <article class="erp-domain"><span class="shell-label">Accounting</span><h3>Invoices and financial documents</h3><p>Proposed verification of pending documents, missing invoices and accountable recovery.</p><span class="erp-domain-status">Proposed · not in reference adapter</span></article>
      <article class="erp-domain"><span class="shell-label">Payments</span><h3>Collections and reconciliation</h3><p>Proposed cross-system status verification; payment execution remains out of scope.</p><span class="erp-domain-status">Proposed · not in reference adapter</span></article>
    </div>
    <p class="erp-domain-footnote">Source model, company restrictions, field availability, data retention and API edition must be validated for each customer's actual Odoo deployment. No HR or financial figures are displayed without authoritative integration.</p>`;
  const erpLive = el('section','panel erp-live-panel');
  erpLive.innerHTML=`<h2>Enterprise ERP state mirror</h2>
    <p>Read-only, tenant-bound snapshots from explicitly authorized Odoo models. No salaries, invoice amounts, banking details or employee identity are displayed. <strong>Only tenant administrators can load this data.</strong></p>
    <button type="button" id="erp-load-state">↻ Load approved ERP states</button>
    <div id="erp-live-result" aria-live="polite"><div class="shell-empty">No ERP query made yet. The source requires a valid Odoo instance, dedicated credential, model/company grant and explicit selector.</div></div>`;
  integrations.append(integrationCards,setupGuides,erpDomains,erpLive,panels.connectorsHead,panels.connectors);
  byId('erp-load-state').onclick=async()=>{
    const btn=byId('erp-load-state'), host=byId('erp-live-result');
    if(typeof identity==='undefined'||!identity||identity.role!=='admin'){
      host.textContent='Tenant administrator access required.';return;
    }
    btn.disabled=true;host.textContent='Loading authorized Odoo state records…';
    try{
      const [summary, grants] = await Promise.all([api('erp/summary'),api('erp/grants')]);
      if(!Array.isArray(summary)||!Array.isArray(grants))throw new Error('Unexpected ERP response');
      const grantCount=grants.length;
      if(!summary.length){
        host.innerHTML='<div class="shell-empty">No Odoo enterprise records imported yet. Approved model/company grants: '
          +grantCount+'. Configure the connector privately on the deployment host. No source data is fabricated.</div>';
      }else{
        const count=summary.reduce((n,r)=>n+Number(r.records||0),0);
        host.innerHTML='<p class="erp-live-count">'+count+' mirrored ERP record'+(count===1?'':'s')+
          ' · '+summary.length+' state group'+(summary.length===1?'':'s')+
          ' · '+grantCount+' approved model/company grant'+(grantCount===1?'':'s')+'</p>'+
          '<div class="erp-live-scroll"><table><thead><tr><th>Instance</th><th>Company ID</th><th>Model</th><th>State</th><th>Records</th><th>Last seen</th></tr></thead><tbody>'+
          summary.map(r=>'<tr><td>'+safe(r.instance)+'</td><td>'+safe(r.company_id)+'</td><td>'+safe(r.model)+
          '</td><td>'+safe(r.state)+'</td><td>'+safe(r.records)+'</td><td>'+safe(asLocal(r.last_seen))+'</td></tr>').join('')+
          '</tbody></table></div>';
      }
    }catch(error){host.textContent='ERP data unavailable: '+error.message;}
    finally{btn.disabled=false;}
  };
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
    const assetList=detail.assets||[], activeCustody=(detail.custody||[]).filter(x=>x.state==='active');
    const assignedByAsset=new Map(activeCustody.map(x=>[x.asset_id,x]));
    byId('asset-register').innerHTML=assetList.map(x=>{
      const assigned=assignedByAsset.get(x.id);
      return '<tr><td><strong>'+safe(x.tag)+'</strong></td><td>'+safe(x.name)+
        '</td><td><span class="badge '+(assigned?'warn':'')+'">'+
        safe(assigned?'Assigned':x.status||'Ready')+'</span></td><td>'+
        safe(assigned?.holder||'—')+'</td></tr>';
    }).join('')||'<tr><td colspan="4">No equipment registered for this tenant.</td></tr>';
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
    button.disabled=!tileAllowed;
    byId('geo-tile-state').textContent=tileAllowed?
      'Street tiles load only by user action. Without devices the map starts at a neutral world view; real device coordinates may be disclosed if available.':
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
    else map.setView([0,0],2);
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
    if(!tileAllowed)return;
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
