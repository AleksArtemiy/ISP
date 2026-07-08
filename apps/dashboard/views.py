from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import date

from .mock_data import INSTITUTIONS_DATA, PRESCRIPTIONS_MOCK

# (если у вас остались login_view/logout_view – их тоже можно убрать, но пока оставим)

def login_view(request):
    # ... ваш код (но лучше перенести в accounts)
    pass

@login_required
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
    new_this_month = 8  # пока оставляем заглушку

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
def institution_dashboard(request, institution_id):
    inst = next((i for i in INSTITUTIONS_DATA if i["id"] == institution_id), None)
    if not inst:
        from django.http import Http404
        raise Http404("Учреждение не найдено")
    
    prescs = [p for p in PRESCRIPTIONS_MOCK if p["institution_id"] == institution_id]
    context = {
        "institution": inst,
        "prescriptions": prescs,
        "funding_requests": [],
    }
    return render(request, "institution_dashboard.html", context)

def logout_view(request):
    logout(request)
    return redirect("login")