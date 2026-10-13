"""Durable local RFID spool. Read NDJSON stdin or --drain retained events.

Source must retain input until spool acknowledgment. Disk spool belongs to ONE
Rally tenant and reader namespace. Poison events remain for operator correction.
"""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys
from hashlib import sha256
from adapters.rfid import rfid_evidence
from adapters.transport import RallyClient


async def main():
    client = RallyClient()
    mapping = json.loads(os.environ['RFID_EPC_ASSET_MAP'])
    mapping = {k.upper(): v for k, v in mapping.items()}
    path = Path(os.getenv('RFID_SPOOL_PATH', './data/rfid-spool.db'))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE IF NOT EXISTS spool(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS binding(id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL)')
    max_events = int(os.getenv('RFID_MAX_SPOOL_EVENTS', '100000'))
    if max_events < 1:
        raise ValueError('RFID_MAX_SPOOL_EVENTS must be positive')
    max_bytes = int(os.getenv('RFID_MAX_SPOOL_BYTES', '268435456'))
    if max_bytes < 16777216 or max_bytes > 10737418240:
        raise ValueError('RFID spool disk budget out of allowed range')
    page_size = db.execute('PRAGMA page_size').fetchone()[0]
    max_pages = max_bytes // page_size
    if db.execute('PRAGMA page_count').fetchone()[0] > max_pages:
        raise RuntimeError('Existing spool is larger than allowed capacity')
    db.execute('PRAGMA max_page_count=' + str(max_pages))
    import httpx
    from adapters.transport import request
    async with httpx.AsyncClient(timeout=30) as http:
        response = await request(http, 'GET', client.base + '/api/me', headers={'Authorization': 'Bearer ' + client.token})
        tenant_id = response.json()['tenant_id']
    bound = db.execute('SELECT tenant_id FROM binding WHERE id=1').fetchone()
    if bound and bound[0] != tenant_id:
        raise RuntimeError('Spool belongs to another tenant; use a separate path')
    db.execute('INSERT OR IGNORE INTO binding VALUES(1,?)', (tenant_id,))
    db.commit()
    async def drain():
        for event_id, payload in db.execute('SELECT id,payload FROM spool ORDER BY rowid LIMIT 500').fetchall():
            try:
                await client.post('evidence', json.loads(payload))
            except Exception as error:
                await client.heartbeat('error', 'RFID spool pending: ' + type(error).__name__)
                raise
            db.execute('DELETE FROM spool WHERE id=?', (event_id,))
            db.commit()
        await client.heartbeat('ok', 'RFID spool batch delivered; heartbeat does not prove reader activity')
    try:
        if '--drain' in sys.argv:
            while db.execute('SELECT 1 FROM spool LIMIT 1').fetchone():
                await drain()
            return
        while True:
            raw = sys.stdin.buffer.readline(65537)
            if not raw:
                break
            if len(raw) > 65536:
                raise ValueError('RFID input event exceeds 64 KiB')
            if not raw.strip():
                continue
            event = rfid_evidence(json.loads(raw.decode('utf-8')), mapping)
            payload = json.dumps(event, sort_keys=True)
            event_id = event['source_event_id']
            old = db.execute('SELECT payload FROM spool WHERE id=?', (event_id,)).fetchone()
            if old and old[0] != payload:
                raise ValueError('Conflicting RFID source ID in spool')
            if not old and db.execute('SELECT COUNT(*) FROM spool').fetchone()[0] >= max_events:
                raise RuntimeError('RFID spool event limit reached; stop reader input and drain or recover the spool')
            db.execute('INSERT OR IGNORE INTO spool VALUES(?,?)', (event_id, payload))
            db.commit()
            print(json.dumps({'spooled': event_id}), flush=True)
            await drain()
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
