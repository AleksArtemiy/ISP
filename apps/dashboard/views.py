from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Create your views here.
MOCK_INSTITUTIONS = [
    {"id": 1, "name": "Школа №1 (Новгород)", "total_prescriptions": 5, "funding": 182000, "overdue_count": 1},
    {"id": 2, "name": "Школа №2 им. Героя", "total_prescriptions": 3, "funding": 45000, "overdue_count": 0},
    {"id": 3, "name": "Детский сад «Солнышко»", "total_prescriptions": 4, "funding": 98000, "overdue_count": 2},
]

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        # Временно имитируем вход: для демо любые логин/пароль
        # В реальности нужно будет использовать аутентификацию Django
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Перенаправление в зависимости от роли (будет настроено позже)
            return redirect("committee_dashboard")
        else:
            # Временная заглушка: создаём "технического" пользователя
            # Это только для демонстрации, не для продакшна
            messages.error(request, "Неверное имя пользователя или пароль")
    return render(request, "login.html")

@login_required
def committee_dashboard(request):
    # Проверка, что пользователь имеет роль 'committee'
    # Пока просто передаём список учреждений
    context = {
        "institutions": MOCK_INSTITUTIONS,
    }
    return render(request, "committee_dashboard.html", context)

@login_required
def institution_dashboard(request, institution_id):
    # Находим учреждение по ID (пока из мок-данных)
    institution = next((inst for inst in MOCK_INSTITUTIONS if inst["id"] == institution_id), None)
    if not institution:
        # 404 можно вернуть
        from django.http import Http404
        raise Http404("Учреждение не найдено")
    
    # Мок-предписания для этого учреждения (можно вынести в отдельный словарь)
    mock_prescriptions = {
        1: [
            {"number": "РПН-23/45", "oversight": "Роспотребнадзор", "due_date": "2026-05-20", "status": "overdue", "violations": ["Санитарное состояние", "Маркировка"]},
            {"number": "ГПН-78/12", "oversight": "Госпожнадзор", "due_date": "2026-06-10", "status": "expiring", "violations": ["Огнетушители"]},
        ],
        3: [
            {"number": "РПН-67/88", "oversight": "Роспотребнадзор", "due_date": "2026-05-10", "status": "overdue", "violations": ["Игрушки"]},
        ],
    }
    prescriptions = mock_prescriptions.get(institution_id, [])
    
    context = {
        "institution": institution,
        "prescriptions": prescriptions,
        "funding_requests": [],  # позже добавим
    }
    return render(request, "institution_dashboard.html", context)

def logout_view(request):
    logout(request)
    return redirect("login")