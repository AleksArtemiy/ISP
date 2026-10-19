"""Local production-profile HTTPS/CRUD/NAT drill, using only synthetic data.

Requires the repository's isolated PostgreSQL cluster at 127.0.0.1:55432,
a portable nginx executable and OpenSSL. No service, trust store or scheduler
is installed. Databases and evidence are retained; child servers stop on exit.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import hashlib
import http.client
import http.cookiejar
import io
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


class Session:
    def __init__(self, base, context):
        self.base = base
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=context), urllib.request.ProxyHandler({}))

    def request(self, path, fields=None, files=(), csrf=True, headers=None):
        extra = dict(headers or {})
        body = None
        if fields is not None:
            fields = dict(fields)
            if csrf:
                _, page, _, _ = self.request(path)
                token = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page)
                if not token:
                    raise AssertionError('No CSRF token at ' + path)
                fields['csrfmiddlewaretoken'] = token.group(1).decode()
            if files:
                boundary = uuid.uuid4().hex
                pieces = []
                for name, value in fields.items():
                    pieces.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
                for field, filename, content in files:
                    pieces.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + content + b'\r\n')
                body = b''.join(pieces) + f'--{boundary}--\r\n'.encode()
                extra['Content-Type'] = 'multipart/form-data; boundary=' + boundary
            else:
                body = urllib.parse.urlencode(fields).encode()
            extra.update(Origin=self.base, Referer=self.base + path)
        request = urllib.request.Request(self.base + path, data=body, headers=extra)
        try:
            response = self.opener.open(request, timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), dict(response.headers), response.url

    def login(self, email, password, admin=False):
        path = '/admin/login/' if admin else '/login/'
        key = 'username' if admin else 'email'
        started = time.perf_counter()
        fields = {key: email, 'password': password}
        if admin:
            fields['next'] = '/admin/'
        response = self.request(path, fields)
        assert response[0] == 200 and '/login/' not in response[3], (email, response[0], response[3])
        return time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nginx', type=Path, required=True)
    parser.add_argument('--openssl', type=Path, required=True)
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--artifact-root', type=Path, required=True,
                        help='Writable ASCII-only directory for Windows nginx paths')
    parser.add_argument('--hold', action='store_true', help='Keep the drill available for browser acceptance until Enter')
    args = parser.parse_args()
    artifact = args.artifact_root.resolve() / ('stage1_proxy_' + uuid.uuid4().hex[:10])
    artifact.mkdir(parents=True)
    if not str(artifact).isascii():
        raise SystemExit('Use an ASCII artifact path for portable Windows nginx.')
    params = dict(host='127.0.0.1', port=55432, user='stage1_test', password='')
    database = artifact.name
    role_name = database.replace('stage1_proxy_', 'stage1_app_')
    restored = database.replace('stage1_proxy_', 'stage1_proxy_restore_')
    admin = psycopg2.connect(dbname='postgres', **params)
    try:
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute("SELECT pg_read_binary_file('postmaster.pid')")
            if bytes(cursor.fetchone()[0]) != (ROOT / '.stage1/pg_data/postmaster.pid').read_bytes():
                raise SystemExit('Refusing any cluster except the repository isolated drill.')
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Identifier(role_name)))
            for name in (database, restored):
                cursor.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(name), sql.Identifier(role_name)))
    finally:
        admin.close()
    args.nginx = args.nginx.resolve()
    args.openssl = args.openssl.resolve()
    args.pg_bin = args.pg_bin.resolve()
    backend_port, tls_port, http_port = free_port(), free_port(), free_port()
    base = f'https://127.0.0.1:{tls_port}'
    media = artifact / 'private-media'
    media.mkdir()
    env = dict(os.environ, PYTHON_DOTENV_DISABLED='1', PYTHONIOENCODING='utf-8',
               DJANGO_SETTINGS_MODULE='config.settings', DJANGO_ENV='production',
               DJANGO_SECRET_KEY='local-drill-only-' + uuid.uuid4().hex + uuid.uuid4().hex,
               DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost',
               DJANGO_CSRF_TRUSTED_ORIGINS=base, DJANGO_TRUST_PROXY='False',
               DJANGO_SECURE_SSL_REDIRECT='True', DJANGO_SECURE_HSTS_SECONDS='3600',
               DB_HOST='127.0.0.1', DB_PORT='55432', DB_NAME=database, DB_USER=role_name,
               DB_PASSWORD='', DJANGO_MEDIA_ROOT=str(media), DJANGO_TRUSTED_PROXY_IPS='')
    # The local cluster uses loopback trust, solely for these synthetic accounts.
    # All application settings and PBKDF2 are the actual production profile.
    os.environ.update(env)
    commands = []

    def run(label, command, run_env=None):
        result = subprocess.run([str(value) for value in command], cwd=ROOT,
                                env=run_env or env, text=True, encoding='utf-8',
                                errors='replace', capture_output=True, timeout=120)
        (artifact / (label + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        commands.append(dict(label=label, exit_code=result.returncode))
        if result.returncode:
            raise RuntimeError(label + ': ' + result.stderr[-2000:])
        return result.stdout

    for name, flags in (('migrate', ['--noinput']), ('check', ['--deploy']),
                        ('schema_preflight', []), ('collectstatic', ['--noinput'])):
        run(name, [sys.executable, 'manage.py', name, *flags])
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth.hashers import make_password
    from django.db import connections
    from django.utils import timezone
    from apps.accounts.models import LoginThrottle, Role, User
    from apps.institutions.models import Institution, InstitutionType
    from apps.prescriptions.models import File, Order, SupervisoryAuthority
    from PIL import Image
    from pypdf import PdfWriter

    assert settings.IS_PRODUCTION and not settings.DEBUG
    assert settings.PASSWORD_HASHERS[0].endswith('PBKDF2PasswordHasher')
    kind = InstitutionType.objects.create(name='Rehearsal school')
    institutions = [Institution.objects.create(name=f'Synthetic school {n}', short_name=f'TEST-{n}',
                    address='Synthetic address', institution_type=kind) for n in range(22)]
    authority = SupervisoryAuthority.objects.create(name='Rehearsal authority')
    password = 'Synthetic-Rehearsal-Only-941!'
    # Same synthetic password and production hash for fixture creation only.
    # Each measured login still performs a full PBKDF2 verification.
    fixture_password = make_password(password)
    users = []
    for n in range(40):
        user = User.objects.create(email=f'proxy-{n}@example.test', password=fixture_password,
                  role=Role.objects.get(code='DIRECTOR' if n in (0, 1) else 'COMMITTEE'),
                  institution=institutions[n] if n in (0, 1) else None)
        users.append(user)
    app_admin = User.objects.create_user('app-admin@example.test', password, role=Role.objects.get(code='ADMIN'))
    system = User.objects.create_superuser('system@example.test', password)
    for n, institution in enumerate(institutions):
        for m in range(5):
            Order.objects.create(number=f'PROXY-{n}-{m}', institution=institution,
                authority=authority, created_by_user=users[2], issue_date=date.today(),
                deadline_date=date.today()+timedelta(days=30))
    foreign_order = Order.objects.filter(institution=institutions[1]).first()
    own_order = Order.objects.filter(institution=institutions[0]).first()
    png = io.BytesIO()
    Image.frombytes('RGB', (1800, 1900), random.Random(941).randbytes(1800*1900*3)).save(png, format='PNG', compress_level=0)
    attachment = png.getvalue()
    assert 9*1024*1024 < len(attachment) < 10*1024*1024
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf = io.BytesIO()
    writer.write(pdf)
    small_report = pdf.getvalue()
    shutil.copytree(settings.STATIC_ROOT, artifact / 'static')
    (artifact / 'logs').mkdir()
    (artifact / 'temp').mkdir()
    run('certificate', [args.openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
        '-keyout', artifact/'key.pem', '-out', artifact/'cert.pem', '-days', '2',
        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'])
    template = (ROOT / 'deploy/nginx.conf.example').read_text(encoding='utf-8')
    adapted = template.replace('listen 80;', f'listen 127.0.0.1:{http_port};').replace(
        'listen 443 ssl;', f'listen 127.0.0.1:{tls_port} ssl;').replace(
        'minobr.example.test', '127.0.0.1').replace('https://$host$request_uri',
        f'https://$host:{tls_port}$request_uri').replace('/etc/ssl/minobr/fullchain.pem',
        (artifact/'cert.pem').as_posix()).replace('/etc/ssl/minobr/privkey.pem',
        (artifact/'key.pem').as_posix()).replace('/srv/minobr/current/staticfiles/',
        (artifact/'static').as_posix()+'/').replace('127.0.0.1:8000', f'127.0.0.1:{backend_port}')
    # These substitutions change only test addresses/paths; rate and location
    # directives are used verbatim from the shipped deployment example.
    conf = ('worker_processes 1;\npid logs/nginx.pid;\nevents { worker_connections 512; }\n'
            'http {\ninclude "' + (args.nginx.parent/'conf/mime.types').resolve().as_posix() + '";\n'
            'default_type application/octet-stream;\naccess_log logs/access.log;\n'
            'error_log logs/error.log warn;\n' + adapted)
    ui_port, ui_backend_port = free_port(), free_port()
    if args.hold:
        # A separate HTTP-only UI fixture avoids modifying the browser trust
        # store for our self-signed local TLS certificate. HTTPS tests above
        # use certificate validation with the explicit local CA file.
        conf += (f'\nserver {{ listen 127.0.0.1:{ui_port}; server_name 127.0.0.1;'
                 f' client_max_body_size 52m; location /static/ {{ alias {(artifact/"static").as_posix()}/; }}'
                 ' location /media/ { return 404; }'
                 f' location / {{ proxy_pass http://127.0.0.1:{ui_backend_port}; proxy_set_header Host $http_host; }} }}\n')
    conf += '\n}\n'
    config = artifact / 'nginx.conf'
    config.write_text(conf, encoding='utf-8')
    prefix = artifact.as_posix() + '/'
    run('nginx_config', [args.nginx, '-t', '-p', prefix, '-c', config])
    context = ssl.create_default_context(cafile=str(artifact/'cert.pem'))
    server_log = (artifact/'waitress.log').open('ab')
    backend = nginx = ui_backend = None
    metrics, checks = {}, {}

    def start_backend(database_name, listen_port=None, overrides=None):
        return subprocess.Popen([sys.executable, '-m', 'waitress',
            f'--listen=127.0.0.1:{listen_port or backend_port}', '--threads=8', '--trusted-proxy=127.0.0.1',
            '--trusted-proxy-headers=x-forwarded-for x-forwarded-proto',
            '--max-request-body-size=54525952', 'config.wsgi:application'], cwd=ROOT,
            env=dict(env, DB_NAME=database_name, **(overrides or {})), stdout=server_log, stderr=server_log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def ready(site=base):
        for _ in range(120):
            try:
                if Session(site, context).request('/login/')[0] == 200:
                    return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(.25)
        raise RuntimeError('HTTPS application did not start')

    def timed(label, operation):
        started = time.perf_counter()
        value = operation()
        metrics.setdefault(label, []).append(time.perf_counter()-started)
        return value

    try:
        connections.close_all()
        backend = start_backend(database)
        nginx = subprocess.Popen([str(args.nginx), '-p', prefix, '-c', str(config)], cwd=artifact,
            stdout=server_log, stderr=server_log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        ready()
        print('Production HTTPS ready; starting 40 concurrent PBKDF2 logins.', flush=True)
        def nat_login(user):
            session = Session(base, context)
            seconds = session.login(user.email, password)
            return session, seconds
        with ThreadPoolExecutor(max_workers=40) as pool:
            logged_in = list(pool.map(nat_login, users))
        metrics['40 concurrent logins'] = [row[1] for row in logged_in]
        sessions = [row[0] for row in logged_in]
        assert not LoginThrottle.objects.filter(attempts__gt=0).exists()
        checks['40_successful_nat_logins_zero_budget'] = True
        print('40 NAT logins passed; checking pages, writes and access controls.', flush=True)
        for path, label in (('/', 'dashboard'), ('/prescriptions/', 'list'),
                            (f'/prescriptions/{own_order.pk}/', 'detail')):
            def read(session):
                start = time.perf_counter()
                scoped_path = f'/prescriptions/{foreign_order.pk}/' if label == 'detail' and session is sessions[1] else path
                assert session.request(scoped_path)[0] == 200
                return time.perf_counter()-start
            with ThreadPoolExecutor(max_workers=40) as pool:
                metrics[label] = list(pool.map(read, sessions))
        director, committee = sessions[0], sessions[2]
        assert director.request(f'/prescriptions/{foreign_order.pk}/')[0] == 404
        assert sessions[1].request(f'/prescriptions/{own_order.pk}/')[0] == 404
        assert director.request('/admin-panel/')[0] == 403
        checks['director_scope'] = True
        payload = dict(number='HTTPS-CREATE', institution=institutions[1].pk,
                       authority=authority.pk, issue_date=date.today().isoformat(),
                       deadline_date=(date.today()+timedelta(days=30)).isoformat(),
                       created_by_user=system.pk, status='COMPLETED',
                       **{'violations-TOTAL_FORMS': '1', 'violations-INITIAL_FORMS': '0',
                          'violations-0-text': 'Synthetic HTTPS violation'})
        response = timed('create with near-10MiB PNG', lambda: director.request(
            '/prescriptions/create/', payload, [('attachments', 'near-limit.png', attachment)]))
        created = Order.objects.get(number='HTTPS-CREATE')
        assert response[0] == 200 and created.institution_id == institutions[0].pk
        assert created.created_by_user_id == users[0].pk and created.status == 'NEW'
        file = File.objects.get(order=created)
        downloaded = committee.request(f'/prescriptions/files/{file.pk}/download/')
        assert downloaded[0] == 200 and hashlib.sha256(downloaded[1]).digest() == hashlib.sha256(attachment).digest()
        assert downloaded[2]['X-Content-Type-Options'] == 'nosniff'
        assert downloaded[2]['Content-Disposition'].startswith('attachment;')
        assert Session(base, context).request('/media/' + file.file_path.replace('\\', '/'))[0] == 404
        assert sessions[1].request(f'/prescriptions/files/{file.pk}/download/')[0] == 404
        assert b'HTTPS-CREATE' in timed('committee visibility', lambda: committee.request('/prescriptions/'))[1]
        checks['create_owner_scope_and_private_download'] = True
        edit = dict(payload, number='HTTPS-EDIT', status='NEW', **{'violations-INITIAL_FORMS': '0'})
        assert director.request(f'/prescriptions/update/{created.pk}/', edit)[0] == 200
        created.refresh_from_db()
        assert created.number == 'HTTPS-EDIT' and created.created_by_user_id == users[0].pk
        complete_path = f'/prescriptions/complete/{created.pk}/'
        director.request(complete_path, {})
        created.refresh_from_db()
        assert created.status != 'COMPLETED'
        response = timed('complete with PDF', lambda: director.request(complete_path, {}, [('report', 'report.pdf', small_report)]))
        created.refresh_from_db()
        assert response[0] == 200 and created.status == 'COMPLETED' and created.files.count() == 2
        checks['completion_requires_report'] = True
        admin_session = Session(base, context)
        admin_session.login(app_admin.email, password)
        assert admin_session.request('/admin-panel/')[0] == 200
        assert '/admin/login/' in admin_session.request('/admin/')[3]
        system_session = Session(base, context)
        system_session.login(system.email, password, admin=True)
        admin_path = f'/admin/prescriptions/order/{own_order.pk}/change/'
        assert system_session.request(admin_path)[0] == 200
        # Obtain a token from the standard admin page; view-only detail has no form.
        _, admin_page, _, _ = system_session.request('/admin/password_change/')
        token = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', admin_page).group(1).decode()
        assert system_session.request(admin_path, dict(csrfmiddlewaretoken=token,
                   created_by_user=system.pk, status='COMPLETED'), csrf=False)[0] == 403
        own_order.refresh_from_db()
        assert own_order.created_by_user_id == users[2].pk and own_order.status == 'NEW'
        assert system_session.request(f'/admin/prescriptions/file/{file.pk}/delete/',
                dict(csrfmiddlewaretoken=token, post='yes'), csrf=False)[0] == 403
        assert File.objects.filter(pk=file.pk).exists() and (media/file.file_path).exists()
        checks['admin_invariants_and_history'] = True
        assert director.request('/logout/', {}, csrf=False)[0] == 403
        page = committee.request('/prescriptions/')[2]
        assert page['Strict-Transport-Security'] == 'max-age=3600'
        assert page['X-Frame-Options'] == 'DENY'
        session_cookie = next(c for c in committee.cookies if c.name == 'sessionid')
        assert session_cookie.secure and session_cookie.has_nonstandard_attr('HttpOnly')
        assert Session(base, context).request('/static/css/style.css')[0] == 200
        connection = http.client.HTTPConnection('127.0.0.1', http_port, timeout=10)
        connection.request('GET', '/login/')
        redirect = connection.getresponse()
        assert redirect.status == 301 and redirect.getheader('Location') == base+'/login/'
        redirect.read()
        connection.close()
        oversized = http.client.HTTPSConnection('127.0.0.1', tls_port, context=context, timeout=10)
        oversized.putrequest('POST', '/prescriptions/create/')
        oversized.putheader('Content-Length', str(53*1024*1024))
        oversized.endheaders()
        assert oversized.getresponse().status == 413
        oversized.close()
        checks['tls_csrf_headers_static_and_body_limit'] = True
        # Empty credentials return early: this isolates nginx's rate guard and
        # does not spend CPU on hundreds of PBKDF2 checks or application budget.
        def flood(_):
            return Session(base, context).request('/login/', {}, csrf=False)[0]
        with ThreadPoolExecutor(max_workers=80) as pool:
            statuses = list(pool.map(flood, range(200)))
        assert 429 in statuses and set(statuses) <= {403, 429}
        assert all(Session(base, context).request('/login/')[0] == 200 for _ in range(80))
        checks['nginx_flood_guard_and_unlimited_get'] = {str(n): statuses.count(n) for n in sorted(set(statuses))}
        LoginThrottle.objects.create(key='expired-local-drill', attempts=3,
                                    started_at=timezone.now()-timedelta(minutes=20))
        fresh = LoginThrottle.objects.create(key='fresh-local-drill', attempts=2, started_at=timezone.now())
        run('cleanup_login_counters', [sys.executable, 'manage.py', 'cleanup_login_counters'])
        assert not LoginThrottle.objects.filter(pk='expired-local-drill').exists()
        fresh.refresh_from_db()
        assert fresh.attempts == 2
        overdue = Order.objects.create(number='SCHEDULER-EXPIRED', institution=institutions[0],
            authority=authority, created_by_user=users[0], issue_date=date.today()-timedelta(days=30),
            deadline_date=date.today()-timedelta(days=1), status='IN_PROGRESS')
        run('update_statuses_first', [sys.executable, 'manage.py', 'update_order_statuses'])
        second = run('update_statuses_second', [sys.executable, 'manage.py', 'update_order_statuses'])
        overdue.refresh_from_db()
        created.refresh_from_db()
        assert overdue.status == 'OVERDUE' and created.status == 'COMPLETED' and 'Изменено: 0' in second
        checks['scheduler_commands_and_idempotency'] = True
        pg_env = dict(env, PGPASSWORD='')
        common = ['-h', '127.0.0.1', '-p', '55432', '-U', role_name]
        suffix = '.exe' if os.name == 'nt' else ''
        run('backup', [args.pg_bin/('pg_dump'+suffix), *common, '-d', database,
                      '-Fc', '-f', artifact/'database.dump'], pg_env)
        recovery_start = time.perf_counter()
        run('restore', [args.pg_bin/('pg_restore'+suffix), *common, '-d', restored,
                       '--no-owner', '--no-acl', artifact/'database.dump'], pg_env)
        restored_media = artifact/'restored-media'
        shutil.copytree(media, restored_media)
        for source in media.rglob('*'):
            if source.is_file():
                assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256((restored_media/source.relative_to(media)).read_bytes()).digest()
        with psycopg2.connect(dbname=restored, **params) as recovered:
            with recovered.cursor() as cursor:
                for table, count in [('users', User.objects.count()), ('orders', Order.objects.count()), ('files', File.objects.count())]:
                    cursor.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
                    assert cursor.fetchone()[0] == count
        backend.terminate()
        backend.wait(timeout=10)
        env['DJANGO_MEDIA_ROOT'] = str(restored_media)
        backend = start_backend(restored)
        ready()
        recovery_session = Session(base, context)
        recovery_session.login(users[2].email, password)
        assert recovery_session.request(f'/prescriptions/files/{file.pk}/download/')[1] == attachment
        assert recovery_session.request(f'/prescriptions/{created.pk}/')[0] == 200
        metrics['restore and HTTPS smoke'] = [time.perf_counter()-recovery_start]
        checks['backup_restore_http_and_file_hashes'] = True
        print('HTTPS CRUD, protection, maintenance commands and restore passed.', flush=True)
        with psycopg2.connect(dbname=database, user=role_name, host='127.0.0.1', port=55432) as runtime:
            with runtime.cursor() as cursor:
                cursor.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=current_user')
                assert cursor.fetchone() == (False, False, False, False)
        checks['unprivileged_application_role'] = True
        summary = {}
        for label, values in metrics.items():
            values = sorted(values)
            summary[label] = dict(requests=len(values), p50=round(values[math.ceil(len(values)*.5)-1], 4),
                                  p95=round(values[math.ceil(len(values)*.95)-1], 4), max=round(max(values), 4))
        result = dict(source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            database=database, restored_database=restored, app_role=role_name, url=base,
            browser_url=f'http://127.0.0.1:{ui_port}' if args.hold else None,
            attachment_bytes=len(attachment), commands=commands, checks=checks, metrics=summary,
            functional_checks_passed=True,
            stress_pages_p95_within_3s=all(summary[name]['p95'] <= 3 for name in ('dashboard', 'list', 'detail')),
            scope='Local Windows nginx HTTPS, synthetic PostgreSQL, production settings/PBKDF2; not target-server acceptance',
            browser_accounts={'committee': users[2].email, 'director': users[0].email,
                              'admin': app_admin.email, 'system': system.email, 'synthetic_password': password})
        (artifact/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        print('Evidence:', artifact, flush=True)
        if args.hold:
            ui_backend = start_backend(restored, ui_backend_port,
                                       {'DJANGO_ENV': 'development', 'DJANGO_DEBUG': 'False'})
            ready(result['browser_url'])
            input('Restored HTTP UI fixture is ready; HTTPS checked separately. Press Enter to stop.\n')
    finally:
        connections.close_all()
        if nginx is not None:
            subprocess.run([str(args.nginx), '-p', prefix, '-c', str(config), '-s', 'quit'],
                           cwd=artifact, capture_output=True, timeout=10)
            try:
                nginx.wait(timeout=15)
            except subprocess.TimeoutExpired:
                nginx.terminate()
                nginx.wait(timeout=10)
        if backend is not None and backend.poll() is None:
            backend.terminate()
            backend.wait(timeout=10)
        if ui_backend is not None and ui_backend.poll() is None:
            ui_backend.terminate()
            ui_backend.wait(timeout=10)
        server_log.close()


if __name__ == '__main__':
    main()
