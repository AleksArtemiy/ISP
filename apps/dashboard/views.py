"""
Представления приложения dashboard.

Модуль отвечает за:

    - общий дашборд Комитета образования;
    - дашборд отдельного образовательного учреждения;
    - серверное разграничение доступа к этим представлениям.

Проверки ролей выполняются через централизованный модуль
apps.accounts.permissions и стабильное поле Role.code.

Применяется принцип deny by default:
пользователь с неизвестной ролью или некорректной конфигурацией
не получает расширенные права автоматически.

Важно:
    В этом модуле пока сохраняется существующая бизнес-логика
    расчёта сроков, статистики и финансирования.

    Переход с 14 календарных дней на 10 рабочих дней,
    оптимизация запросов и реализация финансирования
    будут выполнены отдельными этапами.
"""

from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone

from apps.accounts.permissions import (
    can_access_all_institutions,
    can_access_institution,
    has_own_institution,
)
from apps.institutions.models import Institution
from apps.prescriptions.models import Order


def committee_required(view_func):
    """
    Ограничивает доступ к представлению пользователями,
    имеющими право видеть данные всех учреждений.

    Разрешён доступ:

        - Django-superuser;
        - пользователь с ролью COMMITTEE.

    Для директора:
        выполняется перенаправление на дашборд собственного учреждения.

    Для пользователя с неизвестной ролью или некорректной настройкой:
        доступ запрещается.

    Применяется принцип deny by default.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        # Дополнительная защита.
        #
        # Обычно этот декоратор используется совместно
        # с @login_required, однако он не должен полагаться
        # исключительно на внешний декоратор.
        if not user.is_authenticated:
            return redirect("login")

        # Комитет и Django-superuser имеют глобальный доступ.
        if can_access_all_institutions(user):
            return view_func(
                request,
                *args,
                **kwargs,
            )

        # Корректно настроенный директор не должен попадать
        # на общий дашборд Комитета.
        #
        # Вместо ошибки перенаправляем его на собственное учреждение.
        if has_own_institution(user):
            messages.error(
                request,
                "У вас нет доступа к дашборду Комитета образования.",
            )

            return redirect(
                "institution_dashboard",
                institution_id=user.institution_id,
            )

        # Неизвестная роль, директор без учреждения или другая
        # некорректная конфигурация не получают доступ.
        messages.error(
            request,
            "У вас нет доступа к этой странице.",
        )

        raise PermissionDenied(
            "Недостаточно прав для просмотра дашборда Комитета."
        )

    return wrapper


def institution_access_required(view_func):
    """
    Проверяет право доступа к дашборду конкретного учреждения.

    Разрешён доступ:

        Django-superuser:
            к любому учреждению;

        COMMITTEE:
            к любому учреждению;

        DIRECTOR:
            только к учреждению, указанному в user.institution.

    Пользователь с неизвестной ролью, директор без учреждения
    или другой некорректно настроенный пользователь получает отказ.

    Директор при попытке открыть чужое учреждение перенаправляется
    на собственный дашборд.

    Таким образом URL вида:

        /institution/<institution_id>/

    сам по себе не предоставляет доступ к данным учреждения.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return redirect("login")

        institution_id = kwargs.get(
            "institution_id",
        )

        if institution_id is None:
            raise PermissionDenied(
                "Не указано учреждение для проверки доступа."
            )

        # Централизованная объектная проверка доступа.
        if can_access_institution(
            user,
            institution_id,
        ):
            return view_func(
                request,
                *args,
                **kwargs,
            )

        # Корректно настроенного директора возвращаем
        # на страницу собственного учреждения.
        if has_own_institution(user):
            messages.error(
                request,
                "У вас нет доступа к этому учреждению.",
            )

            return redirect(
                "institution_dashboard",
                institution_id=user.institution_id,
            )

        # Неизвестная роль или некорректная конфигурация.
        messages.error(
            request,
            "У вас нет доступа к этому учреждению.",
        )

        raise PermissionDenied(
            "Недостаточно прав для просмотра учреждения."
        )

    return wrapper


