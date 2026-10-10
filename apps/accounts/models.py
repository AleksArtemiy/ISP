from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

from apps.institutions.models import Institution


class Role(models.Model):
    """
    Модель роли, связанная с таблицей 'roles' в БД.

    Роль определяет набор прав пользователя в информационной системе.

    Поле `name` используется как человекочитаемое название роли.
    Исторически проверки доступа в проекте также выполнялись через `name`,
    однако это создаёт зависимость логики безопасности от текста названия.

    Для устойчивого разграничения доступа вводится поле `code`.
    В дальнейшем именно `code` будет использоваться в проверках прав,
    а `name` останется отображаемым названием роли.

    Атрибуты:
        id (int):
            Первичный ключ.

        name (str):
            Название роли, отображаемое пользователю.

        code (str | None):
            Стабильный программный код роли.

            Предусмотренные значения:
                ADMIN      — администратор системы;
                COMMITTEE  — сотрудник Комитета образования;
                DIRECTOR   — директор образовательного учреждения.

            На первом этапе миграции поле допускает NULL, чтобы безопасно
            добавить его в существующую таблицу и заполнить значения
            отдельной миграцией без нарушения работы системы.
    """

    class Code(models.TextChoices):
        """
        Стабильные программные коды ролей.

        Значения перечисления не должны зависеть от языка интерфейса
        или человекочитаемого названия роли.
        """

        ADMIN = "ADMIN", "Администратор"
        COMMITTEE = "COMMITTEE", "Комитет образования"
        DIRECTOR = "DIRECTOR", "Директор учреждения"

    id = models.AutoField(primary_key=True)

    name = models.CharField(
        max_length=100,
    )

    code = models.CharField(
        max_length=50,
        choices=Code.choices,
        null=True,
        blank=True,
        db_column="code",
    )

    class Meta:
        db_table = "roles"
        managed = False
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

    def __str__(self) -> str:
        """
        Возвращает человекочитаемое название роли.
        """
        return self.name


class UserManager(BaseUserManager):
    """
    Менеджер для кастомной модели пользователя.

    Обеспечивает создание обычных и суперпользователей с использованием
    email в качестве уникального идентификатора вместо username.
    """

    def create_user(self, email, password=None, **extra_fields) -> "User":
        """
        Создаёт и сохраняет обычного пользователя.

        Args:
            email:
                Email пользователя. Обязательное поле.

            password:
                Пароль пользователя. Может быть None для неактивных
                или специально создаваемых учётных записей.

            **extra_fields:
                Дополнительные поля модели, например first_name,
                last_name, role и institution.

        Returns:
            User:
                Созданный объект пользователя.

        Raises:
            ValueError:
                Если email не передан.
        """
        if not email:
            raise ValueError("Email обязателен")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        email,
        password=None,
        **extra_fields,
    ) -> "User":
        """
        Создаёт суперпользователя с правами администратора.

        Устанавливает флаги is_staff и is_superuser в True.

        Args:
            email:
                Email суперпользователя.

            password:
                Пароль суперпользователя.

            **extra_fields:
                Дополнительные поля пользователя.

        Returns:
            User:
                Созданный объект суперпользователя.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(
            email,
            password,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    """
    Кастомная модель пользователя, связанная с таблицей 'users'.

    Использует email в качестве логина вместо username.

    Пользователь может быть связан с ролью и образовательным учреждением.
    Для директора поле institution определяет учреждение, к данным которого
    пользователь должен иметь доступ.

    Поля соответствуют структуре существующей таблицы пользователей.

    Атрибуты:
        last_name (str):
            Фамилия пользователя.

        first_name (str):
            Имя пользователя.

        patronymic (str | None):
            Отчество пользователя.

        email (str):
            Уникальный email пользователя. Используется в качестве логина.

        phone (str | None):
            Контактный телефон.

        password (str):
            Хэш пароля. В базе данных хранится в колонке password_hash.

        role (Role | None):
            Роль пользователя.

        institution (Institution | None):
            Учреждение пользователя.

        created_at (datetime):
            Дата создания учётной записи.

        updated_at (datetime):
            Дата последнего изменения учётной записи.

        is_staff (bool):
            Флаг доступа к стандартной административной панели Django.

        is_active (bool):
            Признак активной учётной записи.

        last_login (datetime | None):
            Дата и время последней успешной авторизации.

        is_superuser (bool):
            Флаг суперпользователя Django.
    """

    # --------------------------------------------------------
    # Основные пользовательские данные
    # --------------------------------------------------------

    last_name = models.CharField(
        max_length=255,
    )

    first_name = models.CharField(
        max_length=255,
    )

    patronymic = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    email = models.EmailField(
        unique=True,
        blank=False,
        null=False,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    # В существующей таблице БД поле называется password_hash.
    # Django при этом продолжает использовать стандартный механизм
    # хеширования и проверки паролей AbstractBaseUser.
    password = models.CharField(
        max_length=255,
        db_column="password_hash",
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=None,
    )

    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # --------------------------------------------------------
    # Поля, необходимые Django authentication
    # --------------------------------------------------------

    is_staff = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    last_login = models.DateTimeField(
        blank=True,
        null=True,
    )

    is_superuser = models.BooleanField(
        default=False,
    )

    # --------------------------------------------------------
    # Manager / authentication settings
    # --------------------------------------------------------

    objects = UserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = [
        "last_name",
        "first_name",
    ]

    class Meta:
        db_table = "users"
        managed = True
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        """
        Возвращает строковое представление пользователя.

        В качестве основного представления используется email.
        Если email отсутствует, используется фамилия и имя.
        """
        return self.email or f"{self.last_name} {self.first_name}"

    def get_full_name(self) -> str:
        """
        Возвращает полное имя пользователя.

        Формат:
            Фамилия Имя Отчество

        Отчество не добавляется, если оно отсутствует.
        """
        return (
            f"{self.last_name} "
            f"{self.first_name} "
            f"{self.patronymic or ''}"
        ).strip()

    def get_short_name(self) -> str:
        """
        Возвращает краткое имя пользователя.
        """
        return self.first_name