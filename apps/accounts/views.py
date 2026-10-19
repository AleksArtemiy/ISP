"""
Представления приложения accounts.

Модуль отвечает за:

    - авторизацию пользователя;
    - завершение пользовательской сессии;
    - определение стартовой страницы после входа.

Проверки ролей выполняются через централизованный модуль
apps.accounts.permissions и стабильное поле Role.code.
"""

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
)
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    redirect,
    render,
)
from django.urls import reverse
from django.views.decorators.http import require_POST
from .permissions import can_access_admin_panel
from .throttling import reserve_login_attempt, reset_account_counter

from .permissions import (
    is_committee,
    is_director,
    is_django_admin,
)


def get_redirect_url(user):
    """
    Определяет безопасную стартовую страницу пользователя
    после успешной авторизации.

    Правила:

        Django-superuser:
            административная панель.

        COMMITTEE:
            общий дашборд Комитета образования.

        DIRECTOR:
            дашборд собственного учреждения.

    Returns:
        str | None:
            URL для перенаправления либо None, если учётная запись
            настроена некорректно.

    Принцип безопасности:
        Неизвестная роль или директор без учреждения не получают
        доступ к дашборду Комитета по умолчанию.

        Используется стратегия deny by default.
    """

    if not getattr(user, "is_authenticated", False):
        return None

    if can_access_admin_panel(user):
        return reverse(
            "admin_panel:admin_panel",
        )

    if is_committee(user):
        return reverse(
            "committee_dashboard",
        )

    if is_director(user):
        if user.institution_id is None:
            return None

        return reverse(
            "institution_dashboard",
            kwargs={
                "institution_id": user.institution_id,
            },
        )

    return None


def login_view(request):
    """
    Выполняет авторизацию пользователя по email и паролю.

    Защита от user enumeration:
        При ошибке авторизации система не сообщает,
        существует ли введённый email.

        Для неизвестного email и неправильного пароля
        используется одинаковое сообщение:

            "Неверный email или пароль."

    Также выполняется проверка корректности настройки
    роли пользователя до создания авторизованной сессии.
    """

    # --------------------------------------------------------
    # Уже авторизованный пользователь
    # --------------------------------------------------------

    if request.user.is_authenticated:
        redirect_url = get_redirect_url(
            request.user,
        )

        if redirect_url is not None:
            return redirect(
                redirect_url,
            )

        # Пользователь существует, но его роль/учреждение
        # настроены некорректно.
        #
        # Завершаем сессию, чтобы исключить цикл перенаправлений
        # и случайное предоставление доступа.
        logout(request)

        messages.error(
            request,
            (
                "Учётная запись настроена некорректно. "
                "Обратитесь к администратору системы."
            ),
        )

        return render(
            request,
            "accounts/login.html",
        )

    # --------------------------------------------------------
    # Авторизация
    # --------------------------------------------------------

    if request.method == "POST":
        email = request.POST.get(
            "email",
            "",
        ).strip()

        password = request.POST.get(
            "password",
            "",
        )

        if not email:
            messages.error(
                request,
                "Пожалуйста, введите email.",
            )

            return render(
                request,
                "accounts/login.html",
            )

        if not password:
            messages.error(
                request,
                "Пожалуйста, введите пароль.",
            )

            return render(
                request,
                "accounts/login.html",
            )

        if not reserve_login_attempt(request, email):
            messages.error(request, "Слишком много попыток входа. Повторите через 15 минут.")
            response = render(request, "accounts/login.html", status=429)
            response["Retry-After"] = "900"
            return response

        user = authenticate(
            request,
            username=email,
            password=password,
        )

        # ----------------------------------------------------
        # Неверные учётные данные
        # ----------------------------------------------------

        if user is None:
            # Не различаем:
            #
            # - отсутствующий email;
            # - неправильный пароль;
            # - неактивную учётную запись.
            #
            # Это снижает возможность перечисления пользователей.
            messages.error(
                request,
                "Неверный email или пароль.",
            )

            return render(
                request,
                "accounts/login.html",
            )

        # ----------------------------------------------------
        # Проверка корректности роли
        # ----------------------------------------------------

        redirect_url = get_redirect_url(
            user,
        )

        if redirect_url is None:
            # Сессию ещё не создавали.
            #
            # Пользователь с неизвестной ролью или директор
            # без учреждения не получает доступ автоматически.
            messages.error(
                request,
                (
                    "Учётная запись настроена некорректно. "
                    "Обратитесь к администратору системы."
                ),
            )

            return render(
                request,
                "accounts/login.html",
            )

        # ----------------------------------------------------
        # Успешный вход
        # ----------------------------------------------------

        reset_account_counter(request, email)
        login(
            request,
            user,
        )

        return redirect(
            redirect_url,
        )

    return render(
        request,
        "accounts/login.html",
    )


@login_required
@require_POST
def logout_view(request):
    """
    Завершает пользовательскую сессию и перенаправляет
    пользователя на страницу входа.
    """

    logout(request)

    return redirect(
        "login",
    )
