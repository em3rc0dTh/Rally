"""Odoo model contract: minimum data for enterprise source-state assurance.

No personal names, payroll amounts, bank data, access tokens or arbitrary
provider payloads are persisted. Models here are candidates: every use must be
explicitly approved by the customer's Odoo instance, company and selector.
"""
import re
from datetime import datetime, timezone

# Logical Rally domain and permitted provider fields, not a certification that
# every Odoo edition has these modules and fields.
MODEL_CONTRACTS = {
    "crm.lead": ("crm", ("id", "company_id", "write_date", "stage_id")),
    "sale.order": ("sales", ("id", "company_id", "write_date", "state")),
    "purchase.order": ("procurement", ("id", "company_id", "write_date", "state")),
    "stock.picking": ("inventory", ("id", "company_id", "write_date", "state")),
    "hr.employee": ("workforce", ("id", "company_id", "write_date", "active")),
    "hr.attendance": ("workforce", ("id", "company_id", "write_date", "check_out")),
    "hr.leave": ("workforce", ("id", "company_id", "write_date", "state")),
    "hr.payslip": ("payroll", ("id", "company_id", "write_date", "state")),
    "hr.expense": ("expenses", ("id", "company_id", "write_date", "state")),
    "account.move": ("accounting", ("id", "company_id", "write_date", "state")),
    "account.payment": ("payments", ("id", "company_id", "write_date", "state")),
}
MODEL_NAMES = frozenset(MODEL_CONTRACTS)
NAMESPACE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
STATE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def valid_namespace(value):
    if not isinstance(value, str) or not NAMESPACE.fullmatch(value):
        raise ValueError("Invalid Odoo instance namespace")
    return value


def company_id(value):
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if type(value) is not int or value <= 0:
        raise ValueError("A positive Odoo company_id is required")
    return value


def record_state(model, record):
    if model not in MODEL_CONTRACTS:
        raise ValueError("Unsupported enterprise model")
    if model == "crm.lead":
        stage = record.get("stage_id")
        if isinstance(stage, (list, tuple)):
            stage = stage[0] if stage else None
        if type(stage) is not int or stage < 1:
            raise ValueError("CRM stage is absent/invalid")
        status = "stage:" + str(stage)
    elif model == "hr.employee":
        if type(record.get("active")) is not bool:
            raise ValueError("Employee active status unavailable")
        status = "active" if record["active"] else "inactive"
    elif model == "hr.attendance":
        if "check_out" not in record:
            raise ValueError("Attendance check_out field unavailable")
        status = "checked_out" if record["check_out"] else "checked_in"
    else:
        status = record.get("state")
    if not isinstance(status, str) or not STATE.fullmatch(status):
        raise ValueError("Odoo state is absent or not a safe token")
    return status


def source_timestamp(value):
    """Odoo's UTC write_date may use 'YYYY-MM-DD HH:MM:SS' with no offset."""
    if not isinstance(value, str):
        raise ValueError("Odoo write_date is required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Invalid source write_date") from error
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def normalize_record(model, row, instance, allowed_companies):
    if not isinstance(row, dict):
        raise ValueError("Unexpected Odoo record")
    rid = row.get("id")
    if type(rid) is not int or rid <= 0:
        raise ValueError("Odoo record ID is invalid")
    company = company_id(row.get("company_id"))
    if company not in allowed_companies:
        raise ValueError("Odoo returned a record outside the allowed company scope")
    return {
        "instance": valid_namespace(instance),
        "company_id": company,
        "model": model,
        "record_id": rid,
        "state": record_state(model, row),
        "source_modified_at": source_timestamp(row.get("write_date")),
    }
