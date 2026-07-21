from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from datetime import date

from .mock_data import INSTITUTIONS_DATA, PRESCRIPTIONS_MOCK


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
    institutions = []
    for inst in INSTITUTIONS_DATA:
        inst_prescs = [p for p in PRESCRIPTIONS_MOCK if p["institution_id"] == inst["id"]]
        total = len(inst_prescs)
        completed = sum(1 for p in inst_prescs if p["status_class"] == "green" and p["due_date"] >= date.today())
        overdue = sum(1 for p in inst_prescs if p["status_class"] == "red")
        
        if total == 0:
            bar_color = 'pastel-green'
            progress_percent = 100
        else:
            has_red = any(p["status_class"] == "red" for p in inst_prescs)
            has_yellow = any(p["status_class"] == "yellow" for p in inst_prescs)
            if has_red:
                bar_color = 'red'
            elif has_yellow:
                bar_color = 'yellow'
            else:
                bar_color = 'green'
            progress_percent = int((completed / total * 100)) if total else 0

        if overdue > 0:
            deadline_status = "overdue"
            days_left = 0
            overdue_days = max(0, max((date.today() - p["due_date"]).days for p in inst_prescs if p["status_class"] == "red"))
        elif any(p["status_class"] == "yellow" for p in inst_prescs):
            deadline_status = "expiring"
            days_left = min((p["due_date"] - date.today()).days for p in inst_prescs if p["status_class"] == "yellow")
            overdue_days = 0
        else:
            deadline_status = "ok"
            days_left = max((p["due_date"] - date.today()).days for p in inst_prescs) if inst_prescs else 0
            overdue_days = 0

        institutions.append({
            "id": inst["id"],
            "name": inst["name"],
            "type_name": inst["type_name"],
            "total_prescriptions": total,
            "completed_prescriptions": completed,
            "overdue_count": overdue,
            "funding": inst["funding"],
            "deadline_status": deadline_status,
            "days_left": days_left,
            "overdue_days": overdue_days,
            "progress_percent": progress_percent,
            "bar_color": bar_color,
        })

    total_prescriptions = len(PRESCRIPTIONS_MOCK)
    overdue_total = sum(1 for p in PRESCRIPTIONS_MOCK if p["status_class"] == "red")
    completed_total = sum(1 for p in PRESCRIPTIONS_MOCK if p["status_class"] == "green")
    expiring_soon_total = sum(1 for p in PRESCRIPTIONS_MOCK if p["status_class"] == "yellow")
    total_funding = sum(inst["funding"] for inst in INSTITUTIONS_DATA)
    completion_percent = round(completed_total / total_prescriptions * 100) if total_prescriptions else 0
    new_this_month = 8  # заглушка

    context = {
        "institutions": institutions,
        "prescriptions": PRESCRIPTIONS_MOCK,
        "total_prescriptions": total_prescriptions,
        "overdue_total": overdue_total,
        "expiring_soon_total": expiring_soon_total,
        "completed_total": completed_total,
        "completion_percent": completion_percent,
        "total_funding": total_funding,
        "new_this_month": new_this_month,
        "user_role": "Комитет образования",
    }
    return render(request, "committee_dashboard.html", context)


@login_required
@institution_access_required
def institution_dashboard(request, institution_id):
    inst = next((i for i in INSTITUTIONS_DATA if i["id"] == institution_id), None)
    if not inst:
        from django.http import Http404
        raise Http404("Учреждение не найдено")
    
    prescs = [p for p in PRESCRIPTIONS_MOCK if p["institution_id"] == institution_id]
    completed_count = sum(1 for p in prescs if p["status_class"] == "green")
    overdue_count = sum(1 for p in prescs if p["status_class"] == "red")
    expiring_soon_total = sum(1 for p in prescs if p["status_class"] == "yellow")  # добавлено

    context = {
        "institution": {
            "id": inst["id"],
            "name": inst["name"],
            "short_name": inst["name"],
            "address": "Адрес заглушка",
            "funding": inst["funding"],
        },
        "prescriptions": prescs,
        "completed_count": completed_count,
        "overdue_count": overdue_count,
        "expiring_soon_total": expiring_soon_total,  # добавлено
        "funding_requests": [],
    }
    return render(request, "institution_dashboard.html", context)

def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect("login")