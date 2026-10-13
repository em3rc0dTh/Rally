"""Versioned persistence. PostgreSQL for production; SQLite for local development."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None

IntegrityError = (sqlite3.IntegrityError,) + ((psycopg.IntegrityError,) if psycopg else ())
OperationalError = (sqlite3.OperationalError,) + ((psycopg.OperationalError,) if psycopg else ())

SCHEMA = """

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

MIGRATIONS = [SCHEMA, """
CREATE TABLE IF NOT EXISTS credentials (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','operator','reviewer','viewer','connector')),
 token_hash TEXT NOT NULL UNIQUE, source TEXT, created_at TEXT NOT NULL,
 expires_at TEXT, revoked_at TEXT
);
ALTER TABLE audit ADD COLUMN actor_id TEXT;
ALTER TABLE cases ADD COLUMN owner_id TEXT;
ALTER TABLE cases ADD COLUMN acknowledged_at TEXT;
CREATE TABLE case_notes (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 case_id TEXT NOT NULL REFERENCES cases(id), actor_id TEXT NOT NULL,
 note TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE connector_status (
 tenant_id TEXT NOT NULL REFERENCES tenants(id), name TEXT NOT NULL,
 last_attempt TEXT NOT NULL, last_success TEXT, status TEXT NOT NULL,
 detail TEXT NOT NULL, PRIMARY KEY(tenant_id,name)
);
CREATE TABLE worker_status (name TEXT PRIMARY KEY, last_success TEXT NOT NULL);
CREATE INDEX idx_custody_scan ON custody(tenant_id,state,due_at);
CREATE INDEX idx_audit_tenant ON audit(tenant_id,created_at,id);
CREATE INDEX idx_credential_tenant ON credentials(tenant_id);
CREATE INDEX idx_case_notes ON case_notes(tenant_id,case_id,created_at);
""", """
CREATE UNIQUE INDEX uq_asset_tenant_id ON assets(tenant_id,id);
CREATE UNIQUE INDEX uq_job_tenant_id ON jobs(tenant_id,id);
"""]

class Connection:
    def __init__(self, raw, postgres=False):
        self.raw, self.postgres = raw, postgres
        self.actor_id = 'system'
        self.actor_role = 'system'
        self.actor_source = None
        self.actor_scope = None

    def execute(self, sql, args=()):
        if self.postgres:
            if sql == 'BEGIN IMMEDIATE':
                self.raw.execute('BEGIN')
                self.raw.execute("SET LOCAL lock_timeout = '20s'")
                # All application writes use this transaction lock. Conservative and
                # cross-process safe; shard by tenant only after measured demand.
                return self.raw.execute('SELECT pg_advisory_xact_lock(72419001)')
            sql = sql.replace('?', '%s')
        return self.raw.execute(sql, args)

    def commit(self):
        if self.postgres:
            self.raw.execute('COMMIT')
        else:
            self.raw.commit()

    def rollback(self):
        if self.postgres:
            self.raw.execute('ROLLBACK')
        else:
            self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.close()


def database_path():
    return os.getenv('RALLY_DB_PATH', './data/rally.db')


def connect(path=None):
    url = os.getenv('RALLY_DATABASE_URL', '') if path is None else ''
    if url:
        if not psycopg:
            raise RuntimeError('Install Rally PostgreSQL dependencies')
        return Connection(psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=10), True)
    path = path or database_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path, isolation_level=None, timeout=20, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.execute('PRAGMA foreign_keys=ON')
    raw.execute('PRAGMA busy_timeout=20000')
    return Connection(raw)


