"""Rally operations API. Each credential resolves to one tenant; never trust a tenant ID from clients.

Guarantees: unique active custody in SQLite, idempotent state-changing custody requests,
immutable-by-API evidence, typed reconciliation exceptions. Not production-certified.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from typing import Any, Literal
from uuid import uuid4
import json
import os
import logging
import math
import re
from datetime import timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

from rally.storage import all_rows, get_db, initialize, one, transaction, IntegrityError, OperationalError
from rally.security import GuardMiddleware, validate_environment
from rally.erp_contract import MODEL_CONTRACTS, MODEL_NAMES, STATE, NAMESPACE
from rally.erp_policies import policy_conditions, may_resolve_erp_case

def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def uid() -> str:
    return str(uuid4())

def normalized_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise HTTPException(422, "Timestamp must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")

class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", allow_inf_nan=False)

class TenantIn(Input):
    name: str = Field(min_length=2, max_length=150)

class AssetIn(Input):
    tag: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=250)

class JobIn(Input):
    external_ref: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=250)

class IssueIn(Input):
    asset_id: str
    job_id: str | None = None
    holder: str = Field(min_length=1, max_length=250)
    due_at: datetime | None = None

class ReturnIn(Input):
    custody_id: str
    confirmed_by: str | None = Field(default=None, min_length=1, max_length=250)

class EvidenceIn(Input):
    asset_id: str | None = None
    job_id: str | None = None
    source: Literal["manual", "qr", "rfid", "gps", "traccar", "odoo"]
    source_event_id: str = Field(min_length=1, max_length=150)
    event_type: str = Field(min_length=1, max_length=80)
    observed_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    validate_environment()
    initialize()
    yield

app = FastAPI(
    title="Rally Business Execution Assurance", version="0.2.0", lifespan=lifespan,
    docs_url="/docs" if os.getenv("RALLY_ENV") != "production" else None,
    redoc_url=None, openapi_url="/openapi.json" if os.getenv("RALLY_ENV") != "production" else None,
    description="Tenant-scoped asset custody, work orders, evidence and exception reconciliation."
)

def require_admin(x_admin_key: str | None = Header(default=None)):
    expected = os.getenv("RALLY_ADMIN_KEY", "")
    if len(expected) < 32 or not x_admin_key or not compare_digest(expected, x_admin_key):
        raise HTTPException(403, "Valid admin credential required")
    return True

def tenant(request: Request, authorization: str | None = Header(default=None), db=Depends(get_db)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    raw = authorization.removeprefix("Bearer ").strip()
    if not 32 <= len(raw) <= 256:
        raise HTTPException(401, "Invalid bearer token")
    row = one(db, "SELECT * FROM credentials WHERE token_hash=? AND revoked_at IS NULL "
                  "AND (expires_at IS NULL OR expires_at>?)", (sha256(raw.encode()).hexdigest(), stamp()))
    if not row:
        raise HTTPException(401, "Invalid or expired bearer token")
    role, path = row["role"], request.url.path
    if request.method not in {"GET", "HEAD"}:
        allowed = role in {"admin", "operator"}
        if role == "reviewer":
            allowed = path == "/api/reconcile" or path.startswith("/api/cases/")
        if role == "connector":
            allowed = path in {"/api/evidence", "/api/connectors/heartbeat"} or (
                (row["source"] == "odoo" and path == "/api/jobs/import") or
                (row["source"] == "odoo_enterprise" and path == "/api/erp/records/import"))
        if not allowed:
            raise HTTPException(403, "Credential role does not permit this operation")
    elif role == "connector" and path != "/api/me":
        raise HTTPException(403, "Connector credentials cannot browse operational data")
    db.actor_id, db.actor_role, db.actor_source = row["id"], role, row["source"]
    db.actor_scope = row["scope"]
    return row["tenant_id"]


def tenant_admin(tid=Depends(tenant), db=Depends(get_db)):
    if db.actor_role != "admin":
        raise HTTPException(403, "Tenant administrator required")
    return tid

def audit(db, tid, entity, eid, action, details=None):
    db.execute(
        "INSERT INTO audit (id,tenant_id,entity,entity_id,action,details,created_at,actor_id) VALUES (?,?,?,?,?,?,?,?)",
        (uid(), tid, entity, eid, action, json.dumps(details or {}, sort_keys=True), stamp(), db.actor_id)
    )

def within_tenant(db, table, tid, item_id):
    if table not in {"assets", "jobs", "custody"}:
        raise ValueError("Disallowed table")
    row = one(db, "SELECT * FROM " + table + " WHERE id=? AND tenant_id=?", (item_id, tid))
    if not row:
        raise HTTPException(404, "Record not found for this tenant")
    return row

def perform(db, tid, operation: str, key: str, data: dict, action):
    if not key or not 8 <= len(key) <= 128:
        raise HTTPException(422, "Idempotency-Key must contain 8–128 characters")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    request_hash = sha256(canonical.encode()).hexdigest()
    try:
        db.execute("BEGIN IMMEDIATE")
        old = one(db, "SELECT request_hash,response FROM idempotency WHERE tenant_id=? AND operation=? AND key=?",
                  (tid, operation, key))
        if old:
            if old["request_hash"] != request_hash:
                raise HTTPException(409, "Idempotency key reused with different request")
            db.commit()
            return json.loads(old["response"])
        result = action()
        db.execute(
            "INSERT INTO idempotency(tenant_id,operation,key,request_hash,response) VALUES(?,?,?,?,?)",
            (tid, operation, key, request_hash, json.dumps(result, sort_keys=True))
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Uniqueness or referential-integrity conflict") from error
    except Exception:
        db.rollback()
        raise

@app.get("/")
def home():
    return FileResponse(Path(__file__).resolve().parent / "web" / "index.html")

@app.get("/healthz")
def health():
    return {"status": "ok", "product": "Rally", "version": "0.2.0"}

@app.post("/api/tenants", dependencies=[Depends(require_admin)], status_code=201)
def create_tenant(payload: TenantIn, db=Depends(get_db)):
    token = token_urlsafe(48)
    tid = uid()
    with transaction(db):
        db.execute("INSERT INTO tenants(id,name,token_hash,created_at) VALUES(?,?,?,?)",
                   (tid, payload.name, sha256(token.encode()).hexdigest(), stamp()))
        db.execute("INSERT INTO credentials(id,tenant_id,name,role,token_hash,created_at) VALUES(?,?,?,'admin',?,?)",
                   (tid, tid, "Bootstrap administrator", sha256(token.encode()).hexdigest(), stamp()))
        db.actor_id = "platform-admin"
        audit(db, tid, "tenant", tid, "created")
    # Token is revealed only at creation; store it securely. No token-recovery endpoint exists.
    return {"tenant_id": tid, "name": payload.name.strip(), "api_token": token}

@app.post("/api/assets", status_code=201)
def create_asset(body: AssetIn, tid: str = Depends(tenant), db=Depends(get_db)):
    tag, name, aid = body.tag.strip().upper(), body.name.strip(), uid()
    if not tag or not name:
        raise HTTPException(422, "Tag and name are required")
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO assets(id,tenant_id,tag,name,created_at) VALUES(?,?,?,?,?)",
                   (aid, tid, tag, name, stamp()))
        audit(db, tid, "asset", aid, "registered", {"tag": tag})
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Asset tag already exists") from e
    return within_tenant(db, "assets", tid, aid)

@app.get("/api/assets")
def assets(tid: str = Depends(tenant), db=Depends(get_db), limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
    return all_rows(db, "SELECT * FROM assets WHERE tenant_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (tid, limit, offset))

@app.post("/api/jobs", status_code=201)
def create_job(body: JobIn, tid: str = Depends(tenant), db=Depends(get_db)):
    jid = uid()
    ref, title = body.external_ref.strip(), body.title.strip()
    if not ref or not title:
        raise HTTPException(422, "Reference and title are required")
    if ref.lower().startswith("odoo:"):
        raise HTTPException(422, "The odoo: namespace is reserved for verified ERP imports")
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO jobs(id,tenant_id,external_ref,title,created_at) VALUES(?,?,?,?,?)",
                   (jid, tid, ref, title, stamp()))
        audit(db, tid, "job", jid, "planned", {"external_ref": ref})
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Work order reference already exists") from e
    return within_tenant(db, "jobs", tid, jid)

@app.get("/api/jobs")
def jobs(tid: str = Depends(tenant), db=Depends(get_db), limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
    return all_rows(db, "SELECT * FROM jobs WHERE tenant_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (tid, limit, offset))

@app.post("/api/jobs/{job_id}/complete")
def complete_job(job_id: str, tid: str = Depends(tenant), db=Depends(get_db)):
    with transaction(db):
        row = within_tenant(db, "jobs", tid, job_id)
        if row["state"] not in ("planned", "in_progress", "completed"):
            raise HTTPException(409, "Work order cannot be completed")
        if row["state"] != "completed":
            db.execute("UPDATE jobs SET state='completed',completed_at=? WHERE tenant_id=? AND id=?", (stamp(), tid, job_id))
            audit(db, tid, "job", job_id, "completed")
        return within_tenant(db, "jobs", tid, job_id)

@app.post("/api/custody/issue")
def issue(body: IssueIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
          tid: str = Depends(tenant), db=Depends(get_db)):
    due = normalized_time(body.due_at)
    data = body.model_dump(mode="json")
    def action():
        asset = within_tenant(db, "assets", tid, body.asset_id)
        if asset["status"] != "ready":
            raise HTTPException(409, "Asset is not ready to be issued")
        if body.job_id:
            job = within_tenant(db, "jobs", tid, body.job_id)
            if job["state"] == "completed":
                raise HTTPException(409, "Cannot issue to a completed work order")
        if not body.holder.strip():
            raise HTTPException(422, "Holder must not be blank")
        if due and due <= stamp():
            raise HTTPException(422, "Due date must be in the future")
        cid = uid()
        db.execute(
            "INSERT INTO custody(id,tenant_id,asset_id,job_id,holder,state,issued_at,due_at) "
            "VALUES(?,?,?,?,?,'active',?,?)",
            (cid, tid, body.asset_id, body.job_id, body.holder.strip(), stamp(), due)
        )
        audit(db, tid, "custody", cid, "issued", {"asset_id": body.asset_id, "holder": body.holder})
        return within_tenant(db, "custody", tid, cid)
    return perform(db, tid, "issue", idempotency_key, data, action)

@app.post("/api/custody/return")
def return_asset(body: ReturnIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                 tid: str = Depends(tenant), db=Depends(get_db)):
    data = body.model_dump(mode="json")
    def action():
        row = within_tenant(db, "custody", tid, body.custody_id)
        if row["state"] != "active":
            raise HTTPException(409, "Custody has already ended")
        # The authenticated credential is the only credible acting identity.
        # A client-supplied name is never accepted as proof of another person.
        operator = one(db, "SELECT name FROM credentials WHERE id=? AND tenant_id=?",
                       (db.actor_id, tid))
        if not operator:
            raise HTTPException(403, "An active named credential is required")
        if body.confirmed_by and body.confirmed_by.strip() != operator["name"]:
            raise HTTPException(422, "Return confirmation name must match the signed-in operator")
        db.execute("UPDATE custody SET state='returned',returned_at=? WHERE tenant_id=? AND id=?",
                   (stamp(), tid, body.custody_id))
        audit(db, tid, "custody", body.custody_id, "returned",
              {"confirmed_by": operator["name"], "credential_id": db.actor_id,
               "receiver_acceptance_verified": False})
        return within_tenant(db, "custody", tid, body.custody_id)
    return perform(db, tid, "return", idempotency_key, data, action)

@app.get("/api/custody")
def custody(tid: str = Depends(tenant), db=Depends(get_db), limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
    return all_rows(db, "SELECT * FROM custody WHERE tenant_id=? ORDER BY issued_at DESC,id DESC LIMIT ? OFFSET ?", (tid, limit, offset))

@app.post("/api/evidence", status_code=201)
def append_evidence(body: EvidenceIn, tid: str = Depends(tenant), db=Depends(get_db)):
    observed = normalized_time(body.observed_at)
    if body.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "Observation is too far in the future")
    try:
        encoded_payload = json.dumps(body.payload, allow_nan=False)
    except (ValueError, TypeError) as error:
        raise HTTPException(422, "Evidence payload must contain finite JSON values") from error
    if len(encoded_payload.encode()) > 65536:
        raise HTTPException(422, "Evidence payload exceeds 64 KiB")
    if db.actor_role == "connector" and body.source != db.actor_source:
        raise HTTPException(403, "Source does not match connector credential")
    if db.actor_role != "connector" and body.source not in {"manual", "qr"}:
        raise HTTPException(403, "Use a source-scoped connector credential for sensor/ERP evidence")
    with transaction(db):
        if body.asset_id:
            within_tenant(db, "assets", tid, body.asset_id)
        if body.job_id:
            within_tenant(db, "jobs", tid, body.job_id)
        current = one(db, "SELECT * FROM evidence WHERE tenant_id=? AND source=? AND source_event_id=?",
                      (tid, body.source, body.source_event_id))
        if current:
            if (current["asset_id"] != body.asset_id or current["job_id"] != body.job_id or
                current["event_type"] != body.event_type or current["observed_at"] != observed or
                json.loads(current["payload"]) != body.payload):
                raise HTTPException(409, "Conflicting event with the same source ID")
            return current
        eid = uid()
        db.execute("INSERT INTO evidence(id,tenant_id,asset_id,job_id,source,source_event_id,event_type,observed_at,payload,received_at) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (eid, tid, body.asset_id, body.job_id, body.source, body.source_event_id, body.event_type,
                    observed, json.dumps(body.payload, sort_keys=True, allow_nan=False), stamp()))
        audit(db, tid, "evidence", eid, "received", {"source": body.source, "event_type": body.event_type})
        return one(db, "SELECT * FROM evidence WHERE id=? AND tenant_id=?", (eid, tid))

@app.get("/api/evidence")
def evidence(tid: str = Depends(tenant), db=Depends(get_db), limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
    return all_rows(db, "SELECT * FROM evidence WHERE tenant_id=? ORDER BY received_at DESC,id DESC LIMIT ? OFFSET ?", (tid, limit, offset))


@app.get("/api/geo/positions")
def geo_positions(tid: str = Depends(tenant), db=Depends(get_db),
                  limit: int = Query(1000, ge=1, le=2000)):
    """Read-only, tenant-bound latest device positions from persisted observations.

    Locations are NOT a separate source of truth: each row comes from a
    previously received Traccar/GPS evidence event and retains its provenance.
    No provider credentials are accessible to the browser.
    """
    rows = all_rows(db,
        "SELECT e.asset_id,e.source,e.source_event_id,e.observed_at,e.received_at,"
        "e.payload,a.tag AS asset_tag,a.name AS asset_name "
        "FROM evidence e LEFT JOIN assets a "
        "ON a.id=e.asset_id AND a.tenant_id=e.tenant_id "
        "WHERE e.tenant_id=? AND e.source IN ('traccar','gps') "
        "AND e.event_type='gps_position_reported' "
        "ORDER BY e.observed_at DESC,e.id DESC LIMIT ?",
        (tid, limit))
    seen = set()
    results = []
    for row in rows:
        try:
            payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
            if not isinstance(payload, dict):
                continue
            lat, lon = float(payload['latitude']), float(payload['longitude'])
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                continue
            stamp_time = datetime.fromisoformat(str(row['observed_at']).replace('Z','+00:00'))
            if stamp_time.tzinfo is None:
                continue
            device = str(payload.get('device_id') or row['asset_id'] or row['source_event_id'])
            key = (row['source'], device)
            if key in seen:
                continue
            seen.add(key)
            age = (datetime.now(timezone.utc) - stamp_time.astimezone(timezone.utc)).total_seconds()
            valid = payload.get('valid') is True
            fresh = -300 <= age <= max(30, int(os.getenv('TRACCAR_MAX_POSITION_AGE_SECONDS', '300')))
            speed = payload.get('speed')
            accuracy = payload.get('accuracy')
            results.append({
                'asset_id': row['asset_id'], 'asset_tag': row['asset_tag'],
                'asset_name': row['asset_name'], 'device_id': device,
                'source': row['source'], 'source_event_id': row['source_event_id'],
                'observed_at': row['observed_at'], 'received_at': row['received_at'],
                'latitude': lat, 'longitude': lon,
                'valid': valid, 'fresh': fresh, 'quality': 'current' if valid and fresh else 'unverified',
                'speed': speed if isinstance(speed, (int, float)) and math.isfinite(speed) else None,
                'accuracy': accuracy if isinstance(accuracy, (int, float)) and math.isfinite(accuracy) else None,
            })
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return results

@app.get("/api/map/config")
def map_config(tid: str = Depends(tenant)):
    """OSM tiles are explicitly opt-in for production due to geodata privacy."""
    enabled = os.getenv('RALLY_PUBLIC_MAP_TILES',
                        'off' if os.getenv('RALLY_ENV') == 'production' else 'on').lower() == 'on'
    return {'public_tiles_enabled': enabled, 'tiles_provider': 'OpenStreetMap' if enabled else None}

@app.post("/api/reconcile")
def reconcile(tid: str = Depends(tenant), db=Depends(get_db)):
    with transaction(db):
        now = stamp()
        conditions = {}
        active = all_rows(db, "SELECT c.*,j.state AS job_state FROM custody c LEFT JOIN jobs j "
                               "ON c.job_id=j.id AND c.tenant_id=j.tenant_id "
                               "WHERE c.tenant_id=? AND c.state='active'", (tid,))
        for item in active:
            if item["due_at"] and item["due_at"] < now:
                conditions["overdue:" + item["id"]] = (
                    "overdue_custody", "warning", "Asset return time is overdue")
            if item["job_state"] == "completed":
                conditions["completed_job:" + item["id"]] = (
                    "closed_job_active_custody", "critical",
                    "Work order is completed but assigned equipment has not been returned")
        # Enterprise cases require explicit tenant-admin rules and fresh source state.
        conditions.update(policy_conditions(db, tid, datetime.now(timezone.utc)))
        existing = {c["fingerprint"]: c for c in
                    all_rows(db, "SELECT * FROM cases WHERE tenant_id=?", (tid,))}
        for fp, (kind, severity, description) in conditions.items():
            if fp in existing:
                db.execute(
                    "UPDATE cases SET state=CASE WHEN state='resolved' THEN 'open' ELSE state END,last_seen=?,resolved_at=NULL WHERE tenant_id=? AND fingerprint=?",
                    (now, tid, fp))
            else:
                cid = uid()
                db.execute("INSERT INTO cases(id,tenant_id,fingerprint,kind,severity,state,description,first_seen,last_seen) "
                           "VALUES(?,?,?,?,?,'open',?,?,?)",
                           (cid, tid, fp, kind, severity, description, now, now))
                audit(db, tid, "case", cid, "opened", {"kind": kind, "fingerprint": fp})
        for fp, case in existing.items():
            if case["state"] in {"open", "acknowledged"} and fp not in conditions and case["kind"] in {"overdue_custody", "closed_job_active_custody"}:
                db.execute("UPDATE cases SET state='resolved',resolved_at=? WHERE tenant_id=? AND fingerprint=?",
                           (now, tid, fp))
                audit(db, tid, "case", case["id"], "resolved", {"reason": "Custody returned; authoritative condition cleared", "fingerprint": fp})
            elif (case["state"] in {"open", "acknowledged"} and fp not in conditions
                  and case["kind"] == "erp_state_overdue"
                  and may_resolve_erp_case(db, tid, fp, datetime.now(timezone.utc))):
                db.execute("UPDATE cases SET state='resolved',resolved_at=? "
                           "WHERE tenant_id=? AND fingerprint=?", (now, tid, fp))
                audit(db, tid, "case", case["id"], "resolved",
                      {"reason": "Approved ERP state rule no longer applies to the fresh source record "
                       "or was explicitly disabled", "fingerprint": fp})
        return {"active_custody_scanned": len(active), "open_conditions": len(conditions)}

@app.get("/api/cases")
def cases(tid: str = Depends(tenant), db=Depends(get_db), limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
    return all_rows(db, "SELECT * FROM cases WHERE tenant_id=? ORDER BY last_seen DESC,id DESC LIMIT ? OFFSET ?", (tid, limit, offset))

@app.get("/api/audit")
def audits(tid: str = Depends(tenant), db=Depends(get_db), limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
    return all_rows(db, "SELECT * FROM audit WHERE tenant_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (tid, limit, offset))

@app.get("/api/overview")
def overview(tid: str = Depends(tenant), db=Depends(get_db)):
    def count(sql):
        return next(iter(dict(db.execute(sql, (tid,)).fetchone()).values()))
    return {
        "assets": count("SELECT count(*) FROM assets WHERE tenant_id=?"),
        "jobs": count("SELECT count(*) FROM jobs WHERE tenant_id=?"),
        "active_custody": count("SELECT count(*) FROM custody WHERE tenant_id=? AND state='active'"),
        "open_cases": count("SELECT count(*) FROM cases WHERE tenant_id=? AND state IN ('open','acknowledged')"),
        "evidence_events": count("SELECT count(*) FROM evidence WHERE tenant_id=?"),
    }


class CredentialIn(Input):
    name: str = Field(min_length=2, max_length=120)
    role: Literal['admin', 'operator', 'reviewer', 'viewer', 'connector']
    source: Literal['odoo', 'odoo_enterprise', 'traccar', 'gps', 'rfid'] | None = None
    scope: str | None = Field(default=None, max_length=128)
    expires_at: datetime | None = None


class CaseAction(Input):
    owner_id: str | None = None
    note: str = Field(min_length=3, max_length=4000)


class Heartbeat(Input):
    status: Literal['ok', 'error']
    detail: str = Field(default='', max_length=500)


@app.get('/readyz')
def ready(db=Depends(get_db)):
    db.execute('SELECT 1')
    last = one(db, "SELECT last_success FROM worker_status WHERE name='reconciliation'")
    healthy = bool(last and datetime.fromisoformat(last['last_success']) > datetime.now(timezone.utc) - timedelta(seconds=int(os.getenv('RALLY_WORKER_STALE_SECONDS', '180'))))
    return JSONResponse({'database': 'ok', 'reconciliation': 'ok' if healthy else 'stale'}, status_code=200 if healthy else 503)


@app.get('/api/me')
def me(tid=Depends(tenant), db=Depends(get_db)):
    identity = one(db, 'SELECT id,name,role,source,expires_at FROM credentials WHERE id=? AND tenant_id=?', (db.actor_id, tid))
    return {'tenant_id': tid, **identity}


@app.get('/api/credentials')
def credentials(tid=Depends(tenant_admin), db=Depends(get_db)):
    return all_rows(db, 'SELECT id,name,role,source,scope,created_at,expires_at,revoked_at FROM credentials WHERE tenant_id=? ORDER BY created_at,id', (tid,))


@app.post('/api/credentials', status_code=201)
def create_credential(body: CredentialIn, tid=Depends(tenant_admin), db=Depends(get_db)):
    if (body.role == 'connector') != bool(body.source):
        raise HTTPException(422, 'Only connector credentials require a source')
    if body.role == 'connector' and body.source in {'odoo', 'odoo_enterprise'}:
        if not body.scope or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", body.scope):
            raise HTTPException(422, 'Odoo credentials require an explicit instance scope')
    elif body.scope:
        raise HTTPException(422, 'An instance scope is only supported for Odoo credentials')
    expires = normalized_time(body.expires_at)
    if expires and expires <= stamp():
        raise HTTPException(422, 'Expiry must be in the future')
    raw, cid = token_urlsafe(48), uid()
    with transaction(db):
        db.execute('INSERT INTO credentials(id,tenant_id,name,role,source,scope,token_hash,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)',
                   (cid, tid, body.name, body.role, body.source, body.scope, sha256(raw.encode()).hexdigest(), stamp(), expires))
        audit(db, tid, 'credential', cid, 'created',
              {'name': body.name, 'role': body.role, 'source': body.source, 'scope': body.scope})
    return {'id': cid, 'api_token': raw, 'role': body.role, 'name': body.name, 'expires_at': expires}


@app.post('/api/credentials/{credential_id}/revoke')
def revoke_credential(credential_id: str, tid=Depends(tenant_admin), db=Depends(get_db)):
    with transaction(db):
        row = one(db, 'SELECT * FROM credentials WHERE id=? AND tenant_id=?', (credential_id, tid))
        if not row:
            raise HTTPException(404, 'Credential not found')
        if row['role'] == 'admin' and not row['revoked_at']:
            admins = all_rows(db, "SELECT id FROM credentials WHERE tenant_id=? AND role='admin' AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?) AND id<>?", (tid, stamp(), credential_id))
            if not admins:
                raise HTTPException(409, 'Create another active administrator before revoking the last one')
        if not row['revoked_at']:
            db.execute('UPDATE credentials SET revoked_at=? WHERE id=? AND tenant_id=?', (stamp(), credential_id, tid))
            audit(db, tid, 'credential', credential_id, 'revoked')
    return {'revoked': True}


@app.post('/api/jobs/import')
def import_job(body: JobIn, tid=Depends(tenant), db=Depends(get_db)):
    if db.actor_role != 'admin' and not (db.actor_role == 'connector' and db.actor_source == 'odoo'):
        raise HTTPException(403, 'Odoo connector or tenant administrator required')
    # A connector must not overwrite a manually entered work order by choosing
    # its external reference. Reserve a structured, traceable Odoo namespace.
    reference = body.external_ref.strip()
    if not re.fullmatch(r"odoo:[A-Za-z0-9_.-]{1,128}:sale[.]order:[1-9][0-9]{0,18}", reference):
        raise HTTPException(422, "Expected odoo:INSTANCE:sale.order:POSITIVE_ID reference")
    if db.actor_role == 'connector' and db.actor_scope != reference.split(':', 2)[1]:
        raise HTTPException(403, 'Odoo connector credential is not authorized for this ERP instance')
    with transaction(db):
        old = one(db, 'SELECT * FROM jobs WHERE tenant_id=? AND external_ref=?', (tid, reference))
        if old:
            if old['source'] != 'odoo':
                # Existing MK0 rows must be explicitly checked and assigned
                # provenance before a connector can take control of them.
                raise HTTPException(409, 'Reference belongs to a manual or legacy work order; review provenance')
            if old['title'] != body.title:
                db.execute('UPDATE jobs SET title=? WHERE id=? AND tenant_id=?', (body.title, old['id'], tid))
                audit(db, tid, 'job', old['id'], 'import_updated')
            return within_tenant(db, 'jobs', tid, old['id'])
        jid = uid()
        db.execute("INSERT INTO jobs(id,tenant_id,external_ref,title,created_at,source) VALUES(?,?,?,?,?,'odoo')",
                   (jid, tid, reference, body.title, stamp()))
        audit(db, tid, 'job', jid, 'imported', {'external_ref': reference, 'source': 'odoo'})
        return within_tenant(db, 'jobs', tid, jid)


class ERPGrantIn(Input):
    credential_id: str = Field(min_length=1, max_length=80)
    company_id: int = Field(ge=1, strict=True)
    models: list[str] = Field(min_length=1, max_length=30)


class ERPRecordIn(Input):
    instance: str = Field(min_length=1, max_length=128)
    company_id: int = Field(ge=1, strict=True)
    model: str = Field(min_length=2, max_length=80)
    record_id: int = Field(ge=1, strict=True)
    state: str = Field(min_length=1, max_length=80)
    source_modified_at: datetime


@app.get("/api/erp/catalog")
def erp_catalog(tid=Depends(tenant_admin)):
    """Static supported model metadata; NOT assertions of live Odoo modules."""
    return [{"model": k, "domain": v[0], "fields": list(v[1]),
             "status": "adapter_supported_not_connected"} for k,v in MODEL_CONTRACTS.items()]


@app.get("/api/erp/grants")
def erp_grants(tid=Depends(tenant_admin), db=Depends(get_db)):
    return all_rows(db, "SELECT g.credential_id,c.name AS connector,g.company_id,g.model,g.created_at "
                    "FROM erp_grants g JOIN credentials c ON c.id=g.credential_id AND c.tenant_id=g.tenant_id "
                    "WHERE g.tenant_id=? ORDER BY c.name,g.company_id,g.model", (tid,))


@app.post("/api/erp/grants", status_code=201)
def erp_add_grants(body: ERPGrantIn, tid=Depends(tenant_admin), db=Depends(get_db)):
    """Administrator authorizes one company's model allowlist for one connector."""
    models = set(body.models)
    if len(models) != len(body.models) or models - MODEL_NAMES:
        raise HTTPException(422, "Unsupported or duplicate ERP models")
    with transaction(db):
        cred = one(db, "SELECT id,role,source,scope,revoked_at,expires_at FROM credentials "
                       "WHERE tenant_id=? AND id=?", (tid, body.credential_id))
        if (not cred or cred["role"] != "connector" or cred["source"] != "odoo_enterprise"
            or not cred["scope"] or cred["revoked_at"]
            or (cred["expires_at"] and cred["expires_at"] <= stamp())):
            raise HTTPException(422, "Active instance-scoped Odoo connector credential required")
        for model in sorted(models):
            db.execute("INSERT INTO erp_grants(tenant_id,credential_id,company_id,model,created_at) "
                       "VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                       (tid, body.credential_id, body.company_id, model, stamp()))
        audit(db, tid, "erp_grant", body.credential_id, "authorized",
              {"company_id": body.company_id, "models": sorted(models), "instance": cred["scope"]})
    return {"authorized": sorted(models), "company_id": body.company_id,
            "connector_id": body.credential_id}


@app.delete("/api/erp/grants/{credential_id}/{company_id}/{model}")
def erp_revoke_grant(credential_id: str, company_id: int, model: str,
                     tid=Depends(tenant_admin), db=Depends(get_db)):
    if company_id <= 0 or model not in MODEL_NAMES:
        raise HTTPException(422, "Invalid company or ERP model")
    with transaction(db):
        result = db.execute("DELETE FROM erp_grants WHERE tenant_id=? AND credential_id=? "
                            "AND company_id=? AND model=?", (tid, credential_id, company_id, model))
        if not result.rowcount:
            raise HTTPException(404, "ERP grant not found")
        audit(db, tid, "erp_grant", credential_id, "revoked",
              {"company_id": company_id, "model": model})
    return {"revoked": True}


@app.post("/api/erp/records/import", status_code=201)
def erp_import_state(body: ERPRecordIn, tid=Depends(tenant), db=Depends(get_db)):
    """Read-only provider mirror, source-only auth and append-on-change history.

    This is not a write to Odoo and does not imply fiscal or physical completion.
    """
    if db.actor_role != "connector" or db.actor_source != "odoo_enterprise":
        raise HTTPException(403, "Odoo connector credential required")
    if (body.instance != db.actor_scope or not NAMESPACE.fullmatch(body.instance)):
        raise HTTPException(403, "Odoo source instance scope mismatch")
    if body.model not in MODEL_NAMES or not STATE.fullmatch(body.state):
        raise HTTPException(422, "Unsupported Odoo model or state")
    modified = normalized_time(body.source_modified_at)
    if datetime.fromisoformat(modified) > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "Source modification time is in the future")
    with transaction(db):
        grant = one(db, "SELECT model FROM erp_grants WHERE tenant_id=? AND credential_id=? "
                        "AND company_id=? AND model=?",
                    (tid, db.actor_id, body.company_id, body.model))
        if not grant:
            raise HTTPException(403, "Model/company not granted for this connector")
        old = one(db, "SELECT * FROM erp_records WHERE tenant_id=? AND instance=? "
                      "AND company_id=? AND model=? AND record_id=?",
                  (tid, body.instance, body.company_id, body.model, body.record_id))
        now = stamp()
        if old and old["source_modified_at"] > modified:
            return {"id": old["id"], "model": body.model, "action": "older_ignored"}
        if old and old["source_modified_at"] == modified and old["state"] != body.state:
            raise HTTPException(409, "Conflicting state for the same Odoo modification timestamp")
        action = "unchanged"
        if not old:
            rid = uid()
            db.execute("INSERT INTO erp_records(id,tenant_id,instance,company_id,model,record_id,"
                       "state,source_modified_at,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (rid, tid, body.instance, body.company_id, body.model, body.record_id,
                        body.state, modified, now, now))
            action = "created"
        else:
            rid = old["id"]
            if old["state"] != body.state:
                action = "changed"
            db.execute("UPDATE erp_records SET state=?,source_modified_at=?,last_seen=? "
                       "WHERE id=? AND tenant_id=?", (body.state, modified, now, rid, tid))
        if action != "unchanged":
            db.execute("INSERT INTO erp_state_changes(id,tenant_id,erp_record_id,previous_state,"
                       "current_state,source_modified_at,received_at) VALUES(?,?,?,?,?,?,?)",
                       (uid(), tid, rid, old["state"] if old else None, body.state, modified, now))
            audit(db, tid, "erp_record", rid, action,
                  {"model": body.model, "instance": body.instance,
                   "company_id": body.company_id, "record_id": body.record_id})
        return {"id": rid, "model": body.model, "action": action}


