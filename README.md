# ИС Реестр предписаний

Django/PostgreSQL-приложение для учёта предписаний надзорных органов
образовательных учреждений Новгородского муниципального округа.

Этап 1 включает авторизацию, пользователей и справочники, реестр, нарушения,
приватные вложения, создание/редактирование/завершение с отчётом, дашборды,
поиск и фильтры, контроль сроков и прикладную административную панель.
Готовность конкретного сервера подтверждается по [ПМИ](docs/acceptance-stage1.md),
а фактические результаты приведены в [протоколе](docs/release-verification.md).

## Запуск с нуля

Проверенный набор: Python 3.14.2, Django 6.0.9, PostgreSQL 18. Зависимости
закреплены в requirements.txt. Активная БД — PostgreSQL; SQLite не используется.

```text
git clone https://github.com/AleksArtemiy/ISP.git
cd ISP
python -m venv .venv
```

Активировать `.venv\Scripts\Activate.ps1` в Windows или `source .venv/bin/activate`
в Linux, затем:

```text
python -m pip install -r requirements.txt
```

Администратор PostgreSQL создаёт отдельную БД и роль приложения по
[deploy/database.sql](deploy/database.sql), затем назначает пароль через
`\password minobr_app` в psql. Роль не получает superuser/CREATEDB/CREATEROLE.

Для разработки скопировать `.env.example` в `.env` и задать свои значения:
DJANGO_SECRET_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.
`.env` и пользовательские media не коммитятся. Пароль в примере — placeholder.
Для production использовать защищённые переменные ОС/secret store и
[руководство развёртывания](docs/deployment.md).

```text
python manage.py migrate --noinput
python manage.py check
python manage.py createsuperuser
python manage.py runserver
```

Открыть http://127.0.0.1:8000/login/. Системный администратор создаёт учреждения,
директоров и сотрудников через `/admin-panel/`. Таблицы и системные роли
ADMIN/COMMITTEE/DIRECTOR создаются миграциями; ручной импорт предметной схемы
на новой БД не нужен. Все предметные модели этапа 1 управляются Django.
Повторный `migrate` безопасен.

Для уже существующей БД сначала изучить [расхождения снимка](docs/existing-schema.md)
и [политику миграций](docs/migration-policy.md), проверить копию и выполнить
`python manage.py schema_preflight`. Не подменять рабочую схему SQL-дампом и не
использовать --fake без проверки истории и фактической структуры.

## Доступ

| Пользователь | Область доступа |
|---|---|
| ADMIN | Прикладная админ-панель и данные всех учреждений |
| COMMITTEE | Дашборд Комитета и предписания всех учреждений |
| DIRECTOR | Только назначенное учреждение и его предписания/файлы |
| Неизвестная роль или директор без учреждения | Отказ |
| Django-superuser | Отдельный системный уровень с прикладным доступом |

ADMIN не назначает is_staff/is_superuser и не открывает `/admin/`.
Прикладной администратор не может сбрасывать пароль или отключать системных
пользователей. Подробности — [политика доступа](docs/access-policy.md).
Проверки выполняются сервером по Role.code, а не по отображаемому имени роли.

## Маршруты и данные

| URL | Назначение |
|---|---|
| `/login/` | Вход по email, одинаковая ошибка неверных credentials |
| `/logout/` | Выход только POST с CSRF |
| `/` и `/dashboard/` | Дашборд Комитета |
| `/institution/<id>/` | Дашборд разрешённого учреждения |
| `/prescriptions/` | Реестр с пагинацией по 20 записей |
| `/prescriptions/create/` | Создание с системным автором и статусом NEW |
| `/prescriptions/<id>/` | Карточка |
| `/prescriptions/update/<id>/` | Редактирование с неизменяемым автором |
| `/prescriptions/complete/<id>/` | Завершение с обязательным отчётом |
| `/prescriptions/files/<id>/download/` | Скачивание с объектной проверкой доступа |
| `/admin-panel/` | Прикладное управление пользователями и справочниками |
| `/admin/` | Стандартная Django Admin |

