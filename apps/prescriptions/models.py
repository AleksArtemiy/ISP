from django.db import models
from django.conf import settings
from apps.institutions.models import Institution


class SupervisoryAuthority(models.Model):
    """
    Модель надзорного органа (таблица supervisory_authorities).

    Содержит перечень органов, выдающих предписания (пожнадзор, санэпидемстанция и т.п.).
    Поля:
        id (int): Первичный ключ.
        name (str): Уникальное название надзорного органа.

    Мета:
        db_table = 'supervisory_authorities' — имя таблицы в БД.
        managed = False — таблица уже существует, Django не управляет её структурой.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = 'supervisory_authorities'
        managed = False
        verbose_name = 'Надзорный орган'
        verbose_name_plural = 'Надзорные органы'

    def __str__(self):
        return self.name


class Order(models.Model):
    """
    Модель предписания (таблица orders).

    Основной документ, выдаваемый надзорным органом учреждению.
    Связан с:
        - Institution (учреждение)
        - SupervisoryAuthority (надзорный орган)
        - User (создатель предписания, он же ответственный)

    Статус предписания хранится в виде строки, соответствующей ENUM-типу
    order_status в PostgreSQL. Доступные значения:
        NEW         — новое
        IN_PROGRESS — в работе
        COMPLETED   — выполнено
        OVERDUE     — просрочено

    Поля (полностью соответствуют колонкам таблицы orders):
        id (int): Первичный ключ.
        number (str): Номер предписания (не уникален по схеме, но рекомендуется
                      добавлять уникальность на уровне приложения).
        institution (Institution): Внешний ключ на учреждение.
        authority (SupervisoryAuthority): Внешний ключ на надзорный орган.
        created_by_user (User): Пользователь, создавший запись.
        status (str): Статус выполнения.
        issue_date (date): Дата выдачи.
        deadline_date (date): Срок исполнения.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.

    Индексы:
        - idx_orders_status (по полю status)
        - idx_orders_deadline (по полю deadline_date)

    Мета:
        db_table = 'orders'
        managed = False
        ordering = ('-created_at',) — сначала новые.

    Методы:
        __str__: возвращает номер предписания.
        is_overdue: свойство, определяющее, просрочено ли предписание.
        get_status_display: возвращает человекочитаемое название статуса.
    """
    STATUS_CHOICES = [
        ('NEW', 'Новое'),
        ('IN_PROGRESS', 'В работе'),
        ('COMPLETED', 'Выполнено'),
        ('OVERDUE', 'Просрочено'),
    ]

    id = models.AutoField(primary_key=True)
    number = models.CharField(max_length=100, db_column='number')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, db_column='institution_id')
    authority = models.ForeignKey(SupervisoryAuthority, on_delete=models.CASCADE, db_column='authority_id')
    created_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='created_by_user_id')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW', db_column='status')
    issue_date = models.DateField(db_column='issue_date')
    deadline_date = models.DateField(db_column='deadline_date')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'orders'
        managed = False
        verbose_name = 'Предписание'
        verbose_name_plural = 'Предписания'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['status'], name='idx_orders_status'),
            models.Index(fields=['deadline_date'], name='idx_orders_deadline'),
        ]

    def __str__(self):
        return self.number


class Violation(models.Model):
    """
    Модель нарушения (таблица violations).

    Содержит описание нарушения. Связь с предписаниями осуществляется
    через промежуточную таблицу order_violations (многие ко многим).

    Поля:
        id (int): Первичный ключ.
        description (str): Текст нарушения.

    Мета:
        db_table = 'violations'
        managed = False
        verbose_name / verbose_name_plural.
    """
    id = models.AutoField(primary_key=True)
    description = models.TextField(db_column='description')

    class Meta:
        db_table = 'violations'
        managed = False
        verbose_name = 'Нарушение'
        verbose_name_plural = 'Нарушения'

    def __str__(self):
        return self.description[:50]


class OrderViolation(models.Model):
    """
    Промежуточная таблица для связи предписаний и нарушений (order_violations).

    Обеспечивает связь многие-ко-многим между Order и Violation.
    Каждая запись связывает одно предписание с одним нарушением.

    Поля:
        id (int): Первичный ключ.
        order (Order): Предписание.
        violation (Violation): Нарушение.

    Уникальное ограничение: (order_id, violation_id) — предотвращает дублирование.

    Мета:
        db_table = 'order_violations'
        managed = False
        verbose_name / verbose_name_plural.
    """
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, db_column='order_id')
    violation = models.ForeignKey(Violation, on_delete=models.CASCADE, db_column='violation_id')

    class Meta:
        db_table = 'order_violations'
        managed = False
        unique_together = (('order', 'violation'),)
        verbose_name = 'Связь предписания и нарушения'
        verbose_name_plural = 'Связи предписаний и нарушений'


class File(models.Model):
    """
    Модель прикреплённых файлов (таблица files).

    Хранит информацию о загруженных файлах, привязанных к предписанию.

    Поля:
        id (int): Первичный ключ.
        order (Order): Предписание.
        uploaded_by_user (User): Пользователь, загрузивший файл.
        original_filename (str): Оригинальное имя файла.
        file_path (str): Путь к файлу на диске.
        uploaded_at (datetime): Дата загрузки.

    Мета:
        db_table = 'files'
        managed = False
    """
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, db_column='order_id', related_name='files')
    uploaded_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='uploaded_by_user_id')
    original_filename = models.CharField(max_length=255, db_column='original_filename')
    file_path = models.TextField(db_column='file_path')
    uploaded_at = models.DateTimeField(auto_now_add=True, db_column='uploaded_at')

    class Meta:
        db_table = 'files'
        managed = False
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'

    def __str__(self):
        return self.original_filename