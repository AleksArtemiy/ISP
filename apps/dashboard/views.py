from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum, Case, When, IntegerField
from django.utils import timezone
from datetime import date, timedelta

from apps.institutions.models import Institution
from apps.prescriptions.models import Order, Violation, OrderViolation
from apps.accounts.models import User


def committee_required(view_func):
    """Декоратор: доступ только для пользователей с ролью 'Комитет' или суперпользователей."""
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if request.user.role and 'committee' in request.user.role.name.lower():
            return view_func(request, *args, **kwargs)
        if request.user.is_authenticated:
            if request.user.institution:
                messages.error(request, 'У вас нет доступа к дашборду комитета.')
                return redirect('institution_dashboard', institution_id=request.user.institution.id)
            else:
                messages.error(request, 'У вас нет доступа к этой странице.')
                raise PermissionDenied
        return redirect('login')
    return wrapper


def institution_access_required(view_func):
    """Декоратор: доступ к учреждению только для суперпользователя, комитета или владельца."""
    def wrapper(request, *args, **kwargs):
        institution_id = kwargs.get('institution_id')
        if not institution_id:
            return redirect('committee_dashboard')
        
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if request.user.role and 'committee' in request.user.role.name.lower():
            return view_func(request, *args, **kwargs)
        
        if request.user.institution and request.user.institution.id == institution_id:
            return view_func(request, *args, **kwargs)
        
        if request.user.is_authenticated:
            messages.error(request, 'У вас нет доступа к этому учреждению.')
            if request.user.institution:
                return redirect('institution_dashboard', institution_id=request.user.institution.id)
            else:
                raise PermissionDenied
        return redirect('login')
    return wrapper


@login_required
@committee_required
def committee_dashboard(request):
    """Дашборд комитета – общая статистика по всем учреждениям."""
    
    # Получаем все учреждения с аннотациями по предписаниям
    institutions = Institution.objects.annotate(
        total_orders=Count('order', distinct=True),
        completed_orders=Count('order', filter=Q(order__status='COMPLETED'), distinct=True),
        overdue_orders=Count('order', filter=Q(order__status='OVERDUE'), distinct=True),
        in_progress_orders=Count('order', filter=Q(order__status='IN_PROGRESS'), distinct=True),
        new_orders=Count('order', filter=Q(order__status='NEW'), distinct=True),
    ).select_related('institution_type')

    # Общая статистика по всем предписаниям
    all_orders = Order.objects.all()
    total_prescriptions = all_orders.count()
    overdue_total = all_orders.filter(status='OVERDUE').count()
    completed_total = all_orders.filter(status='COMPLETED').count()
    today = date.today()
    expiring_soon_total = all_orders.filter(
        status__in=['NEW', 'IN_PROGRESS'],
        deadline_date__gte=today,
        deadline_date__lte=today + timedelta(days=14)
    ).count()
    completion_percent = round(completed_total / total_prescriptions * 100) if total_prescriptions else 0

    # Новых за месяц (для простоты – за последние 30 дней)
    one_month_ago = timezone.now() - timedelta(days=30)
    new_this_month = all_orders.filter(created_at__gte=one_month_ago).count()

    # Общее финансирование (если есть поле funding в Institution, иначе 0)
    total_funding = 0

    # Подготовка данных для карточек учреждений
    institutions_data = []
    for inst in institutions:
        # Определяем цвет прогресс-бара и статус
        if inst.overdue_orders > 0:
            bar_color = 'red'
            deadline_status = 'overdue'
            # Вычисляем максимальное количество дней просрочки среди просроченных предписаний
            overdue_days = 0
            overdue_orders = inst.order_set.filter(status='OVERDUE')
            if overdue_orders.exists():
                overdue_days = max((today - o.deadline_date).days for o in overdue_orders)
            days_left = 0
        elif inst.in_progress_orders > 0 or inst.new_orders > 0:
            # Смотрим ближайший дедлайн среди активных
            nearest = inst.order_set.filter(
                status__in=['NEW', 'IN_PROGRESS']
            ).order_by('deadline_date').first()
            if nearest:
                days_left = (nearest.deadline_date - today).days
                if days_left <= 14:
                    bar_color = 'yellow'
                    deadline_status = 'expiring'
                    overdue_days = 0
                else:
                    bar_color = 'green'
                    deadline_status = 'ok'
                    overdue_days = 0
            else:
                bar_color = 'pastel-green'
                deadline_status = 'ok'
                days_left = 0
                overdue_days = 0
        else:
            bar_color = 'pastel-green'
            deadline_status = 'ok'
            days_left = 0
            overdue_days = 0

        # Процент выполнения
        if inst.total_orders > 0:
            progress_percent = int((inst.completed_orders / inst.total_orders) * 100)
        else:
            progress_percent = 100

        # Получаем тип учреждения
        type_name = inst.institution_type.name if inst.institution_type else '—'

        institutions_data.append({
            'id': inst.id,
            'name': inst.name,
            'short_name': inst.short_name,
            'type_name': type_name,
            'total_prescriptions': inst.total_orders,
            'completed_prescriptions': inst.completed_orders,
            'overdue_count': inst.overdue_orders,
            'funding': 0,
            'deadline_status': deadline_status,
            'days_left': days_left,
            'overdue_days': overdue_days,
            'progress_percent': progress_percent,
            'bar_color': bar_color,
        })

    # Список всех предписаний для реестра
    prescriptions = Order.objects.select_related(
        'institution', 'authority', 'created_by_user'
    ).prefetch_related(
        'order_violations__violation'
    ).order_by('-created_at')

    prescriptions_data = []
    for order in prescriptions:
        # Определяем статус и прогресс для mock-подобного отображения
        if order.status == 'COMPLETED':
            status_class = 'green'
            progress = 100
            status_text = 'Выполнено'
        elif order.status == 'OVERDUE':
            status_class = 'red'
            progress = 0
            days = (today - order.deadline_date).days
            status_text = f'Просрочено на {days} дн.'
        elif order.status == 'EXPIRING':
            status_class = 'yellow'
            progress = 50
            days_left = (order.deadline_date - today).days
            status_text = f'Истекает через {days_left} дн.'
        else:
            # NEW или IN_PROGRESS
            days_left = (order.deadline_date - today).days
            if days_left < 0:
                # На всякий случай, если статус не OVERDUE, но срок уже прошёл
                status_class = 'red'
                progress = 0
                status_text = f'Просрочено на {-days_left} дн.'
            elif days_left <= 14:
                status_class = 'yellow'
                progress = 50
                status_text = f'До окончания: {days_left} дн.'
            else:
                status_class = 'green'
                progress = 75
                status_text = f'До окончания: {days_left} дн.'

        violations = [ov.violation.description for ov in order.order_violations.all()]

        prescriptions_data.append({
            'id': order.id,
            'number': order.number,
            'institution_id': order.institution.id,
            'institution_name': order.institution.short_name,
            'authority': order.authority.name if order.authority else '—',
            'due_date': order.deadline_date,
            'progress_percent': progress,
            'status_class': status_class,
            'status_text': status_text,
            'responsible': order.created_by_user.get_full_name() if order.created_by_user else '—',
            'violations': violations,
        })

    context = {
        'institutions': institutions_data,
        'prescriptions': prescriptions_data,
        'total_prescriptions': total_prescriptions,
        'overdue_total': overdue_total,
        'expiring_soon_total': expiring_soon_total,
        'completed_total': completed_total,
        'completion_percent': completion_percent,
        'total_funding': total_funding,
        'new_this_month': new_this_month,
        'user_role': 'Комитет образования',
    }
    return render(request, "committee_dashboard.html", context)


