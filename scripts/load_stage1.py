"""Local HTTP load rehearsal: 30 independent authenticated browser sessions.

Synthetic isolated database only. No production credentials or external hosts.
Uses the same Waitress dependency as the deployment recipe. Assets are excluded.
"""
import concurrent.futures
import faulthandler
import http.cookiejar
import json
import math
import os
import re
import sys
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'


def main():
    import django
    django.setup()
    from django.conf import settings
    from django.test import override_settings
    from django.db import connection
    from django.utils import timezone
    if not settings.DATABASES['default']['NAME'].startswith('stage1_clean_'):
        raise SystemExit('Set TEST_DB_NAME to a disposable stage1_clean_* database created by verify_stage1.py.')
    from apps.accounts.models import Role, User, LoginThrottle
    from apps.institutions.models import Institution, InstitutionType
    from apps.prescriptions.models import Order, SupervisoryAuthority
    from django.core.wsgi import get_wsgi_application
    from waitress import create_server

    override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher']).enable()

    users = []
    LoginThrottle.objects.update(attempts=0, started_at=timezone.now())
    password = 'Synthetic-load-password-842!'
    role = Role.objects.get(code='COMMITTEE')
    for n in range(30):
        user, _ = User.objects.get_or_create(email=f'load-{n}@example.test', defaults={'role': role})
        user.set_password(password)
        user.save()
        users.append(user.email)
    kind, _ = InstitutionType.objects.get_or_create(name='Load school')
    authority, _ = SupervisoryAuthority.objects.get_or_create(name='Load authority')
    for n in range(22):
        institution, _ = Institution.objects.get_or_create(short_name=f'LOAD-{n}',
            defaults={'name': f'Synthetic school {n}', 'address': 'Synthetic address', 'institution_type': kind})
        for m in range(5):
            Order.objects.get_or_create(number=f'LOAD-{n}-{m}', defaults={
                'institution': institution, 'authority': authority, 'created_by_user': user,
                'issue_date': date.today(), 'deadline_date': date.today()+timedelta(days=30)})
    order_id = Order.objects.filter(number__startswith='LOAD-').first().pk
    connection.close()
    server = create_server(get_wsgi_application(), listen='127.0.0.1:0', threads=8,
                           max_request_body_size=52*1024*1024)
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.effective_port}'
    barrier = threading.Barrier(30)
    measurements = []

    def client(email):
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with opener.open(base+'/login/', timeout=60) as response:
            page = response.read().decode('utf-8')
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
        started = time.perf_counter()
        data = urllib.parse.urlencode({'csrfmiddlewaretoken': csrf, 'email': email, 'password': password}).encode()
        with opener.open(urllib.request.Request(base+'/login/', data=data), timeout=60) as response:
            response.read()
            assert response.status == 200 and '/login/' not in response.url
        values = [('login and redirect', time.perf_counter()-started)]
        barrier.wait(timeout=45)
        for _ in range(2):
            for label, path in (('dashboard', '/'), ('list', '/prescriptions/'), ('detail', f'/prescriptions/{order_id}/')):
                started = time.perf_counter()
                with opener.open(base+path, timeout=60) as response:
                    response.read()
                    assert response.status == 200
                values.append((label, time.perf_counter()-started))
        return values

    errors = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
            futures = [pool.submit(client, email) for email in users]
            for future in concurrent.futures.as_completed(futures):
                try:
                    measurements.extend(future.result())
                except Exception as error:
                    barrier.abort()
                    errors.append(type(error).__name__ + ': ' + str(error))
    finally:
        server.task_dispatcher.shutdown(timeout=3)
        server.close()
    metrics = {}
    for label in sorted({row[0] for row in measurements}):
        values = sorted(seconds for name, seconds in measurements if name == label)
        metrics[label] = {'requests': len(values), 'p50_seconds': round(values[math.ceil(len(values)*0.50)-1], 4),
                          'p95_seconds': round(values[math.ceil(len(values)*0.95)-1], 4),
                          'p99_seconds': round(values[math.ceil(len(values)*0.99)-1], 4)}
    result = {'concurrent_sessions': 30, 'threads': 8, 'synthetic_institutions': 22,
              'synthetic_orders': 110, 'metrics': metrics, 'errors': errors,
              'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'password_hasher': 'PBKDF2PasswordHasher',
              'scope': 'Local loopback HTTP and synthetic PostgreSQL; no TLS/proxy/browser assets.'}
    target = ROOT/'.stage1'/settings.DATABASES['default']['NAME']/'load.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    faulthandler.cancel_dump_traceback_later()
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if errors or len(measurements) != 210 or any(v['p95_seconds'] > 3 for key, v in metrics.items() if key != 'login and redirect'):
        raise SystemExit(1)


if __name__ == '__main__':
    faulthandler.dump_traceback_later(50)
    main()