Фильтры: номер (`q`), статус, учреждение, надзорный орган (`authority`), даты
выдачи `issue_from/issue_to`, сроки `deadline_from/deadline_to`. Фильтры
комбинируются и сохраняются в пагинации; неправильный ввод не расширяет доступ.

Статусы: NEW, IN_PROGRESS, EXPIRING, OVERDUE, COMPLETED. Предупреждение — за
10 рабочих дней, понедельник–пятница без праздников. Правила и подключение
будущего производственного календаря — [scheduler](docs/scheduler.md).

```text
python manage.py update_order_statuses
```

В production команда должна ежедневно выполняться внешним планировщиком.
Дашборды используют ту же функцию сроков. Завершённые записи не переводятся
в активные статусы автоматически.

Вложения: до пяти за операцию, до 10 МиБ каждый, PDF/DOC/DOCX/XLS/XLSX/JPEG/PNG.
Проверяются сигнатура и структура, а не клиентский MIME. Макросы, шифрование
и известные активные конструкции отклоняются. `/media/` публично не раздаётся,
включая DEBUG. [Политика файлов](docs/private-files.md) описывает ограничения.
Связанные исторические сущности защищены от удаления; действие над
пользователем в прикладной панели деактивирует его с сохранением записей.

## Тесты и проверки

Тесты работают на отдельной PostgreSQL. config.test_settings отключает чтение
локального .env. Параметры тестового сервера задаются через TEST_DB_HOST,
TEST_DB_PORT, TEST_DB_USER, TEST_DB_PASSWORD, TEST_DB_NAME. По умолчанию это
127.0.0.1:55432, stage1_test, minobr_stage1_audit. Тестовый пользователь должен
иметь право создавать только тестовые БД в изолированном кластере.

```text
python manage.py migrate --noinput --settings=config.test_settings
python manage.py check --settings=config.test_settings
python manage.py makemigrations --check --dry-run --settings=config.test_settings
python manage.py test --noinput --settings=config.test_settings
python scripts/check_production.py
```

81 тест проверяет миграции, роли, вход/выход, пароли, права объектов, подмену
POST, завершение, rollback, файлы, редиректы, исторические связи, сроки,
фильтры, пагинацию и число SQL-запросов. Отдельно проверяются 40 пользователей
за NAT, TTL/конкуренция счётчиков и read-only бизнес-модели Django Admin.
CI — `.github/workflows/stage1.yml`.

Дополнительный drill создаёт уникальные синтетические БД, применяет миграции
с нуля, запускает тесты, smoke, pg_dump/pg_restore и сравнивает файл:

```text
python scripts/verify_stage1.py --pg-bin "C:\Program Files\PostgreSQL\18\bin"
```

На Linux, если pg_dump/pg_restore находятся в PATH, параметр --pg-bin не нужен.
Базы stage1_clean_* и stage1_restore_* сохраняются для анализа; имена и
протоколы пишутся в игнорируемый `.stage1/`. Для локальной нагрузки указать
TEST_DB_NAME равным созданной stage1_clean_* и запустить
`python scripts/load_stage1.py`. Скрипт создаёт 30 тестовых пользователей,
22 учреждения/110 предписаний и выполняет HTTP-запросы через Waitress.
Результат локального прогона не заменяет испытания целевого сервера.

## Эксплуатация и последующие этапы

Для эксплуатации обязательны [production deployment](docs/deployment.md),
[scheduler](docs/scheduler.md), [backup/restore runbook](docs/backup-restore.md)
и [актуальная ПМИ](docs/acceptance-stage1.md). Основная БД и приватные файлы
копируются ежедневно с хранением не менее 30 дней и проверкой восстановления.
Кроме ежедневного обновления статусов, каждые пять минут запускать
`python manage.py cleanup_login_counters` для удаления истёкших счётчиков входа.
Параметры throttle и Nginx описаны в [политике доступа](docs/access-policy.md).

Этап 2: системный аудит, финансирование, email-уведомления, прикладной backup.
Этап 3: OCR. Суммы финансирования и уведомления в текущем интерфейсе не
означают наличие этих подсистем. Полное ТЗ не фиксирует детальное разделение
модулей по этапам: для приёмки нужен согласованный объём этапа 1.
