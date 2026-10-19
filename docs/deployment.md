# Развёртывание этапа 1

Поддерживаемый воспроизводимый стенд: Python 3.14, PostgreSQL 18,
Django и остальные зависимости закреплены в requirements.txt. Разработка
ведётся в Windows; deployment-примеры есть для Linux и Windows.

## Чистая установка

1. Получить review-approved release commit, создать отдельное venv и выполнить
   `python -m pip install -r requirements.txt`.
2. На чистом сервере администратор PostgreSQL выполняет deploy/database.sql,
   затем `\password minobr_app` в psql. Пароль хранится только в secret store
   или защищённом файле окружения, доступном служебной учётной записи.
3. Задать переменные окружения. Минимальный production-профиль:

```text
DJANGO_ENV=production
DJANGO_SECRET_KEY=<уникальное случайное значение минимум 50 символов>
DJANGO_ALLOWED_HOSTS=<реальный DNS-адрес>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<реальный DNS-адрес>
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=3600
DJANGO_TRUST_PROXY=False
DB_NAME=minobr
DB_USER=minobr_app
DB_PASSWORD=<пароль из secret store>
DB_HOST=127.0.0.1
DB_PORT=5432
DJANGO_MEDIA_ROOT=/srv/minobr/private-media
```

4. Выполнить `python manage.py migrate --noinput`, `python manage.py check`,
   `python manage.py makemigrations --check --dry-run`,
   `python manage.py collectstatic --noinput`, `python manage.py createsuperuser`.
   Таблицы и три системные роли создаются миграциями без SQL-импорта предметной
   схемы. Через прикладную панель создать прикладного ADMIN и тестовые роли.
5. Выполнить `python manage.py check --deploy` в реальном production-окружении.
   Локальный `python scripts/check_production.py` проверяет отдельный профиль с
   фиктивными значениями без чтения .env и не удостоверяет настройки сервера.

При HSTS=3600 остаются security.W005 и W021: includeSubDomains/preload
преднамеренно не включаются до проверки всех поддоменов. Предупреждения не
подавляются. После проверки HTTPS увеличить HSTS до согласованного значения;
preload требует отдельного решения владельца домена.

## Web-сервер

Waitress закреплён в requirements и работает на Windows/Linux. Запуск:

```text
python -m waitress --listen=127.0.0.1:8000 --threads=8 --trusted-proxy=127.0.0.1 --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" --max-request-body-size=54525952 config.wsgi:application
```

Команда предполагает единственный локальный доверенный proxy. Waitress
устанавливает wsgi.url_scheme и REMOTE_ADDR из перезаписанных proxy-заголовков.
При этом DJANGO_TRUST_PROXY=False достаточно. Если HTTPS распознаётся самим
Django, DJANGO_TRUST_PROXY=True допускается только с закрытым backend-портом и
proxy, который перезаписывает X-Forwarded-Proto. Не задавать trusted_proxy=*.

Пример Nginx — deploy/nginx.conf.example, Linux service — deploy/minobr.service.
Заменить домен/сертификаты/пути, выполнить `nginx -t`, проверить HTTPS и restart.
Для Windows использовать IIS с TLS и reverse proxy к тому же Waitress-порту;
запускать Waitress службой под отдельной учётной записью через утверждённый
service wrapper с автоматическим перезапуском. runserver для эксплуатации не
используется. Выбор IIS/wrapper и выдача сертификата проверяются на сервере.

STATIC_ROOT раздаётся публично. MEDIA_ROOT находится вне web root и доступен
только служебной учётной записи; `/media/` возвращает 404. Проверить скачивание
настоящими пользователями директор А/Б, Комитет и ADMIN, а также анонимно.
Настроить scheduler по docs/scheduler.md. Проверить учёт реальных IP в лимите
входа и запрет прямого подключения к backend из внешней сети.

## Логи и восстановление релиза

Логи приложения идут в stderr и собираются journald/service wrapper.
Доступ ограничен администраторами, ротация и срок хранения задаются на сервере.
Пароли и тела POST не должны записываться proxy или APM. Ошибки приложения,
429 и ошибки scheduler должны попадать в мониторинг. Системный аудит действий
пользователей остаётся этапом 2.

До upgrade сделать согласованную копию БД и media, проверить restore. Развернуть
новый код в отдельном каталоге, применить миграции и smoke tests, переключить
service. При ошибке остановить запись, вернуть предыдущий код. Откат БД
выполняется только по проверенному плану миграций или восстановлением копии;
это теряет записи после копии и требует согласования владельца данных.
Не использовать git reset --hard или destructive SQL для исправления схемы.

Ссылки: [Django deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/),
[Waitress proxy settings](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html).
