"""Scoped dashboards with shared calendar rules and bounded query counts."""
from datetime import timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.permissions import can_access_all_institutions, can_access_institution, has_own_institution
from apps.institutions.models import Institution
from apps.prescriptions.deadlines import deadline_display, warning_end
from apps.prescriptions.models import Order


def committee_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if can_access_all_institutions(request.user):
            return view(request, *args, **kwargs)
        if has_own_institution(request.user):
            return redirect("institution_dashboard", institution_id=request.user.institution_id)
        raise PermissionDenied("Недостаточно прав для просмотра дашборда Комитета.")
    return wrapper


def institution_access_required(view):
    @wraps(view)
    def wrapper(request, institution_id, *args, **kwargs):
        if can_access_institution(request.user, institution_id):
            return view(request, institution_id, *args, **kwargs)
        if has_own_institution(request.user):
            return redirect("institution_dashboard", institution_id=request.user.institution_id)
        raise PermissionDenied("Недостаточно прав для просмотра учреждения.")
    return wrapper


def summary(queryset, today):
    active = ~Q(status="COMPLETED")
    return queryset.aggregate(
        total_prescriptions=Count("pk"),
        completed_total=Count("pk", filter=Q(status="COMPLETED")),
        overdue_total=Count("pk", filter=active & Q(deadline_date__lt=today)),
        expiring_soon_total=Count("pk", filter=active & Q(deadline_date__gte=today, deadline_date__lte=warning_end(today))),
        new_this_month=Count("pk", filter=Q(created_at__gte=timezone.now()-timedelta(days=30))),
    )


def order_rows(queryset, today):
    result = []
    for order in queryset.select_related("institution", "authority", "created_by_user").prefetch_related("order_violations__violation"):
        display = deadline_display(order, today)
        result.append({
            "id": order.pk, "number": order.number, "institution_id": order.institution_id,
            "institution_name": order.institution.short_name, "authority": order.authority.name,
            "due_date": order.deadline_date,
            "responsible": order.created_by_user.get_full_name() or order.created_by_user.email,
            "violations": [v.violation.description for v in order.order_violations.all()],
            **display,
            "status": {"COMPLETED": "completed", "OVERDUE": "overdue", "EXPIRING": "expiring",
                       "NEW": "in_progress", "IN_PROGRESS": "in_progress"}[display["status"]],
        })
    return result


@login_required
@committee_required
def committee_dashboard(request):
    today = timezone.localdate()
    end = warning_end(today)
    active = ~Q(order__status="COMPLETED")
    institutions = Institution.objects.select_related("institution_type").annotate(
        total_orders=Count("order"),
        completed_orders=Count("order", filter=Q(order__status="COMPLETED")),
        overdue_orders=Count("order", filter=active & Q(order__deadline_date__lt=today)),
        oldest_overdue=Min("order__deadline_date", filter=active & Q(order__deadline_date__lt=today)),
        nearest_deadline=Min("order__deadline_date", filter=active & Q(order__deadline_date__gte=today)),
    )
    cards = []
    for inst in institutions:
        overdue = inst.overdue_orders > 0
        expiring = inst.nearest_deadline is not None and inst.nearest_deadline <= end
        cards.append({
            "id": inst.pk, "name": inst.name, "short_name": inst.short_name,
            "type_name": inst.institution_type.name,
            "total_prescriptions": inst.total_orders, "completed_prescriptions": inst.completed_orders,
            "overdue_count": inst.overdue_orders, "funding": 0,
            "deadline_status": "overdue" if overdue else "expiring" if expiring else "ok",
            "bar_color": "red" if overdue else "yellow" if expiring else "green" if inst.nearest_deadline else "pastel-green",
            "days_left": (inst.nearest_deadline-today).days if inst.nearest_deadline else 0,
            "overdue_days": (today-inst.oldest_overdue).days if overdue else 0,
            "progress_percent": int(100*inst.completed_orders/inst.total_orders) if inst.total_orders else 100,
        })
    orders = Order.objects.all()
    context = summary(orders, today)
    context.update(institutions=cards, prescriptions=order_rows(orders, today), total_funding=0)
    total = context["total_prescriptions"]
    context["completion_percent"] = round(100*context["completed_total"]/total) if total else 0
    return render(request, "committee_dashboard.html", context)


@login_required
@institution_access_required
def institution_dashboard(request, institution_id):
    institution = get_object_or_404(Institution, pk=institution_id)
    today = timezone.localdate()
    orders = Order.objects.filter(institution_id=institution_id)
    stats = summary(orders, today)
    return render(request, "institution_dashboard.html", {
        "institution": {"id": institution.pk, "name": institution.name, "short_name": institution.short_name,
                        "address": institution.address, "funding": 0},
        "prescriptions": order_rows(orders, today), "completed_count": stats["completed_total"],
        "overdue_count": stats["overdue_total"], "expiring_soon_total": stats["expiring_soon_total"],
        "funding_requests": [],
    })