@app.get("/api/erp/summary")
def erp_summary(tid=Depends(tenant_admin), db=Depends(get_db)):
    return all_rows(db,
        "SELECT instance,company_id,model,state,count(*) AS records,max(last_seen) AS last_seen "
        "FROM erp_records WHERE tenant_id=? "
        "GROUP BY instance,company_id,model,state ORDER BY instance,company_id,model,state", (tid,))


@app.get("/api/erp/records")
def erp_records(tid=Depends(tenant_admin), db=Depends(get_db),
                model: str | None = Query(default=None), company_id: int | None = Query(default=None, ge=1),
                limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    if model is not None and model not in MODEL_NAMES:
        raise HTTPException(422, "Unsupported ERP model")
    conditions, values = ["tenant_id=?"], [tid]
    if model:
        conditions.append("model=?"); values.append(model)
    if company_id is not None:
        conditions.append("company_id=?"); values.append(company_id)
    return all_rows(db, "SELECT id,instance,company_id,model,record_id,state,source_modified_at,"
                    "first_seen,last_seen FROM erp_records WHERE " + " AND ".join(conditions) +
                    " ORDER BY last_seen DESC,id DESC LIMIT ? OFFSET ?", (*values, limit, offset))


@app.get("/api/erp/records/{record_uuid}/history")
def erp_history(record_uuid: str, tid=Depends(tenant_admin), db=Depends(get_db),
                limit: int = Query(default=100,ge=1,le=500)):
    existing = one(db, "SELECT id FROM erp_records WHERE tenant_id=? AND id=?", (tid, record_uuid))
    if not existing:
        raise HTTPException(404, "ERP record not found in this tenant")
    return all_rows(db, "SELECT previous_state,current_state,source_modified_at,received_at "
                    "FROM erp_state_changes WHERE tenant_id=? AND erp_record_id=? "
                    "ORDER BY received_at DESC,id DESC LIMIT ?", (tid, record_uuid, limit))


class ERPPolicyIn(Input):
    instance: str = Field(min_length=1, max_length=128)
    company_id: int = Field(ge=1, strict=True)
    model: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=1, max_length=80)
    max_age_seconds: int = Field(ge=60, le=31536000, strict=True)
    severity: Literal["warning", "critical"] = "warning"


