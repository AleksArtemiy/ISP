from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

class InstitutionType(models.Model):
    """
    Справочник типов учреждений.

    Связан с таблицей 'institution_types' в базе данных.
    Используется для классификации учреждений (школы, сады, лагеря и т.д.).

    Поля:
        id (int): Первичный ключ.
        name (str): Название типа (уникальное).

    Мета-параметры:
        db_table = 'institution_types' — имя таблицы в БД.
        managed = False — Django не управляет созданием/изменением этой таблицы,
                          так как она уже существует.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name='Название типа')

    class Meta:
        db_table = 'institution_types'
        managed = False
        verbose_name = 'Тип учреждения'
        verbose_name_plural = 'Типы учреждений'

    def __str__(self) -> str:
        return self.name


class Institution(models.Model):
    """
    Модель учреждения образования.

    Содержит основную информацию об учебных заведениях.
    Связана с моделью User через внешний ключ (users.institution_id) — это позволяет
    привязывать пользователей (сотрудников) к конкретному учреждению.

    Важные связи:
        - User.institution → ссылается на Institution (on_delete=SET_NULL),
          поэтому при удалении учреждения пользователи не удаляются,
          а поле institution у них становится NULL.
        - Обратная связь: institution.user_set позволяет получить всех сотрудников
          данного учреждения.
        - Institution.institution_type → ссылается на справочник InstitutionType.

    Поля (соответствуют колонкам существующей таблицы 'institutions'):
        id (int): Первичный ключ (автоинкремент).
        name (str): Полное наименование учреждения.
        short_name (str): Краткое название.
        address (str): Физический адрес.
        institution_type (InstitutionType): Тип учреждения (внешний ключ).
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.

    Мета-параметры:
        db_table = 'institutions' — имя таблицы в БД.
        managed = False — Django не управляет структурой этой таблицы,
                          так как она уже существует.
        verbose_name / verbose_name_plural — для админки.

    Методы:
        __str__: возвращает краткое название учреждения.
        employee_count: свойство, возвращающее количество привязанных пользователей.
    """

    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        db_column='name',
        verbose_name='Полное наименование',
        help_text='Официальное полное наименование учреждения'
    )
    short_name = models.CharField(
        max_length=100,
        db_column='short_name',
        verbose_name='Краткое название',
        help_text='Сокращённое название, используемое в списках и отчётах'
    )
    address = models.TextField(
        db_column='address',
        verbose_name='Адрес',
        help_text='Юридический и/или фактический адрес'
    )
    institution_type = models.ForeignKey(
        InstitutionType,
        on_delete=models.PROTECT,
        db_column='institution_type_id',
        verbose_name='Тип учреждения',
        help_text='Ссылка на тип учреждения из справочника'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='created_at',
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column='updated_at',
        verbose_name='Дата обновления'
    )

    class Meta:
        db_table = 'institutions'
        managed = False
        verbose_name = 'Учреждение'
        verbose_name_plural = 'Учреждения'
        ordering = ('short_name',)  # сортировка по умолчанию

    def __str__(self) -> str:
        """Возвращает краткое название учреждения для отображения в интерфейсах."""
        return self.short_name

    @property
    def employee_count(self) -> int:
        """
        Возвращает количество пользователей, привязанных к этому учреждению.
        Используется в шаблонах для отображения числа сотрудников.
        """
        return self.user_set.count()  # обратная связь с моделью User

    @property
    def full_address(self) -> str:
        """Возвращает полный адрес (может быть расширен при необходимости)."""
        return self.address

    # При необходимости можно добавить метод для получения списка сотрудников
    def get_employees(self):
        """Возвращает QuerySet пользователей, относящихся к данному учреждению."""
        return self.user_set.all().select_related('role')

    # Валидация на уровне модели (если потребуется)
    def clean(self) -> None:
        """
        Дополнительная валидация перед сохранением.
        Например, можно проверить, что short_name не пустой.
        """
        if not self.short_name:
            raise ValidationError({'short_name': 'Краткое название обязательно'})

    def save(self, *args, **kwargs) -> None:
        """Переопределённый метод сохранения с вызовом валидации."""
        self.full_clean()
        super().save(*args, **kwargs)