"""Offline MK0 SQLite -> empty PostgreSQL copy. Stop writers and back up first."""
import argparse
from rally.storage import connect, initialize, transaction, all_rows

TABLES = ('tenants', 'assets', 'jobs', 'custody', 'evidence', 'cases', 'audit', 'idempotency', 'credentials', 'case_notes', 'connector_status', 'worker_status')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sqlite_path', help='Backup copy of SQLite DB; schema will be upgraded')
    args = parser.parse_args()
    initialize(args.sqlite_path)
    initialize()
    with connect(args.sqlite_path) as source, connect() as target:
        if not target.postgres:
            raise RuntimeError('RALLY_DATABASE_URL must point to PostgreSQL')
        with transaction(target):
            if target.execute('SELECT 1 FROM tenants LIMIT 1').fetchone():
                raise RuntimeError('Destination must be empty')
            source.execute('BEGIN IMMEDIATE')
            try:
                for table in TABLES:
                    cursor = source.execute('SELECT * FROM ' + table)
                    count = 0
                    while rows := cursor.fetchmany(500):
                        for raw in rows:
                            row = dict(raw)
                            columns = ','.join(row)
                            placeholders = ','.join('?' for _ in row)
                            target.execute(f'INSERT INTO {table}({columns}) VALUES({placeholders})', tuple(row.values()))
                            count += 1
                    print(f'{table}: {count} records copied')
            finally:
                source.rollback()
    print('Copy committed. Source retained. Configure service URL for cutover.')


if __name__ == '__main__':
    main()