@app.get("/api/erp/policies")
def erp_list_policies(tid=Depends(tenant_admin), db=Depends(get_db)):
    return all_rows(db, "SELECT * FROM erp_policies WHERE tenant_id=? "
                    "ORDER BY created_at DESC,id DESC", (tid,))


@app.post("/api/erp/policies", status_code=201)
def erp_add_policy(body: ERPPolicyIn, tid=Depends(tenant_admin), db=Depends(get_db)):
    if (not NAMESPACE.fullmatch(body.instance) or body.model not in MODEL_NAMES
        or not STATE.fullmatch(body.state)):
        raise HTTPException(422, "Unsupported ERP policy namespace, model or state")
    with transaction(db):
        credential_has_grant = one(db,
            "SELECT g.credential_id FROM erp_grants g JOIN credentials c "
            "ON c.tenant_id=g.tenant_id AND c.id=g.credential_id "
            "WHERE g.tenant_id=? AND c.scope=? AND g.company_id=? AND g.model=? "
            "AND c.role='connector' AND c.source='odoo_enterprise' AND c.revoked_at IS NULL "
            "AND (c.expires_at IS NULL OR c.expires_at>?)",
            (tid, body.instance, body.company_id, body.model, stamp()))
        if not credential_has_grant:
            raise HTTPException(422, "Approve an active Odoo connector grant before defining ERP rules")
        current = one(db, "SELECT id FROM erp_policies WHERE tenant_id=? AND instance=? "
                         "AND company_id=? AND model=? AND state=?",
                      (tid, body.instance, body.company_id, body.model, body.state))
        if current:
            db.execute("UPDATE erp_policies SET max_age_seconds=?,severity=?,enabled=1 "
                       "WHERE id=? AND tenant_id=?",
                       (body.max_age_seconds,body.severity,current["id"],tid))
            pid = current["id"]
        else:
            pid = uid()
            db.execute("INSERT INTO erp_policies(id,tenant_id,instance,company_id,model,state,"
                       "max_age_seconds,severity,enabled,created_at) VALUES(?,?,?,?,?,?,?,?,1,?)",
                       (pid,tid,body.instance,body.company_id,body.model,body.state,
                        body.max_age_seconds,body.severity,stamp()))
        audit(db, tid, "erp_policy", pid, "configured",
              {"instance":body.instance,"company_id":body.company_id,"model":body.model,
               "state":body.state,"max_age_seconds":body.max_age_seconds,"severity":body.severity})
    return {"id":pid,"enabled":True}


