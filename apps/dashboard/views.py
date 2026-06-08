from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from datetime import date, timedelta
import random

# ========== МОК-ДАННЫЕ ДЛЯ 22 УЧРЕЖДЕНИЙ ==========
INSTITUTIONS_DATA = [
    {"id": 1, "name": "Школа №1", "type_name": "Школа", "funding": 182000},
    {"id": 2, "name": "Школа №2", "type_name": "Школа", "funding": 45000},
    {"id": 3, "name": "Детский сад «Солнышко»", "type_name": "Детский сад", "funding": 98000},
    {"id": 4, "name": "Школа №3", "type_name": "Школа", "funding": 250000},
    {"id": 5, "name": "Детский сад «Ромашка»", "type_name": "Детский сад", "funding": 34000},
    {"id": 6, "name": "Гимназия №1", "type_name": "Школа", "funding": 0},
    {"id": 7, "name": "Школа №4", "type_name": "Школа", "funding": 120000},
    {"id": 8, "name": "Детский сад «Берёзка»", "type_name": "Детский сад", "funding": 67000},
    {"id": 9, "name": "Школа №5", "type_name": "Школа", "funding": 89000},
    {"id": 10, "name": "Детский сад «Колокольчик»", "type_name": "Детский сад", "funding": 45000},
    {"id": 11, "name": "Школа №6", "type_name": "Школа", "funding": 310000},
    {"id": 12, "name": "Детский сад «Звёздочка»", "type_name": "Детский сад", "funding": 27000},
    {"id": 13, "name": "Школа №7", "type_name": "Школа", "funding": 56000},
    {"id": 14, "name": "Детский сад «Сказка»", "type_name": "Детский сад", "funding": 0},
    {"id": 15, "name": "Школа №8", "type_name": "Школа", "funding": 149000},
    {"id": 16, "name": "Детский лагерь «Дружба»", "type_name": "Детский лагерь", "funding": 210000},
    {"id": 17, "name": "Школа №9", "type_name": "Школа", "funding": 0},
    {"id": 18, "name": "Детский сад «Улыбка»", "type_name": "Детский сад", "funding": 43000},
    {"id": 19, "name": "Школа №10", "type_name": "Школа", "funding": 95000},
    {"id": 20, "name": "Детский сад «Теремок»", "type_name": "Детский сад", "funding": 77000},
    {"id": 21, "name": "Вечерняя школа", "type_name": "Школа", "funding": 22000},
    {"id": 22, "name": "Детский лагерь «Олимпиец»", "type_name": "Детский лагерь", "funding": 180000},
]

# ========== ГЕНЕРАЦИЯ МОК-ПРЕДПИСАНИЙ (24 шт) ==========
authorities = ["Пожнадзор", "Роспотребнадзор", "Рособрнадзор", "Трудовая инспекция"]
status_templates = [
    {"class": "green", "progress": (70,100), "days_left": (15,60)},
    {"class": "yellow", "progress": (30,69), "days_left": (1,14)},
    {"class": "red", "progress": (0,29), "days_left": (-10,-1)},
]

def random_due_date():
    return date.today() + timedelta(days=random.randint(-5, 60))

def random_progress_and_status(due_date):
    days = (due_date - date.today()).days
    if days < 0:
        return {"class": "red", "progress": random.randint(0, 30), "text": f"Просрочено на {-days} дн."}
    elif days <= 14:
        return {"class": "yellow", "progress": random.randint(30, 70), "text": f"До окончания: {days} дн."}
    else:
        return {"class": "green", "progress": random.randint(70, 100), "text": f"До окончания: {days} дн."}

def get_violations(presc_id):
    base = [
        ["Неисправна пожарная сигнализация", "Отсутствуют огнетушители"],
        ["Нарушение температурного режима", "Нет маркировки на продуктах"],
        ["Нет плана эвакуации", "Запасные выходы заблокированы"],
        ["Просрочены санитарные книжки", "Нет графика дезинфекции"],
        ["Не ведётся журнал инструктажа", "Нет аптечек"],
        ["Освещение не соответствует нормам", "Электропроводка открытая"],
    ]
    return base[presc_id % len(base)]

# Генерация предписаний
PRESCRIPTIONS_MOCK = []
for i in range(1, 25):
    inst_id = random.randint(1, 22)
    due = random_due_date()
    status_info = random_progress_and_status(due)
    presc = {
        "id": i,
        "number": f"ПР-{100+i}",
        "institution_id": inst_id,
        "institution_name": next(inst["name"] for inst in INSTITUTIONS_DATA if inst["id"] == inst_id),
        "authority": random.choice(authorities),
        "due_date": due,
        "progress_percent": status_info["progress"],
        "status_class": status_info["class"],
        "status_text": status_info["text"],
        "responsible": f"Ответственный {random.choice(['Иванов','Петрова','Сидоров','Кузнецова','Смирнов'])}",
        "violations": get_violations(i),
    }
    PRESCRIPTIONS_MOCK.append(presc)

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("committee_dashboard")
        else:
            messages.error(request, "Неверное имя пользователя или пароль")
    return render(request, "login.html")

def committee_dashboard(request):
    # Подготовка данных по учреждениям для карточек
    institutions = []
    for inst in INSTITUTIONS_DATA:
        inst_prescs = [p for p in PRESCRIPTIONS_MOCK if p["institution_id"] == inst["id"]]
        total = len(inst_prescs)
        completed = sum(1 for p in inst_prescs if p["status_class"] == "green" and p["due_date"] >= date.today())
        overdue = sum(1 for p in inst_prescs if p["status_class"] == "red")
        
        # Определяем цвет прогресс-бара по новым правилам
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

        # Дополнительные поля для отображения текста (оставляем как есть)
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
            "bar_color": bar_color,          # новое поле
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

def institution_dashboard(request, institution_id):
    # сохраняем для совместимости (позже доработаем в стиле дашборда учреждения)
    inst = next((i for i in INSTITUTIONS_DATA if i["id"] == institution_id), None)
    if not inst:
        from django.http import Http404
        raise Http404("Учреждение не найдено")
    # фильтруем предписания для этого учреждения
    prescs = [p for p in PRESCRIPTIONS_MOCK if p["institution_id"] == institution_id]
    context = {
        "institution": inst,
        "prescriptions": prescs,
        "funding_requests": [],  # можно добавить мок-заявки позже
    }
    return render(request, "institution_dashboard.html", context)

def logout_view(request):
    logout(request)
    return redirect("login")