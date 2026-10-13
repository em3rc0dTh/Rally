"""Rally MK0 API. Each credential resolves to one tenant; never trust a tenant ID from clients.

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
import sqlite3

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from rally.storage import all_rows, get_db, initialize, one

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

class TenantIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)

class AssetIn(BaseModel):
    tag: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=250)

class JobIn(BaseModel):
    external_ref: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=250)

class IssueIn(BaseModel):
    asset_id: str
    job_id: str | None = None
    holder: str = Field(min_length=1, max_length=250)
    due_at: datetime | None = None

class ReturnIn(BaseModel):
    custody_id: str
    confirmed_by: str = Field(min_length=1, max_length=250)

class EvidenceIn(BaseModel):
    asset_id: str | None = None
    job_id: str | None = None
    source: Literal["manual", "qr", "rfid", "gps", "traccar", "odoo"]
    source_event_id: str = Field(min_length=1, max_length=150)
    event_type: str = Field(min_length=1, max_length=80)
    observed_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield

app = FastAPI(
    title="Rally Business Execution Assurance", version="0.1.0", lifespan=lifespan,
    description="Tenant-scoped asset custody, work orders, evidence and exception reconciliation."
)

def require_admin(x_admin_key: str | None = Header(default=None)):
    expected = os.getenv("RALLY_ADMIN_KEY", "")
    if len(expected) < 32 or not x_admin_key or not compare_digest(expected, x_admin_key):
        raise HTTPException(403, "Valid admin credential required")
    return True

def tenant(authorization: str | None = Header(default=None), db=Depends(get_db)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    raw = authorization.removeprefix("Bearer ").strip()
    if len(raw) < 32:
        raise HTTPException(401, "Invalid bearer token")
    row = one(db, "SELECT id FROM tenants WHERE token_hash=?", (sha256(raw.encode()).hexdigest(),))
    if not row:
        raise HTTPException(401, "Invalid bearer token")
    return row["id"]

def audit(db, tid, entity, eid, action, details=None):
    db.execute(
        "INSERT INTO audit (id,tenant_id,entity,entity_id,action,details,created_at) VALUES (?,?,?,?,?,?,?)",
        (uid(), tid, entity, eid, action, json.dumps(details or {}, sort_keys=True), stamp())
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
    except sqlite3.IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Uniqueness or referential-integrity conflict") from error
    except Exception:
        db.rollback()
        raise

@app.get("/")
def home():
    return FileResponse(Path(__file__).resolve().parents[1] / "web" / "index.html")

@app.get("/healthz")
def health():
    return {"status": "ok", "product": "Rally", "version": "0.1.0"}

@app.post("/api/tenants", dependencies=[Depends(require_admin)], status_code=201)
def create_tenant(payload: TenantIn, db=Depends(get_db)):
    token = token_urlsafe(48)
    tid = uid()
    db.execute(
        "INSERT INTO tenants(id,name,token_hash,created_at) VALUES(?,?,?,?)",
        (tid, payload.name.strip(), sha256(token.encode()).hexdigest(), stamp())
    )
    db.commit()
    # Token is revealed only at creation; store it securely. No token-recovery endpoint exists.
    return {"tenant_id": tid, "name": payload.name.strip(), "api_token": token}

@app.post("/api/assets", status_code=201)
def create_asset(body: AssetIn, tid: str = Depends(tenant), db=Depends(get_db)):
    tag, name, aid = body.tag.strip().upper(), body.name.strip(), uid()
    if not tag or not name:
        raise HTTPException(422, "Tag and name are required")
    try:
        db.execute("INSERT INTO assets(id,tenant_id,tag,name,created_at) VALUES(?,?,?,?,?)",
                   (aid, tid, tag, name, stamp()))
        audit(db, tid, "asset", aid, "registered", {"tag": tag})
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Asset tag already exists") from e
    return within_tenant(db, "assets", tid, aid)

@app.get("/api/assets")
def assets(tid: str = Depends(tenant), db=Depends(get_db)):
    return all_rows(db, "SELECT * FROM assets WHERE tenant_id=? ORDER BY created_at DESC", (tid,))

@app.post("/api/jobs", status_code=201)
def create_job(body: JobIn, tid: str = Depends(tenant), db=Depends(get_db)):
    jid = uid()
    ref, title = body.external_ref.strip(), body.title.strip()
    if not ref or not title:
        raise HTTPException(422, "Reference and title are required")
    try:
        db.execute("INSERT INTO jobs(id,tenant_id,external_ref,title,created_at) VALUES(?,?,?,?,?)",
                   (jid, tid, ref, title, stamp()))
        audit(db, tid, "job", jid, "planned", {"external_ref": ref})
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Work order reference already exists") from e
    return within_tenant(db, "jobs", tid, jid)

@app.get("/api/jobs")
def jobs(tid: str = Depends(tenant), db=Depends(get_db)):
    return all_rows(db, "SELECT * FROM jobs WHERE tenant_id=? ORDER BY created_at DESC", (tid,))

@app.post("/api/jobs/{job_id}/complete")
def complete_job(job_id: str, tid: str = Depends(tenant), db=Depends(get_db)):
    row = within_tenant(db, "jobs", tid, job_id)
    if row["state"] not in ("planned", "in_progress", "completed"):
        raise HTTPException(409, "Work order cannot be completed")
    if row["state"] != "completed":
        db.execute("UPDATE jobs SET state='completed',completed_at=? WHERE tenant_id=? AND id=?",
                   (stamp(), tid, job_id))
        audit(db, tid, "job", job_id, "completed")
        db.commit()
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
        if not body.confirmed_by.strip():
            raise HTTPException(422, "Confirmation actor is required")
        db.execute("UPDATE custody SET state='returned',returned_at=? WHERE tenant_id=? AND id=?",
                   (stamp(), tid, body.custody_id))
        audit(db, tid, "custody", body.custody_id, "returned",
              {"confirmed_by": body.confirmed_by.strip()})
        return within_tenant(db, "custody", tid, body.custody_id)
    return perform(db, tid, "return", idempotency_key, data, action)

@app.get("/api/custody")
def custody(tid: str = Depends(tenant), db=Depends(get_db)):
    return all_rows(db, "SELECT * FROM custody WHERE tenant_id=? ORDER BY issued_at DESC", (tid,))

@app.post("/api/evidence", status_code=201)
def append_evidence(body: EvidenceIn, tid: str = Depends(tenant), db=Depends(get_db)):
    observed = normalized_time(body.observed_at)
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
    try:
        db.execute(
            "INSERT INTO evidence(id,tenant_id,asset_id,job_id,source,source_event_id,event_type,observed_at,payload,received_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eid, tid, body.asset_id, body.job_id, body.source, body.source_event_id,
             body.event_type, observed, json.dumps(body.payload, sort_keys=True), stamp())
        )
        audit(db, tid, "evidence", eid, "received", {"source": body.source, "event_type": body.event_type})
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Duplicate source event") from e
    return one(db, "SELECT * FROM evidence WHERE id=? AND tenant_id=?", (eid, tid))

@app.get("/api/evidence")
def evidence(tid: str = Depends(tenant), db=Depends(get_db)):
    return all_rows(db, "SELECT * FROM evidence WHERE tenant_id=? ORDER BY received_at DESC LIMIT 200", (tid,))

@app.post("/api/reconcile")
def reconcile(tid: str = Depends(tenant), db=Depends(get_db)):
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
    try:
        db.execute("BEGIN IMMEDIATE")
        existing = {c["fingerprint"]: c for c in
                    all_rows(db, "SELECT * FROM cases WHERE tenant_id=?", (tid,))}
        for fp, (kind, severity, description) in conditions.items():
            if fp in existing:
                db.execute(
                    "UPDATE cases SET state='open',last_seen=?,resolved_at=NULL WHERE tenant_id=? AND fingerprint=?",
                    (now, tid, fp))
            else:
                cid = uid()
                db.execute("INSERT INTO cases(id,tenant_id,fingerprint,kind,severity,state,description,first_seen,last_seen) "
                           "VALUES(?,?,?,?,?,'open',?,?,?)",
                           (cid, tid, fp, kind, severity, description, now, now))
                audit(db, tid, "case", cid, "opened", {"kind": kind, "fingerprint": fp})
        for fp, case in existing.items():
            if case["state"] == "open" and fp not in conditions:
                db.execute("UPDATE cases SET state='resolved',resolved_at=? WHERE tenant_id=? AND fingerprint=?",
                           (now, tid, fp))
                audit(db, tid, "case", case["id"], "resolved")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"active_custody_scanned": len(active), "open_conditions": len(conditions)}

@app.get("/api/cases")
def cases(tid: str = Depends(tenant), db=Depends(get_db)):
    return all_rows(db, "SELECT * FROM cases WHERE tenant_id=? ORDER BY last_seen DESC", (tid,))

@app.get("/api/audit")
def audits(tid: str = Depends(tenant), db=Depends(get_db)):
    return all_rows(db, "SELECT * FROM audit WHERE tenant_id=? ORDER BY created_at DESC LIMIT 200", (tid,))

@app.get("/api/overview")
def overview(tid: str = Depends(tenant), db=Depends(get_db)):
    def count(sql):
        return db.execute(sql, (tid,)).fetchone()[0]
    return {
        "assets": count("SELECT count(*) FROM assets WHERE tenant_id=?"),
        "jobs": count("SELECT count(*) FROM jobs WHERE tenant_id=?"),
        "active_custody": count("SELECT count(*) FROM custody WHERE tenant_id=? AND state='active'"),
        "open_cases": count("SELECT count(*) FROM cases WHERE tenant_id=? AND state='open'"),
        "evidence_events": count("SELECT count(*) FROM evidence WHERE tenant_id=?"),
    }