@app.post("/api/erp/policies/{policy_id}/disable")
def erp_disable_policy(policy_id: str, tid=Depends(tenant_admin), db=Depends(get_db)):
    with transaction(db):
        policy = one(db,"SELECT id,enabled FROM erp_policies WHERE tenant_id=? AND id=?",
                     (tid,policy_id))
        if not policy:
            raise HTTPException(404,"ERP policy not found for tenant")
        if policy["enabled"]:
            db.execute("UPDATE erp_policies SET enabled=0 WHERE id=? AND tenant_id=?",
                       (policy_id,tid))
            audit(db,tid,"erp_policy",policy_id,"disabled")
    return {"disabled":True}


@app.get('/api/cases/{case_id}')
def case_detail(case_id: str, tid=Depends(tenant), db=Depends(get_db)):
    row = one(db, 'SELECT * FROM cases WHERE id=? AND tenant_id=?', (case_id, tid))
    if not row:
        raise HTTPException(404, 'Case not found')
    row['notes'] = all_rows(db, 'SELECT * FROM case_notes WHERE case_id=? AND tenant_id=? ORDER BY created_at,id', (case_id, tid))
    return row


@app.post('/api/cases/{case_id}/acknowledge')
def acknowledge_case(case_id: str, body: CaseAction, tid=Depends(tenant), db=Depends(get_db)):
    with transaction(db):
        row = case_detail(case_id, tid, db)
        if row['state'] == 'resolved':
            raise HTTPException(409, 'Resolved cases cannot be acknowledged')
        owner = body.owner_id or db.actor_id
        if not one(db, "SELECT id FROM credentials WHERE id=? AND tenant_id=? AND role IN ('admin','operator','reviewer') AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?)", (owner, tid, stamp())):
            raise HTTPException(422, 'Owner must be an active operational identity in this tenant')
        db.execute("UPDATE cases SET state='acknowledged',owner_id=?,acknowledged_at=? WHERE id=? AND tenant_id=?", (owner, stamp(), case_id, tid))
        db.execute('INSERT INTO case_notes(id,tenant_id,case_id,actor_id,note,created_at) VALUES(?,?,?,?,?,?)', (uid(), tid, case_id, db.actor_id, body.note, stamp()))
        audit(db, tid, 'case', case_id, 'acknowledged', {'owner_id': owner})
        return case_detail(case_id, tid, db)


