"""
Context processors приложения accounts.

Модуль добавляет информацию о текущей роли пользователя
в контекст Django Templates.
"""

from .permissions import (
    has_admin_role,
    is_committee,
    is_director,
)


def user_role(request):
    """
    Добавляет в контекст переменную user_role для отображения
    роли текущего пользователя в интерфейсе.

    Роль определяется по стабильному полю Role.code,
    а не по человекочитаемому Role.name.

    Значения:

        Администратор
            Django-superuser или пользователь с ролью ADMIN.

        Комитет образования
            Пользователь с ролью COMMITTEE.

        Директор
            Пользователь с ролью DIRECTOR.

        Пользователь
            Авторизованный пользователь с неизвестной
            или некорректно настроенной ролью.

        None
            Неавторизованный пользователь.

    Важно:
        Эта функция отвечает только за отображение роли.

        Наличие определённого значения user_role в шаблоне
        не является механизмом авторизации. Все проверки доступа
        должны выполняться на сервере.
    """

    if not request.user.is_authenticated:
        return {
            "user_role": None,
        }

    if request.user.is_superuser or has_admin_role(request.user):
        role = "Администратор"

    elif is_committee(request.user):
        role = "Комитет образования"

    elif is_director(request.user):
        role = "Директор"

    else:
        role = "Пользователь"

    return {
        "user_role": role,
    }