@login_required
@institution_access_required
def institution_dashboard(request, institution_id):
    """Дашборд конкретного учреждения."""
    institution = get_object_or_404(Institution, pk=institution_id)
    orders = Order.objects.filter(institution=institution).select_related(
        'authority', 'created_by_user'
    ).prefetch_related(
        'order_violations__violation'
    ).order_by('-created_at')

    completed_count = orders.filter(status='COMPLETED').count()
    overdue_count = orders.filter(status='OVERDUE').count()
    today = date.today()
    expiring_soon_total = orders.filter(
        status__in=['NEW', 'IN_PROGRESS'],
        deadline_date__gte=today,
        deadline_date__lte=today + timedelta(days=14)
    ).count()

    prescriptions_data = []
    for order in orders:
        violations = [ov.violation.description for ov in order.order_violations.all()]
        if order.status == 'COMPLETED':
            status = 'completed'
            progress = 100
            status_text = 'Выполнено'
        elif order.status == 'OVERDUE':
            status = 'overdue'
            progress = 0
            days = (today - order.deadline_date).days
            status_text = f'Просрочено на {days} дн.'
        elif order.status == 'EXPIRING':
            status = 'expiring'
            progress = 50
            days_left = (order.deadline_date - today).days
            status_text = f'Истекает через {days_left} дн.'
        else:
            # NEW или IN_PROGRESS
            days_left = (order.deadline_date - today).days
            if days_left < 0:
                # На случай, если срок прошёл, но статус не OVERDUE
                status = 'overdue'
                progress = 0
                status_text = f'Просрочено на {-days_left} дн.'
            elif days_left <= 14:
                status = 'expiring'
                progress = 50
                status_text = f'Истекает через {days_left} дн.'
            else:
                status = 'in_progress'
                progress = 75
                status_text = f'До окончания: {days_left} дн.'

        prescriptions_data.append({
            'id': order.id,
            'number': order.number,
            'authority': order.authority.name if order.authority else '—',
            'due_date': order.deadline_date,
            'status': status,
            'progress_percent': progress,
            'status_text': status_text,
            'responsible': order.created_by_user.get_full_name() if order.created_by_user else '—',
            'violations': violations,
        })

    funding = getattr(institution, 'funding', 0)

    context = {
        'institution': {
            'id': institution.id,
            'name': institution.name,
            'short_name': institution.short_name,
            'address': institution.address,
            'funding': funding,
        },
        'prescriptions': prescriptions_data,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'expiring_soon_total': expiring_soon_total,
        'funding_requests': [],
    }
    return render(request, "institution_dashboard.html", context)


def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect("login")