@app.post('/api/cases/{case_id}/notes', status_code=201)
def add_case_note(case_id: str, body: CaseAction, tid=Depends(tenant), db=Depends(get_db)):
    with transaction(db):
        case_detail(case_id, tid, db)
        note_id = uid()
        db.execute('INSERT INTO case_notes(id,tenant_id,case_id,actor_id,note,created_at) VALUES(?,?,?,?,?,?)', (note_id, tid, case_id, db.actor_id, body.note, stamp()))
        audit(db, tid, 'case', case_id, 'note_added', {'note_id': note_id})
    return {'id': note_id}


@app.post('/api/connectors/heartbeat')
def heartbeat(body: Heartbeat, tid=Depends(tenant), db=Depends(get_db)):
    if db.actor_role != 'connector':
        raise HTTPException(403, 'Connector credential required')
    with transaction(db):
        now = stamp()
        db.execute('INSERT INTO connector_status(tenant_id,name,last_attempt,last_success,status,detail) VALUES(?,?,?,?,?,?) '
                   'ON CONFLICT(tenant_id,name) DO UPDATE SET last_attempt=excluded.last_attempt, '
                   'last_success=COALESCE(excluded.last_success,connector_status.last_success),status=excluded.status,detail=excluded.detail',
                   (tid, db.actor_id, now, now if body.status == 'ok' else None, body.status, body.detail))
    return {'recorded': True}