@login_required
@committee_required
def committee_dashboard(request):
    """
    Отображает общий дашборд Комитета образования.

    Доступ разрешён только пользователям с глобальным доступом:

        - Django-superuser;
        - COMMITTEE.

    Дашборд содержит:

        - агрегированную статистику по учреждениям;
        - количество предписаний по статусам;
        - информацию о просроченных и приближающихся сроках;
        - общий реестр предписаний.

    Примечание:
        Текущая версия использует существующую бизнес-логику
        с порогом 14 календарных дней.

        Замена на 10 рабочих дней будет выполнена
        отдельным этапом BIZ-01.
    """

    # --------------------------------------------------------
    # Учреждения и агрегированные показатели
    # --------------------------------------------------------

    institutions = (
        Institution.objects
        .annotate(
            total_orders=Count(
                "order",
                distinct=True,
            ),
            completed_orders=Count(
                "order",
                filter=Q(
                    order__status="COMPLETED",
                ),
                distinct=True,
            ),
            overdue_orders=Count(
                "order",
                filter=Q(
                    order__status="OVERDUE",
                ),
                distinct=True,
            ),
            in_progress_orders=Count(
                "order",
                filter=Q(
                    order__status="IN_PROGRESS",
                ),
                distinct=True,
            ),
            new_orders=Count(
                "order",
                filter=Q(
                    order__status="NEW",
                ),
                distinct=True,
            ),
        )
        .select_related(
            "institution_type",
        )
    )

    # --------------------------------------------------------
    # Общая статистика
    # --------------------------------------------------------

    all_orders = Order.objects.all()

    total_prescriptions = all_orders.count()

    overdue_total = all_orders.filter(
        status="OVERDUE",
    ).count()

    completed_total = all_orders.filter(
        status="COMPLETED",
    ).count()

    today = date.today()

    expiring_soon_total = all_orders.filter(
        status__in=[
            "NEW",
            "IN_PROGRESS",
        ],
        deadline_date__gte=today,
        deadline_date__lte=(
            today
            + timedelta(days=14)
        ),
    ).count()

    if total_prescriptions:
        completion_percent = round(
            completed_total
            / total_prescriptions
            * 100
        )
    else:
        completion_percent = 0

    # Новые предписания за последние 30 дней.
    one_month_ago = (
        timezone.now()
        - timedelta(days=30)
    )

    new_this_month = all_orders.filter(
        created_at__gte=one_month_ago,
    ).count()

    # Финансирование будет реализовано отдельным этапом.
    total_funding = 0

    # --------------------------------------------------------
    # Карточки учреждений
    # --------------------------------------------------------

    institutions_data = []

    for inst in institutions:
        if inst.overdue_orders > 0:
            bar_color = "red"
            deadline_status = "overdue"

            overdue_days = 0

            overdue_orders = inst.order_set.filter(
                status="OVERDUE",
            )

            if overdue_orders.exists():
                overdue_days = max(
                    (
                        today
                        - order.deadline_date
                    ).days
                    for order in overdue_orders
                )

            days_left = 0

        elif (
            inst.in_progress_orders > 0
            or inst.new_orders > 0
        ):
            nearest = (
                inst.order_set
                .filter(
                    status__in=[
                        "NEW",
                        "IN_PROGRESS",
                    ],
                )
                .order_by(
                    "deadline_date",
                )
                .first()
            )

            if nearest:
                days_left = (
                    nearest.deadline_date
                    - today
                ).days

                if days_left <= 14:
                    bar_color = "yellow"
                    deadline_status = "expiring"
                    overdue_days = 0

                else:
                    bar_color = "green"
                    deadline_status = "ok"
                    overdue_days = 0

            else:
                bar_color = "pastel-green"
                deadline_status = "ok"
                days_left = 0
                overdue_days = 0

        else:
            bar_color = "pastel-green"
            deadline_status = "ok"
            days_left = 0
            overdue_days = 0

        # ----------------------------------------------------
        # Процент выполнения
        # ----------------------------------------------------

        if inst.total_orders > 0:
            progress_percent = int(
                (
                    inst.completed_orders
                    / inst.total_orders
                )
                * 100
            )

        else:
            progress_percent = 100

        # ----------------------------------------------------
        # Тип учреждения
        # ----------------------------------------------------

        if inst.institution_type:
            type_name = (
                inst.institution_type.name
            )
        else:
            type_name = "—"

        institutions_data.append(
            {
                "id": inst.id,
                "name": inst.name,
                "short_name": inst.short_name,
                "type_name": type_name,
                "total_prescriptions": (
                    inst.total_orders
                ),
                "completed_prescriptions": (
                    inst.completed_orders
                ),
                "overdue_count": (
                    inst.overdue_orders
                ),
                "funding": 0,
                "deadline_status": (
                    deadline_status
                ),
                "days_left": days_left,
                "overdue_days": overdue_days,
                "progress_percent": (
                    progress_percent
                ),
                "bar_color": bar_color,
            }
        )

    # --------------------------------------------------------
    # Общий реестр предписаний
    # --------------------------------------------------------

    prescriptions = (
        Order.objects
        .select_related(
            "institution",
            "authority",
            "created_by_user",
        )
        .prefetch_related(
            "order_violations__violation",
        )
        .order_by(
            "-created_at",
        )
    )

    prescriptions_data = []

    for order in prescriptions:
        if order.status == "COMPLETED":
            status_class = "green"
            progress = 100
            status_text = "Выполнено"

        elif order.status == "OVERDUE":
            status_class = "red"
            progress = 0

            days = (
                today
                - order.deadline_date
            ).days

            status_text = (
                f"Просрочено на {days} дн."
            )

        elif order.status == "EXPIRING":
            status_class = "yellow"
            progress = 50

            days_left = (
                order.deadline_date
                - today
            ).days

            status_text = (
                f"Истекает через {days_left} дн."
            )

        else:
            # NEW или IN_PROGRESS.
            days_left = (
                order.deadline_date
                - today
            ).days

            if days_left < 0:
                status_class = "red"
                progress = 0

                status_text = (
                    "Просрочено на "
                    f"{-days_left} дн."
                )

            elif days_left <= 14:
                status_class = "yellow"
                progress = 50

                status_text = (
                    "До окончания: "
                    f"{days_left} дн."
                )

            else:
                status_class = "green"
                progress = 75

                status_text = (
                    "До окончания: "
                    f"{days_left} дн."
                )

        violations = [
            order_violation.violation.description
            for order_violation
            in order.order_violations.all()
        ]

        if order.authority:
            authority_name = (
                order.authority.name
            )
        else:
            authority_name = "—"

        if order.created_by_user:
            responsible = (
                order.created_by_user
                .get_full_name()
            )
        else:
            responsible = "—"

        prescriptions_data.append(
            {
                "id": order.id,
                "number": order.number,
                "institution_id": (
                    order.institution.id
                ),
                "institution_name": (
                    order.institution.short_name
                ),
                "authority": authority_name,
                "due_date": order.deadline_date,
                "progress_percent": progress,
                "status_class": status_class,
                "status_text": status_text,
                "responsible": responsible,
                "violations": violations,
            }
        )

    context = {
        "institutions": institutions_data,
        "prescriptions": prescriptions_data,
        "total_prescriptions": (
            total_prescriptions
        ),
        "overdue_total": overdue_total,
        "expiring_soon_total": (
            expiring_soon_total
        ),
        "completed_total": completed_total,
        "completion_percent": (
            completion_percent
        ),
        "total_funding": total_funding,
        "new_this_month": new_this_month,
        "user_role": (
            "Комитет образования"
        ),
    }

    return render(
        request,
        "committee_dashboard.html",
        context,
    )


