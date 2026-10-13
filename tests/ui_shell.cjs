/* Rally navigation smoke: actual browser DOM construction, without provider APIs. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');
const webDir = path.join(__dirname, '..', 'rally', 'web');
const source = file => fs.readFileSync(path.join(webDir, file), 'utf8');
let html = source('index.html');
html = html.replace('<script src="/static/app.js" defer></script>',
                    '<script>' + source('app.js') + '</script>');
html = html.replace('<script src="/static/shell.js" defer></script>',
                    '<script>' + source('shell.js') + '</script>');
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError',err=>errors.push(err));
virtualConsole.on('error',msg=>errors.push(new Error(String(msg))));
const dom = new JSDOM(html, {
  url: 'http://localhost:8080/', runScripts: 'dangerously', virtualConsole,
  pretendToBeVisual: true,
  beforeParse(window){
    window.scrollTo = () => {};
    window.HTMLDialogElement.prototype.close = function(){this.open=false;};
    window.HTMLDialogElement.prototype.showModal = function(){this.open=true;};
  }
});
const document = dom.window.document;
assert.equal(errors.length,0,errors.map(x=>x.message).join('\n'));
assert.ok(document.body.classList.contains('rally-shell'), 'Shell must be initialized');
assert.equal(document.querySelectorAll('[data-screen]').length, 8);
assert.ok(document.querySelector('[data-screen="overview"] #token'));
assert.ok(document.querySelector('[data-screen="assets"] #issue'));
assert.ok(document.querySelector('[data-screen="work"] #new-job'));
assert.ok(document.querySelector('[data-screen="evidence"] #new-evidence'));
assert.ok(document.querySelector('[data-screen="integrations"] #connectors'));
assert.equal(document.querySelectorAll('[data-screen="integrations"] .erp-domain').length, 8);
assert.match(document.querySelector('[data-screen="integrations"] .erp-domain-catalog').textContent,/Payments/);
assert.match(document.querySelector('[data-screen="integrations"] .erp-domain-catalog').textContent,/not wired/);
assert.ok(document.querySelector('[data-screen="governance"] #credentials'));
assert.ok(document.querySelector('[data-screen="fleet"] #fleet-map'));
assert.ok(document.querySelector('link[href="/static/shell.css"]'));
assert.equal(document.querySelector('[data-screen="fleet"]').hidden, true);
document.querySelector('[data-go="fleet"]').click();
assert.equal(document.querySelector('[data-screen="fleet"]').hidden, false);
assert.equal(document.querySelector('[data-screen="overview"]').hidden, true);
assert.match(document.querySelector('#geo-device-list').textContent,/No GPS events/);
assert.equal(document.querySelector('#geo-tiles').disabled,true);
document.querySelector('[data-go="assets"]').click();
assert.equal(document.querySelector('[data-screen="assets"]').hidden, false);
assert.equal(document.querySelector('#current-view').textContent,'Equipment & custody');
dom.window.dispatchEvent(new dom.window.CustomEvent('rally:state',{detail:{
 identity:{name:'QA operator',role:'admin',tenant_id:'qa'},
 stats:{assets:1,jobs:1,active_custody:1,open_cases:1,evidence_events:1},
 assets:[{id:'a-1',tag:'CAM-001',name:'Inspection camera',status:'ready'}],
 custody:[{id:'c-1',asset_id:'a-1',holder:'Technician A',state:'active'}],
 coverage:[{source:'traccar',coverage:'stale',name:'GPS adapter'}]
}}));
assert.match(document.querySelector('#asset-register').textContent,/CAM-001/);
assert.match(document.querySelector('#asset-register').textContent,/Technician A/);
assert.match(document.querySelector('#overview-attention').textContent,/1 exception/);
assert.match(document.querySelector('#source-traccar').textContent,/Configured/);
console.log('Rally: eight routes, preserved forms, safe empty GPS view and navigation passed.');
dom.window.close();
