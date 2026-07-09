from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class UserManager(BaseUserManager):
    """
    Менеджер для кастомной модели пользователя.

    Обеспечивает создание обычных и суперпользователей с использованием email
    в качестве уникального идентификатора вместо username.
    """
    def create_user(self, email, password=None, **extra_fields) -> 'User':
        """
        Создаёт и сохраняет обычного пользователя.

        Args:
            email: Email пользователя (обязательное поле).
            password: Пароль пользователя (может быть None для неактивных).
            **extra_fields: Дополнительные поля модели (first_name, last_name и т.д.).

        Returns:
            User: Созданный объект пользователя.

        Raises:
            ValueError: Если email не передан.
        """
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields) -> 'User':
        """
        Создаёт суперпользователя с правами администратора.

        Устанавливает флаги is_staff и is_superuser в True.

        Args:
            email: Email суперпользователя.
            password: Пароль.
            **extra_fields: Дополнительные поля.

        Returns:
            User: Созданный объект суперпользователя.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """
    Кастомная модель пользователя, связанная с таблицей 'users'.

    Использует email в качестве логина вместо username. Поля соответствуют
    структуре существующей таблицы, поэтому управление таблицей отключено
    (managed = False).

    Атрибуты:
        last_name (str): Фамилия (обязательное).
        first_name (str): Имя (обязательное).
        patronymic (str): Отчество (опционально).
        email (str): Уникальный email (логин).
        phone (str): Номер телефона (опционально).
        password (str): Хэш пароля (поле в БД – password_hash).
        role (Role): Ссылка на роль пользователя.
        institution (Institution): Ссылка на учреждение (опционально).
        created_at (datetime): Дата создания.
        updated_at (datetime): Дата последнего обновления.
        is_staff (bool): Доступ к административной панели.
        is_active (bool): Активность учётной записи.
    """

    # Поля из таблицы users
    last_name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255)
    patronymic = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True, blank=False, null=False)  # сделаем обязательным
    phone = models.CharField(max_length=30, blank=True, null=True)
    password = models.CharField(max_length=255, db_column='password_hash')  # используем существующее поле
    role = models.ForeignKey('roles.Role', on_delete=models.PROTECT, null=True, blank=True)
    institution = models.ForeignKey('institutions.Institution', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Поля, необходимые Django
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Менеджер
    objects = UserManager()

    USERNAME_FIELD = 'email'   # логин по email
    REQUIRED_FIELDS = ['last_name', 'first_name']

    class Meta:
        db_table = 'users' # имя существубщей таблицы
        managed = False # не создавать и не изменять таблицу
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self) -> str:
        """Возвращает строковое представление пользователя."""
        return self.email or f"{self.last_name} {self.first_name}"

    def get_full_name(self) -> str:
        """Возвращает полное имя пользователя (Фамилия Имя Отчество)."""
        return f"{self.last_name} {self.first_name} {self.patronymic or ''}".strip()

    def get_short_name(self) -> str:
        """Возвращает имя пользователя (для краткого отображения)."""
        return self.first_name