@app.get('/api/connectors')
def connectors(tid=Depends(tenant), db=Depends(get_db)):
    rows = all_rows(db, "SELECT c.id,c.name,c.source,s.last_attempt,s.last_success,s.status,s.detail FROM credentials c "
                       "LEFT JOIN connector_status s ON s.name=c.id AND s.tenant_id=c.tenant_id "
                       "WHERE c.tenant_id=? AND c.role='connector' AND c.revoked_at IS NULL AND (c.expires_at IS NULL OR c.expires_at>?)", (tid, stamp()))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=int(os.getenv('RALLY_CONNECTOR_STALE_SECONDS', '300')))
    for row in rows:
        row['coverage'] = 'unknown' if not row['last_success'] else ('stale' if datetime.fromisoformat(row['last_success']) < cutoff else ('degraded' if row['status'] != 'ok' else 'current'))
    return rows


@app.exception_handler(OperationalError[0])
async def sqlite_unavailable(request, error):
    return JSONResponse({'detail': 'Database unavailable; retry with the same idempotency key'}, 503, headers={'Retry-After': '5'})


if len(OperationalError) > 1:
    app.add_exception_handler(OperationalError[1], sqlite_unavailable)

app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'web'), name='static')
app.add_middleware(GuardMiddleware)
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[x.strip() for x in os.getenv('RALLY_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')])