@contextmanager
def transaction(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise


def initialize(path=None):
    with connect(path) as db:
        if db.postgres and os.getenv('RALLY_ENV') == 'production':
            privileges = db.execute(
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication "
                "FROM pg_roles WHERE rolname=current_user"
            ).fetchone()
            if not privileges or any(privileges.values()):
                raise RuntimeError(
                    'Production Rally database account must not have server-wide administrator privileges'
                )
        if not db.postgres:
            db.execute('PRAGMA journal_mode=WAL')
        with transaction(db):
            db.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)')
            versions = {r['version'] for r in db.execute('SELECT version FROM schema_migrations').fetchall()}
            supported = set(range(1, 9))
            if versions - supported:
                raise RuntimeError('Database schema is newer than this Rally build; use an approved matching release')
            for version, sql in enumerate(MIGRATIONS, 1):
                if version in versions:
                    continue
                for statement in sql.split(';'):
                    if statement.strip():
                        db.execute(statement)
                db.execute('INSERT INTO schema_migrations(version) VALUES(?)', (version,))
            # Preserve existing MK0 bearer keys as revocable tenant admin identities.
            db.execute("INSERT INTO credentials(id,tenant_id,name,role,token_hash,created_at) "
                       "SELECT id,id,'Bootstrap administrator','admin',token_hash,created_at FROM tenants WHERE 1=1 "
                       "ON CONFLICT DO NOTHING")
            # Version 4 is reserved on both backends for PostgreSQL tenant constraints.
            # Compound foreign keys enforce tenant isolation in PostgreSQL as well as API.
            if db.postgres and 4 not in versions:
                for table in ('custody', 'evidence'):
                    for column, parent in (('asset_id', 'assets'), ('job_id', 'jobs')):
                        db.execute(f'ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_tenant_fk '
                                   f'FOREIGN KEY(tenant_id,{column}) REFERENCES {parent}(tenant_id,id)')
            if 4 not in versions:
                db.execute('INSERT INTO schema_migrations(version) VALUES(4)')
            # Version 5: explicit origin ownership prevents provider credentials
            # from claiming manually created or legacy work orders.
            if 5 not in versions:
                db.execute("ALTER TABLE jobs ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
                db.execute('INSERT INTO schema_migrations(version) VALUES(5)')
            # Version 6: each Odoo connector is limited to exactly one ERP namespace.
            # Preexisting Odoo tokens have no scope: revoke/reissue after upgrade.
            if 6 not in versions:
                db.execute("ALTER TABLE credentials ADD COLUMN scope TEXT")
                db.execute('INSERT INTO schema_migrations(version) VALUES(6)')

            # Version 7: independently scoped, state-only Odoo enterprise mirror.
            # No employee names, payroll amounts or account details are replicated.
            if 7 not in versions:
                statements = [
                    """CREATE TABLE erp_grants (
                      tenant_id TEXT NOT NULL REFERENCES tenants(id),
                      credential_id TEXT NOT NULL REFERENCES credentials(id),
                      company_id INTEGER NOT NULL,
                      model TEXT NOT NULL,
                      created_at TEXT NOT NULL,
                      PRIMARY KEY(tenant_id,credential_id,company_id,model))""",
                    """CREATE TABLE erp_records (
                      id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
                      instance TEXT NOT NULL, company_id INTEGER NOT NULL,
                      model TEXT NOT NULL, record_id INTEGER NOT NULL,
                      state TEXT NOT NULL, source_modified_at TEXT NOT NULL,
                      first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                      UNIQUE(tenant_id,instance,company_id,model,record_id))""",
                    """CREATE TABLE erp_state_changes (
                      id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
                      erp_record_id TEXT NOT NULL REFERENCES erp_records(id),
                      previous_state TEXT, current_state TEXT NOT NULL,
                      source_modified_at TEXT NOT NULL, received_at TEXT NOT NULL)""",
                    "CREATE INDEX idx_erp_records_scope ON erp_records(tenant_id,model,company_id,last_seen)",
                    "CREATE INDEX idx_erp_changes_record ON erp_state_changes(tenant_id,erp_record_id,received_at)"
                ]
                for statement in statements:
                    db.execute(statement)
                db.execute('INSERT INTO schema_migrations(version) VALUES(7)')

            # Version 8: only tenant administrators may opt in to state-age rules.
            if 8 not in versions:
                db.execute("""CREATE TABLE erp_policies (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    instance TEXT NOT NULL,
                    company_id INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    state TEXT NOT NULL,
                    max_age_seconds INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id,instance,company_id,model,state)
                )""")
                db.execute("CREATE INDEX idx_erp_policies_tenant ON erp_policies(tenant_id,enabled)")
                db.execute('INSERT INTO schema_migrations(version) VALUES(8)')


def get_db():
    with connect() as db:
        yield db


def one(db, sql, args=()):
    row = db.execute(sql, args).fetchone()
    return dict(row) if row else None


def all_rows(db, sql, args=()):
    return [dict(x) for x in db.execute(sql, args).fetchall()]
