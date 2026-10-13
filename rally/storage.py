"""SQLite reference persistence, transactions and tenant-local uniqueness.

SQLite is suited to the single-instance MK0 pilot. Production multi-replica deployment
requires a reviewed PostgreSQL migration, backups, authorization and observability.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  tag TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready',
  created_at TEXT NOT NULL, UNIQUE(tenant_id, tag)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  external_ref TEXT NOT NULL, title TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'planned',
  created_at TEXT NOT NULL, completed_at TEXT,
  UNIQUE(tenant_id, external_ref)
);
CREATE TABLE IF NOT EXISTS custody (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  asset_id TEXT NOT NULL REFERENCES assets(id), job_id TEXT REFERENCES jobs(id),
  holder TEXT NOT NULL, state TEXT NOT NULL, issued_at TEXT NOT NULL,
  due_at TEXT, returned_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_asset
  ON custody(tenant_id, asset_id) WHERE state='active';
CREATE TABLE IF NOT EXISTS evidence (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  asset_id TEXT REFERENCES assets(id), job_id TEXT REFERENCES jobs(id),
  source TEXT NOT NULL, source_event_id TEXT NOT NULL,
  event_type TEXT NOT NULL, observed_at TEXT NOT NULL,
  payload TEXT NOT NULL, received_at TEXT NOT NULL,
  UNIQUE(tenant_id, source, source_event_id)
);
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  fingerprint TEXT NOT NULL, kind TEXT NOT NULL, severity TEXT NOT NULL,
  state TEXT NOT NULL, description TEXT NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, resolved_at TEXT,
  UNIQUE(tenant_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS audit (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  entity TEXT NOT NULL, entity_id TEXT NOT NULL, action TEXT NOT NULL,
  details TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
  tenant_id TEXT NOT NULL REFERENCES tenants(id), operation TEXT NOT NULL,
  key TEXT NOT NULL, request_hash TEXT NOT NULL, response TEXT NOT NULL,
  PRIMARY KEY(tenant_id, operation, key)
);
CREATE INDEX IF NOT EXISTS idx_asset_tenant ON assets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_job_tenant ON jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_evidence_tenant ON evidence(tenant_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_case_tenant ON cases(tenant_id, state);
"""

def database_path() -> str:
    return os.getenv("RALLY_DB_PATH", "./data/rally.db")

def connect(path=None):
    path = path or database_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, isolation_level=None, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=20000")
    return con

def initialize(path=None):
    with connect(path) as con:
        con.executescript(SCHEMA)

def get_db():
    con = connect()
    try:
        yield con
    finally:
        con.close()

def one(con, sql, args=()):
    row = con.execute(sql, args).fetchone()
    return dict(row) if row else None

def all_rows(con, sql, args=()):
    return [dict(x) for x in con.execute(sql, args).fetchall()]
