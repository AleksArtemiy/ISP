"""Fresh PostgreSQL deployment and restore drill using only synthetic data.

Run with an isolated PostgreSQL superuser via TEST_DB_*; never uses .env.
Databases are uniquely named stage1_clean_*/stage1_restore_* and retained.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pg-bin', default='')
    args = parser.parse_args()
    import django
    django.setup()
    from django.conf import settings
    from psycopg2 import connect, sql

    db = settings.DATABASES['default']
    if db['HOST'] not in ('127.0.0.1', 'localhost'):
        raise SystemExit('This local drill requires an isolated loopback PostgreSQL.')
    suffix = uuid.uuid4().hex[:10]
    name, restored = 'stage1_clean_' + suffix, 'stage1_restore_' + suffix
    artifact = ROOT / '.stage1' / name
    artifact.mkdir(parents=True)
    params = dict(host=db['HOST'], port=db['PORT'], user=db['USER'], password=db['PASSWORD'])
    admin = connect(dbname='postgres', **params)
    try:
        admin.autocommit = True
        with admin.cursor() as cursor:
            for target in (name, restored):
                cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(target)))
    finally:
        admin.close()
    os.environ['TEST_DB_NAME'] = name
    settings.DATABASES['default']['NAME'] = name
    from django.db import connections
    connections.close_all()
    connections['default'].settings_dict['NAME'] = name
    transcript, results = [], []

    def run(command):
        completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                   capture_output=True, text=True, encoding='utf-8', errors='replace')
        output = completed.stdout + completed.stderr
        print(output, end='')
        transcript.append('$ ' + ' '.join(str(c) for c in command) + '\n' + output)
        results.append({'command': [str(c) for c in command], 'exit_code': completed.returncode})
        (artifact / 'commands.txt').write_text('\n'.join(transcript), encoding='utf-8')
        if completed.returncode:
            raise SystemExit(completed.returncode)

    python = sys.executable
    for command in ('migrate --noinput', 'schema_preflight', 'check', 'makemigrations --check --dry-run', 'test --noinput', 'update_order_statuses', 'collectstatic --noinput'):
        run([python, 'manage.py', *command.split(), '--settings=config.test_settings'])
    run([python, 'scripts/check_production.py'])
    run(['git', 'diff', '--check'])

    from django.test import Client, override_settings
    from apps.accounts.models import Role, User
    from apps.institutions.models import Institution, InstitutionType
    from apps.prescriptions.models import File, Order, SupervisoryAuthority
    from apps.prescriptions.test_files import pdf_upload
    from apps.prescriptions.views import handle_uploaded_files
    roles = list(Role.objects.order_by('code').values_list('code', flat=True))
    assert roles == ['ADMIN', 'COMMITTEE', 'DIRECTOR'], roles
    user = User.objects.create_user('smoke@example.test', 'Synthetic-Smoke-941!', role=Role.objects.get(code='COMMITTEE'))
    kind = InstitutionType.objects.create(name='Synthetic school')
    institution = Institution.objects.create(name='Synthetic school', short_name='Synthetic', address='Test', institution_type=kind)
    authority = SupervisoryAuthority.objects.create(name='Synthetic authority')
    order = Order.objects.create(number='SMOKE-1', institution=institution, authority=authority,
                                created_by_user=user, issue_date=date.today(), deadline_date=date.today()+timedelta(days=30))
    media = artifact / 'media'
    with override_settings(MEDIA_ROOT=media):
        from django.db import transaction
        with transaction.atomic():
            paths = handle_uploaded_files(order, [pdf_upload()], user)
        client = Client()
        assert client.post('/login/', {'email': user.email, 'password': 'Synthetic-Smoke-941!'}).status_code == 302
        assert client.get('/').status_code == 200
        assert client.get('/prescriptions/').status_code == 200
        response = client.get(f'/prescriptions/files/{File.objects.get(order=order).pk}/download/')
        download_hash = hashlib.sha256(b''.join(response.streaming_content)).hexdigest()

    def binary(tool):
        candidate = Path(args.pg_bin) / (tool + ('.exe' if os.name == 'nt' else '')) if args.pg_bin else shutil.which(tool)
        if not candidate:
            raise SystemExit('Provide --pg-bin for pg_dump and pg_restore')
        return str(candidate)

    dump = artifact / 'database.dump'
    # Credentials are supplied only via process environment, never printed.
    os.environ['PGPASSWORD'] = db['PASSWORD']
    common = ['--host', db['HOST'], '--port', str(db['PORT']), '--username', db['USER']]
    run([binary('pg_dump'), *common, '--dbname', name, '--format=custom', '--file', str(dump)])
    run([binary('pg_restore'), *common, '--dbname', restored, '--no-owner', '--no-acl', str(dump)])
    restored_media = artifact / 'restored-media'
    shutil.copytree(media, restored_media)
    restored_hash = hashlib.sha256((restored_media / paths[0]).read_bytes()).hexdigest()
    assert download_hash == restored_hash
    with connect(dbname=restored, **params) as check:
        with check.cursor() as cursor:
            counts = {}
            for table in ('roles', 'users', 'institutions', 'orders', 'files'):
                cursor.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
                counts[table] = cursor.fetchone()[0]
    assert counts == {'roles': 3, 'users': 1, 'institutions': 1, 'orders': 1, 'files': 1}, counts
    report = {'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'clean_database': name, 'restore_database': restored, 'commands': results,
              'roles': roles, 'smoke_login_dashboard_download': 'PASS', 'restore_counts': counts,
              'restored_file_sha256_matches': download_hash == restored_hash}
    (artifact / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'Evidence: {artifact}')


if __name__ == '__main__':
    main()
