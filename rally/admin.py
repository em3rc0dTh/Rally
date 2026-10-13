"""Deployment-operator credential recovery, requiring direct database access."""
import argparse
from hashlib import sha256
from secrets import token_urlsafe
from rally.app import audit, stamp, uid
from rally.security import validate_environment
from rally.storage import connect, initialize, one, transaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['recover'])
    parser.add_argument('tenant_id')
    parser.add_argument('name', help='Named administrator receiving the new credential')
    args = parser.parse_args()
    if not 2 <= len(args.name.strip()) <= 120:
        parser.error('Name must contain 2–120 characters')
    validate_environment()
    initialize()
    with connect() as db, transaction(db):
        if not one(db, 'SELECT id FROM tenants WHERE id=?', (args.tenant_id,)):
            raise SystemExit('Tenant not found')
        raw, cid = token_urlsafe(48), uid()
        db.execute("INSERT INTO credentials(id,tenant_id,name,role,token_hash,created_at) VALUES(?,?,?,'admin',?,?)",
                   (cid, args.tenant_id, args.name.strip(), sha256(raw.encode()).hexdigest(), stamp()))
        db.actor_id = 'platform:local-recovery'
        audit(db, args.tenant_id, 'credential', cid, 'recovered_by_deployment_operator')
    print('Save this one-time administrator token securely; do not paste into logs:')
    print(raw)


if __name__ == '__main__':
    main()