@login_required
@institution_access_required
def institution_dashboard(
    request,
    institution_id,
):
    """
    Отображает дашборд конкретного образовательного учреждения.

    Доступ разрешён:

        - Django-superuser;
        - COMMITTEE;
        - DIRECTOR своего учреждения.

    DIRECTOR не может получить данные чужого учреждения
    простой заменой institution_id в URL.
    """

    institution = get_object_or_404(
        Institution,
        pk=institution_id,
    )

    orders = (
        Order.objects
        .filter(
            institution=institution,
        )
        .select_related(
            "authority",
            "created_by_user",
        )
        .prefetch_related(
            "order_violations__violation",
        )
        .order_by(
            "-created_at",
        )
    )

    completed_count = orders.filter(
        status="COMPLETED",
    ).count()

    overdue_count = orders.filter(
        status="OVERDUE",
    ).count()

    today = date.today()

    expiring_soon_total = orders.filter(
        status__in=[
            "NEW",
            "IN_PROGRESS",
        ],
        deadline_date__gte=today,
        deadline_date__lte=(
            today
            + timedelta(days=14)
        ),
    ).count()

    prescriptions_data = []

    for order in orders:
        violations = [
            order_violation.violation.description
            for order_violation
            in order.order_violations.all()
        ]

        if order.status == "COMPLETED":
            status = "completed"
            progress = 100
            status_text = "Выполнено"

        elif order.status == "OVERDUE":
            status = "overdue"
            progress = 0

            days = (
                today
                - order.deadline_date
            ).days

            status_text = (
                f"Просрочено на {days} дн."
            )

        elif order.status == "EXPIRING":
            status = "expiring"
            progress = 50

            days_left = (
                order.deadline_date
                - today
            ).days

            status_text = (
                f"Истекает через {days_left} дн."
            )

        else:
            # NEW или IN_PROGRESS.
            days_left = (
                order.deadline_date
                - today
            ).days

            if days_left < 0:
                status = "overdue"
                progress = 0

                status_text = (
                    "Просрочено на "
                    f"{-days_left} дн."
                )

            elif days_left <= 14:
                status = "expiring"
                progress = 50

                status_text = (
                    "Истекает через "
                    f"{days_left} дн."
                )

            else:
                status = "in_progress"
                progress = 75

                status_text = (
                    "До окончания: "
                    f"{days_left} дн."
                )

        if order.authority:
            authority_name = (
                order.authority.name
            )
        else:
            authority_name = "—"

        if order.created_by_user:
            responsible = (
                order.created_by_user
                .get_full_name()
            )
        else:
            responsible = "—"

        prescriptions_data.append(
            {
                "id": order.id,
                "number": order.number,
                "authority": authority_name,
                "due_date": order.deadline_date,
                "status": status,
                "progress_percent": progress,
                "status_text": status_text,
                "responsible": responsible,
                "violations": violations,
            }
        )

    # Финансирование будет подключено отдельным этапом.
    funding = getattr(
        institution,
        "funding",
        0,
    )

    context = {
        "institution": {
            "id": institution.id,
            "name": institution.name,
            "short_name": (
                institution.short_name
            ),
            "address": institution.address,
            "funding": funding,
        },
        "prescriptions": prescriptions_data,
        "completed_count": completed_count,
        "overdue_count": overdue_count,
        "expiring_soon_total": (
            expiring_soon_total
        ),
        "funding_requests": [],
    }

    return render(
        request,
        "institution_dashboard.html",
        context,
    )


def logout_view(request):
    """
    Устаревшая вспомогательная функция выхода.

    Основной маршрут logout проекта использует
    apps.accounts.views.logout_view.

    Функция временно сохраняется для обратной совместимости
    и будет удалена при последующей очистке технического долга.
    """

    from django.contrib.auth import logout

    logout(request)

    return redirect(
        "login",
    )