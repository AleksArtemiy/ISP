"""
Вспомогательные функции разграничения доступа пользователей.

Модуль содержит централизованные проверки ролей информационной системы.

Исторически в проекте роль пользователя определялась через сравнение
текстового поля Role.name, например:

    'committee' in user.role.name.lower()

Такой подход ненадёжен, поскольку бизнес-логика безопасности начинает
зависеть от человекочитаемого названия роли, регистра и языка интерфейса.

После внедрения Role.code все проверки должны выполняться через
стабильные программные коды:

    ADMIN
    COMMITTEE
    DIRECTOR

Централизация проверок также позволяет реализовать принцип
"deny by default": неизвестная или некорректно настроенная роль
не получает дополнительные права автоматически.
"""

from typing import Optional

from .models import Role


def get_role_code(user) -> Optional[str]:
    """
    Возвращает стабильный программный код роли пользователя.

    Args:
        user:
            Пользователь Django или AnonymousUser.

    Returns:
        str | None:
            Код роли пользователя либо None, если:

            - пользователь отсутствует;
            - пользователь не авторизован;
            - роль пользователю не назначена;
            - программный код роли отсутствует.

    Функция не предоставляет никаких прав при отсутствии роли,
    что соответствует принципу deny by default.
    """

    if user is None:
        return None

    if not getattr(user, "is_authenticated", False):
        return None

    role = getattr(user, "role", None)

    if role is None:
        return None

    return role.code


def has_role(user, *role_codes: str) -> bool:
    """
    Проверяет наличие у пользователя одной из указанных ролей.

    Args:
        user:
            Пользователь Django.

        *role_codes:
            Один или несколько допустимых кодов Role.Code.

    Returns:
        bool:
            True, если код роли пользователя присутствует
            среди разрешённых кодов.
    """

    role_code = get_role_code(user)

    if role_code is None:
        return False

    return role_code in role_codes


def has_admin_role(user) -> bool:
    """
    Проверяет наличие прикладной роли администратора.

    Важно:
        Наличие Role.Code.ADMIN пока не заменяет Django-флаг
        is_superuser для доступа к административной панели.

        Перевод admin-panel на единую модель RBAC будет выполнен
        отдельным безопасным этапом.
    """

    return has_role(
        user,
        Role.Code.ADMIN,
    )


def is_committee(user) -> bool:
    """
    Проверяет, является ли пользователь сотрудником
    Комитета образования.
    """

    return has_role(
        user,
        Role.Code.COMMITTEE,
    )


def is_director(user) -> bool:
    """
    Проверяет, является ли пользователь директором учреждения.

    Наличие роли DIRECTOR само по себе не означает, что пользователь
    имеет доступ к какому-либо учреждению.

    Проверка конкретного institution выполняется отдельно.
    """

    return has_role(
        user,
        Role.Code.DIRECTOR,
    )


def is_django_admin(user) -> bool:
    """
    Проверяет наличие системных прав суперпользователя Django.

    Эта проверка пока используется для существующей административной
    панели, поскольку текущий код admin-panel основан на is_superuser.
    """

    if user is None:
        return False

    if not getattr(user, "is_authenticated", False):
        return False

    return bool(
        getattr(
            user,
            "is_superuser",
            False,
        )
    )


def can_access_all_institutions(user) -> bool:
    """
    Определяет, имеет ли пользователь глобальный доступ
    к данным всех образовательных учреждений.

    Такой доступ предоставляется:

        - Django-superuser;
        - пользователю с ролью COMMITTEE.

    Неизвестные роли и пользователи без роли получают False.
    """

    return (
        is_django_admin(user)
        or is_committee(user)
    )


def has_own_institution(user) -> bool:
    """
    Проверяет корректность привязки директора к учреждению.

    Returns:
        bool:
            True только если:

            - пользователь авторизован;
            - имеет роль DIRECTOR;
            - имеет назначенное учреждение.
    """

    if not is_director(user):
        return False

    return getattr(
        user,
        "institution_id",
        None,
    ) is not None


def can_access_institution(user, institution_id: int) -> bool:
    """
    Проверяет право пользователя на доступ к конкретному учреждению.

    Правила:

        Django-superuser:
            может обращаться к любому учреждению.

        COMMITTEE:
            может обращаться к любому учреждению.

        DIRECTOR:
            может обращаться только к собственному учреждению.

        Остальные:
            доступ запрещён.

    Args:
        user:
            Авторизованный пользователь.

        institution_id:
            Первичный ключ проверяемого учреждения.

    Returns:
        bool:
            True при наличии доступа, иначе False.
    """

    if can_access_all_institutions(user):
        return True

    if not has_own_institution(user):
        return False

    return user.institution_id == institution_id