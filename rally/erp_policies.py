"""Opt-in ERP source-state SLA conditions for Rally case reconciliation.

Policies compare a source state with a customer-authorized maximum age.
They do NOT establish bank settlement, payroll correctness, work completion,
physical asset presence, employee attendance misconduct or fiscal compliance.
"""
from datetime import datetime, timezone, timedelta
import os


def _fresh(row, now):
    cutoff = now - timedelta(seconds=int(os.getenv("RALLY_CONNECTOR_STALE_SECONDS", "300")))
    return datetime.fromisoformat(row["last_seen"]) >= cutoff


def policy_conditions(db, tenant_id, now):
    """(fingerprint -> kind, severity, description) from fresh authorized source states."""
    records = db.execute(
        "SELECT r.id,r.instance,r.company_id,r.model,r.record_id,r.state,"
        "r.source_modified_at,r.last_seen,p.id AS policy_id,p.state AS policy_state,"
        "p.max_age_seconds,p.severity "
        "FROM erp_records r JOIN erp_policies p ON "
        "p.tenant_id=r.tenant_id AND p.instance=r.instance "
        "AND p.company_id=r.company_id AND p.model=r.model AND p.state=r.state "
        "WHERE r.tenant_id=? AND p.enabled=1", (tenant_id,)).fetchall()
    result = {}
    for item in records:
        rec = dict(item)
        if not _fresh(rec, now):
            continue  # unknown source coverage, never a new asserted violation
        changed = datetime.fromisoformat(rec["source_modified_at"])
        if changed > now - timedelta(seconds=rec["max_age_seconds"]):
            continue
        fp = "erp_policy:" + rec["policy_id"] + ":" + rec["id"]
        description = ("ERP source state exceeded an explicitly approved age limit: "
                       + rec["model"] + " #" + str(rec["record_id"]) +
                       ", instance " + rec["instance"] + ", company " + str(rec["company_id"]) +
                       ", state " + rec["state"] + ". Check authoritative business context.")
        result[fp] = ("erp_state_overdue", rec["severity"], description)
    return result


def may_resolve_erp_case(db, tenant_id, fingerprint, now):
    """Resolve only after a fresh source state disproves the rule or admin disables it."""
    parts = fingerprint.split(":")
    if len(parts) != 3 or parts[0] != "erp_policy":
        return False
    policy = db.execute("SELECT * FROM erp_policies WHERE tenant_id=? AND id=?",
                        (tenant_id, parts[1])).fetchone()
    record = db.execute("SELECT * FROM erp_records WHERE tenant_id=? AND id=?",
                        (tenant_id, parts[2])).fetchone()
    if not policy or not record:
        return False
    p, r = dict(policy), dict(record)
    if not p["enabled"]:
        return True  # explicit administrative policy disable; audited separately
    if not _fresh(r, now):
        return False
    if (r["instance"],r["company_id"],r["model"]) != (p["instance"],p["company_id"],p["model"]):
        return False
    if r["state"] != p["state"]:
        return True
    return datetime.fromisoformat(r["source_modified_at"]) > now - timedelta(seconds=p["max_age_seconds"])
