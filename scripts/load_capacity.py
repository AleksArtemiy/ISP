"""Compare WSGI process capacity using already seeded synthetic load fixtures.

The HTTP generator and each Waitress worker run in different Python processes.
No application data is seeded or changed except normal login/session counters.
Use the local isolated stage1_clean_* DB from verify_stage1.py/load_stage1.py.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import ssl
import subprocess
import sys
import threading
import time

import psycopg2

from rehearse_proxy import ROOT, Session, free_port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--processes', type=int, default=1, choices=range(1, 9))
    args = parser.parse_args()
    if not args.database.startswith('stage1_clean_'):
        raise SystemExit('Only seeded stage1_clean_* fixtures are allowed.')
    with psycopg2.connect(dbname=args.database, host='127.0.0.1', port=55432,
                          user='stage1_test', password='') as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_read_binary_file('postmaster.pid')")
            if bytes(cursor.fetchone()[0]) != (ROOT/'.stage1/pg_data/postmaster.pid').read_bytes():
                raise SystemExit('Not the repository isolated cluster.')
            cursor.execute('SELECT id FROM orders ORDER BY id LIMIT 1')
            order_id = cursor.fetchone()[0]
            cursor.execute('SELECT count(*) FROM institutions')
            institutions = cursor.fetchone()[0]
            cursor.execute('SELECT count(*) FROM orders')
            orders = cursor.fetchone()[0]
    artifact = ROOT/'.stage1'/args.database
    target = artifact/f'capacity-{args.processes}.json'
    env = dict(os.environ, PYTHON_DOTENV_DISABLED='1', PYTHONIOENCODING='utf-8',
        DJANGO_SETTINGS_MODULE='config.settings', DJANGO_ENV='development',
        DJANGO_DEBUG='False', DJANGO_SECRET_KEY='synthetic-capacity-only-'+('941!'*20),
        DJANGO_ALLOWED_HOSTS='127.0.0.1', DB_NAME=args.database, DB_HOST='127.0.0.1',
        DB_PORT='55432', DB_USER='stage1_test', DB_PASSWORD='',
        DJANGO_MEDIA_ROOT=str(artifact/'media'))
    context = ssl.create_default_context()
    password = 'Synthetic-load-password-842!'
    processes, logs, bases = [], [], []
    errors, measurements = [], []
    barrier = threading.Barrier(30)
    try:
        for n in range(args.processes):
            port = free_port()
            log = (artifact/f'capacity-{args.processes}-worker-{n}.log').open('wb')
            process = subprocess.Popen([sys.executable, '-m', 'waitress',
                f'--listen=127.0.0.1:{port}', '--threads=8', 'config.wsgi:application'],
                cwd=ROOT, env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            processes.append(process)
            logs.append(log)
            base = f'http://127.0.0.1:{port}'
            for _ in range(80):
                try:
                    if Session(base, context).request('/login/')[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError('Waitress worker did not start')
            warmup = Session(base, context)
            warmup.login('load-0@example.test', password)
            for path in ('/', '/prescriptions/', f'/prescriptions/{order_id}/'):
                assert warmup.request(path)[0] == 200
            bases.append(base)

        def client(n):
            session = Session(bases[n % len(bases)], context)
            values = [('login and redirect', session.login(f'load-{n}@example.test', password))]
            barrier.wait(timeout=120)
            for _ in range(2):
                for label, path in (('dashboard', '/'), ('list', '/prescriptions/'),
                                    ('detail', f'/prescriptions/{order_id}/')):
                    start = time.perf_counter()
                    assert session.request(path)[0] == 200
                    values.append((label, time.perf_counter()-start))
            return values

        with ThreadPoolExecutor(max_workers=30) as pool:
            for future in as_completed([pool.submit(client, n) for n in range(30)]):
                try:
                    measurements.extend(future.result())
                except Exception as error:
                    barrier.abort()
                    errors.append(type(error).__name__ + ': ' + str(error))
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
        for log in logs:
            log.close()
    metrics = {}
    for label in sorted({row[0] for row in measurements}):
        values = sorted(value for name, value in measurements if name == label)
        metrics[label] = dict(requests=len(values), p50=round(values[math.ceil(len(values)*.5)-1], 4),
            p95=round(values[math.ceil(len(values)*.95)-1], 4), max=round(max(values), 4))
    pages_pass = len(measurements) == 210 and not errors and all(
        row['p95'] <= 3 for label, row in metrics.items() if label != 'login and redirect')
    result = dict(source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        concurrent_sessions=30, wsgi_processes=args.processes, threads_per_process=8,
        database=args.database, actual_institutions=institutions, actual_orders=orders,
        logical_cpus=os.cpu_count(), platform=platform.platform(), metrics=metrics,
        errors=errors, pages_p95_within_3s=pages_pass,
        scope='Loopback HTTP, separate generator/WSGI processes, PBKDF2, synthetic data; no TLS/proxy/assets')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    raise SystemExit(0 if pages_pass else 1)


if __name__ == '__main__':
    main()
