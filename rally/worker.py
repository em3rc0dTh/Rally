"""Restartable periodic reconciliation; business state remains in the database."""
import logging
import os
import signal
import threading
from rally.app import reconcile, stamp
from rally.security import validate_environment
from rally.storage import connect, initialize, all_rows, transaction


def main():
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('rally.worker')
    validate_environment()
    initialize()
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    interval = max(10, int(os.getenv('RALLY_RECONCILE_SECONDS', '60')))
    while not stop.is_set():
        try:
            with connect() as db:
                for row in all_rows(db, 'SELECT id FROM tenants ORDER BY id'):
                    if stop.is_set():
                        return
                    db.actor_id = 'system:reconciliation'
                    reconcile(row['id'], db)
                with transaction(db):
                    db.execute("INSERT INTO worker_status(name,last_success) VALUES('reconciliation',?) "
                               "ON CONFLICT(name) DO UPDATE SET last_success=excluded.last_success", (stamp(),))
            log.info('Reconciliation cycle completed')
        except Exception as error:
            # Driver error strings can contain connection details; report class only.
            log.error('Reconciliation cycle failed: %s', type(error).__name__)
        stop.wait(interval)


if __name__ == '__main__':
    main()
