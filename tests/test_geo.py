"""Tenant-safe geographic read model, backed by actual persisted observations."""
from datetime import datetime, timezone

def test_map_only_shows_tenant_gps_evidence(authorized):
    api, auth = authorized['api'], authorized['headers']
    asset = api.post('/api/assets', headers=auth, json={
        'tag':'GPS-101', 'name':'Service vehicle'}).json()
    now = datetime.now(timezone.utc).isoformat()
    data={'asset_id':asset['id'], 'job_id':None, 'source':'manual',
          'source_event_id':'note-1','event_type':'qr_scan',
          'observed_at':now,'payload':{'latitude':-12.01,'longitude':-77.01}}
    assert api.post('/api/evidence',headers=auth,json=data).status_code==201
    assert api.get('/api/geo/positions',headers=auth).json()==[]
    credential=api.post('/api/credentials',headers=auth,json={
        'name':'Traccar polling', 'role':'connector','source':'traccar'})
    assert credential.status_code==201
    gps_headers={'Authorization':'Bearer '+credential.json()['api_token']}
    data.update({'source':'traccar','source_event_id':'traccar-001',
        'event_type':'gps_position_reported',
        'payload':{'device_id':31,'latitude':-12.01,'longitude':-77.01,'valid':True}})
    assert api.post('/api/evidence',headers=gps_headers,json=data).status_code==201
    positions=api.get('/api/geo/positions',headers=auth)
    assert positions.status_code==200
    assert len(positions.json())==1
    assert positions.json()[0]['asset_tag']=='GPS-101'
    assert positions.json()[0]['quality']=='current'
    other=api.post('/api/tenants',headers={'X-Admin-Key':'a'*40},
                   json={'name':'Independent customer'}).json()
    other_headers={'Authorization':'Bearer '+other['api_token']}
    assert api.get('/api/geo/positions',headers=other_headers).json()==[]
    assert api.get('/api/map/config',headers=other_headers).status_code==200
    assert api.get('/api/geo/positions',headers=gps_headers).status_code==403

def test_map_deduplicates_and_marks_bad_fixes(authorized):
    api,auth=authorized['api'],authorized['headers']
    asset=api.post('/api/assets',headers=auth,json={'tag':'GPS-102','name':'Van'}).json()
    cred=api.post('/api/credentials',headers=auth,json={
        'name':'Traccar','role':'connector','source':'traccar'}).json()
    token={'Authorization':'Bearer '+cred['api_token']}
    now=datetime.now(timezone.utc).isoformat()
    for n in (1,2):
        response=api.post('/api/evidence',headers=token,json={
            'asset_id':asset['id'],'source':'traccar','source_event_id':f'gps-{n}',
            'event_type':'gps_position_reported','observed_at':now,
            'payload':{'device_id':777,'latitude':-12.1+n/1000,
                       'longitude':-77.1,'valid':False}})
        assert response.status_code==201
    rows=api.get('/api/geo/positions',headers=auth).json()
    assert len(rows)==1
    assert rows[0]['quality']=='unverified'
    assert rows[0]['device_id']=='777'
