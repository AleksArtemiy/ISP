# Регулярное обновление статусов

`python manage.py update_order_statuses` запускается ежедневно в 00:05 по
Europe/Moscow и после изменения календаря или массовой корректировки сроков.
Команда атомарная и идемпотентная; COMPLETED не изменяется. Повторный запуск
без новых изменений выводит «Изменено: 0». Дашборды используют те же правила
при отображении, поэтому не зависят от вчерашнего сохранённого статуса.

Рабочие дни: понедельник–пятница, без праздников. Считается интервал
(сегодня, дедлайн], сегодня не включается. Предупреждение появляется при
0–10 рабочих днях, просрочка — только после даты дедлайна. Выходной дедлайн
не переносится. WORKDAY_CALENDAR позволяет подключить функцию day→bool для
производственного календаря без изменения представлений и команды.

## Linux systemd

`/etc/systemd/system/minobr-status.service`:

```ini
[Unit]
Description=Minobr prescription status update
After=network.target postgresql.service
[Service]
Type=oneshot
User=minobr
WorkingDirectory=/srv/minobr/current
EnvironmentFile=/etc/minobr/production.env
ExecStart=/srv/minobr/venv/bin/python manage.py update_order_statuses
```

`/etc/systemd/system/minobr-status.timer`:

```ini
[Unit]
Description=Daily Minobr status update
[Timer]
OnCalendar=*-*-* 00:05:00 Europe/Moscow
Persistent=true
[Install]
WantedBy=timers.target
```

Активировать `systemctl enable --now minobr-status.timer`; проверить
`systemctl list-timers`, `systemctl start minobr-status.service` и
`journalctl -u minobr-status.service`. Мониторинг должен сообщать об ошибке
или отсутствии успешного запуска более 26 часов.

## Windows Task Scheduler

Создать ежедневную задачу на 00:05 по московскому времени, запуск независимо
от входа пользователя, отдельная служебная учётная запись без прав
администратора. Program: абсолютный путь `venv\Scripts\python.exe`.
Arguments: `manage.py update_order_statuses`. Start in: каталог проекта.
Переменные production должны быть настроены для этой учётной записи.
Включить запуск пропущенной задачи и повтор при ошибке через пять минут.
Запустить вручную, проверить код 0, History и лог. Эти действия выполняются
на целевом сервере; наличие данного примера не подтверждает работу scheduler.

## Очистка счётчиков входа

Запускать `python manage.py cleanup_login_counters` каждые пять минут под той
же служебной учётной записью и с production-окружением. Команда удаляет только
LoginThrottle с истёкшим 15-минутным окном пакетами до 500 строк, пропускает
занятые строки и выводит количество удалённых записей. Рабочие предметные
таблицы не затрагиваются. Вход также выполняет один пакет очистки, но это
не заменяет scheduler при отсутствии запросов. Проверять ошибки команды
и отсутствие успешного выполнения более 15 минут.

Linux: создать minobr-login-cleanup.service по примеру minobr-status.service
с `ExecStart=/srv/minobr/venv/bin/python manage.py cleanup_login_counters`.
Таймер minobr-login-cleanup.timer:

```ini
[Unit]
Description=Expire Minobr login counters
[Timer]
OnCalendar=*-*-* *:0/5:00
Persistent=true
[Install]
WantedBy=timers.target
```

Активировать `systemctl enable --now minobr-login-cleanup.timer`; проверить
ручной запуск service, journal и list-timers. Windows: отдельная задача с
Arguments `manage.py cleanup_login_counters`, повтор каждые пять минут без
ограничения длительности; остальные параметры аналогичны задаче статусов.
