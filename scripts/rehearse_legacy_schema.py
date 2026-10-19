"""Compare a reviewed schema dump with a fresh release DB, in the local drill only.

Imports into new databases on the repository's isolated 55432 cluster. Keeps the
raw import intact; ordinary/fake-initial migration probes run on separate clones.
This is evidence collection, NOT an upgrade or migration-history repair tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent


def snapshot(name, params):
    with psycopg2.connect(dbname=name, **params) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("""SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1""")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.execute("""SELECT table_name, column_name, data_type, udt_name,
                character_maximum_length, is_nullable, column_default, is_identity
                FROM information_schema.columns WHERE table_schema='public'
                ORDER BY table_name, ordinal_position""")
            columns = {}
            for table, column, *values in cursor.fetchall():
                columns.setdefault(table, {})[column] = values
            cursor.execute("""SELECT c.relname, con.conname, con.contype,
                pg_get_constraintdef(con.oid) FROM pg_constraint con
                JOIN pg_class c ON c.oid=con.conrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' ORDER BY 1,2""")
            constraints = cursor.fetchall()
            cursor.execute("""SELECT tablename,indexname,indexdef FROM pg_indexes
                WHERE schemaname='public' ORDER BY 1,2""")
            indexes = cursor.fetchall()
            counts = {}
            for table in tables:
                cursor.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
                counts[table] = cursor.fetchone()[0]
            cursor.execute('SELECT app,name FROM django_migrations ORDER BY app,name')
            migrations = cursor.fetchall()
            cursor.execute("""SELECT t.typname,e.enumlabel FROM pg_type t
                JOIN pg_enum e ON e.enumtypid=t.oid ORDER BY 1,e.enumsortorder""")
            enums = cursor.fetchall()
    return dict(tables=tables, columns=columns, constraints=constraints,
                indexes=indexes, counts=counts, migrations=migrations, enums=enums)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, required=True,
                        help='Reviewed plain SQL dump; psql executes its contents')
    parser.add_argument('--reference-db', required=True)
    parser.add_argument('--pg-bin', type=Path, required=True)
    args = parser.parse_args()
    if not args.reference_db.startswith('stage1_clean_'):
        raise SystemExit('Reference must be a synthetic stage1_clean_* database.')
    params = dict(host='127.0.0.1', port=55432, user='stage1_test', password='')
    connection = psycopg2.connect(dbname='postgres', **params)
    connection.autocommit = True
    with connection.cursor() as cursor:
        # Compare bytes: Windows PostgreSQL can expose a non-UTF8 path in SHOW
        # data_directory when its data folder contains Cyrillic characters.
        cursor.execute("SELECT pg_read_binary_file('postmaster.pid')")
        local_pid = ROOT / '.stage1' / 'pg_data' / 'postmaster.pid'
        if bytes(cursor.fetchone()[0]) != local_pid.read_bytes():
            raise SystemExit('Refusing any cluster except this repository isolated drill.')
        # The reviewed dump names this owner. It is a NOLOGIN role in this
        # synthetic cluster, not the operating PostgreSQL service account.
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='postgres'")
        if not cursor.fetchone():
            cursor.execute('CREATE ROLE postgres NOLOGIN NOSUPERUSER')
        suffix = uuid.uuid4().hex[:10]
        raw = 'stage1_schema_raw_' + suffix
        cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(raw)))
    artifact = ROOT / '.stage1' / raw
    artifact.mkdir()
    before = hashlib.sha256(args.schema.read_bytes()).hexdigest()
    env = dict(os.environ, PYTHON_DOTENV_DISABLED='1', PYTHONIOENCODING='utf-8',
               DJANGO_SETTINGS_MODULE='config.test_settings', TEST_DB_HOST='127.0.0.1',
               TEST_DB_PORT='55432', TEST_DB_USER='stage1_test', TEST_DB_PASSWORD='',
               PGPASSWORD='')
    commands = []

    def run(label, command, database, expected_failure=False):
        result = subprocess.run(command, cwd=ROOT, env=dict(env, TEST_DB_NAME=database),
                                text=True, encoding='utf-8', errors='replace',
                                capture_output=True, timeout=120)
        output = result.stdout + result.stderr
        (artifact / (label + '.log')).write_text(output, encoding='utf-8')
        commands.append(dict(label=label, database=database, exit_code=result.returncode,
                             expected_failure=expected_failure))
        if result.returncode and not expected_failure:
            raise RuntimeError(label + ': ' + output[-2000:])
        return result.returncode

    psql = args.pg_bin / ('psql.exe' if os.name == 'nt' else 'psql')
    run('import', [str(psql), '-X', '-h', '127.0.0.1', '-p', '55432', '-U',
                  'stage1_test', '-d', raw, '-v', 'ON_ERROR_STOP=1',
                  '--single-transaction', '-f', str(args.schema.resolve())], raw)
    original = snapshot(raw, params)
    reference = snapshot(args.reference_db, params)
    differences = []
    for table in sorted(set(original['tables']) & set(reference['tables'])):
        old, new = original['columns'][table], reference['columns'][table]
        for column in sorted(set(old) | set(new)):
            if old.get(column) != new.get(column):
                differences.append(dict(table=table, column=column,
                                        supplied=old.get(column), release=new.get(column)))
    constraints_old = {(t, kind, definition) for t, _, kind, definition in original['constraints']}
    constraints_new = {(t, kind, definition) for t, _, kind, definition in reference['constraints']}
    shared = set(original['tables']) & set(reference['tables'])
    constraint_diff = dict(
        supplied_only=sorted(row for row in constraints_old-constraints_new if row[0] in shared),
        release_only=sorted(row for row in constraints_new-constraints_old if row[0] in shared))
    run('preflight_raw', [sys.executable, 'manage.py', 'schema_preflight'], raw, True)
    clones = []
    for label, extra in (('ordinary', []), ('fake_initial', ['--fake-initial'])):
        clone = 'stage1_schema_' + label + '_' + suffix
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(
                sql.Identifier(clone), sql.Identifier(raw)))
        clones.append(clone)
        run(label, [sys.executable, 'manage.py', 'migrate', '--noinput', *extra], clone, True)
    connection.close()
    assert snapshot(raw, params) == original, 'Raw evidence database changed'
    after = hashlib.sha256(args.schema.read_bytes()).hexdigest()
    assert before == after, 'Source dump changed'
    report = dict(source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                    text=True).strip(),
                  schema_sha256=before, raw_database=raw, probe_databases=clones,
                  reference_database=args.reference_db, commands=commands,
                  missing_tables=sorted(set(reference['tables'])-set(original['tables'])),
                  additional_tables=sorted(set(original['tables'])-set(reference['tables'])),
                  column_value_order=['data_type', 'udt_name', 'max_length', 'nullable',
                                      'default', 'identity'],
                  column_differences=differences, constraint_differences=constraint_diff,
                  supplied=original, reference=reference,
                  source_and_raw_unchanged=True,
                  verdict='NO-GO: schema-only dump cannot establish data or migration history')
    (artifact / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                        encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('raw_database', 'missing_tables',
                                            'additional_tables', 'commands', 'verdict')}, indent=2))
    print('Evidence:', artifact)


if __name__ == '__main__':
    main()
