# apps/admin_panel/views.py
"""
Представления для панели администратора.

Обеспечивают CRUD-операции для управления:
    - учреждениями (Institution)
    - пользователями (User)
    - надзорными органами (SupervisoryAuthority)

Все представления доступны только суперпользователям (is_superuser=True).
Поддерживают работу через модальные окна (AJAX) и обычные GET/POST-запросы.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import get_user_model

from apps.institutions.models import Institution, InstitutionType
from apps.prescriptions.models import SupervisoryAuthority
from .forms import InstitutionForm, UserForm, SupervisoryAuthorityForm

User = get_user_model()

def admin_required(view_func):
    """Декоратор: доступ только для суперпользователей"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Доступ запрещён. Требуются права администратора.")
            return redirect('committee_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ------------------- ГЛАВНАЯ СТРАНИЦА -------------------
@login_required
@admin_required
def admin_panel(request):
    """
    Главная страница панели администратора.

    Передаёт в контекст все учреждения, пользователей и надзорные органы
    для отображения статистики и таблиц.
    """
    context = {
        'institutions': Institution.objects.all().select_related('institution_type'),
        'users': User.objects.all().select_related('institution', 'role'),
        'authorities': SupervisoryAuthority.objects.all(),
        'institution_types': InstitutionType.objects.all(),
        'total_institutions': Institution.objects.count(),
        'total_users': User.objects.count(),
        'total_authorities': SupervisoryAuthority.objects.count(),
    }
    return render(request, 'admin_panel/index.html', context)


# ------------------- УЧРЕЖДЕНИЯ -------------------
@login_required
@admin_required
def institution_create(request):
    """
    Создание нового учреждения.

    Поддерживает AJAX-запросы для модального окна.
    При успехе возвращает JSON {'success': True}, иначе — форму с ошибками.
    """
    if request.method == 'POST':
        form = InstitutionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Учреждение создано')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        # При ошибке возвращаем форму для модального окна
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать учреждение'})
    else:
        form = InstitutionForm()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать учреждение'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать учреждение'})


@login_required
@admin_required
def institution_edit(request, pk):
    """
    Редактирование учреждения.
    """
    inst = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        form = InstitutionForm(request.POST, instance=inst)
        if form.is_valid():
            form.save()
            messages.success(request, 'Учреждение обновлено')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать учреждение'})
    else:
        form = InstitutionForm(instance=inst)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать учреждение'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать учреждение'})


@login_required
@admin_required
def institution_delete(request, pk):
    """
    Удаление учреждения с подтверждением.
    """
    inst = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        inst.delete()
        messages.success(request, 'Учреждение удалено')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('admin_panel')
    # GET-запрос – показываем страницу подтверждения
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'admin_panel/_confirm_delete.html', {'object': inst, 'type': 'учреждение'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': inst, 'type': 'учреждение'})


# ------------------- СОТРУДНИКИ -------------------
@login_required
@admin_required
def user_create(request):
    """
    Создание нового пользователя.

    Устанавливает временный пароль 'temp123' — позже пользователь сможет сменить его.
    """
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password('temp123')  # временный пароль
            user.save()
            messages.success(request, f'Пользователь {user.email} создан (временный пароль: temp123)')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать пользователя'})
    else:
        form = UserForm()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать пользователя'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать пользователя'})

@login_required
@admin_required
def user_edit(request, pk):
    """
    Редактирование пользователя.
    """
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Пользователь обновлён')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать пользователя'})
    else:
        form = UserForm(instance=user)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать пользователя'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать пользователя'})


@login_required
@admin_required
def user_delete(request, pk):
    """
    Удаление пользователя.
    """
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'Пользователь удалён')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('admin_panel')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'admin_panel/_confirm_delete.html', {'object': user, 'type': 'пользователя'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': user, 'type': 'пользователя'})

# ------------------- НАДЗОРНЫЕ ОРГАНЫ -------------------
@login_required
@admin_required
def authority_create(request):
    """
    Создание надзорного органа.
    """
    if request.method == 'POST':
        form = SupervisoryAuthorityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Надзорный орган создан')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать надзорный орган'})
    else:
        form = SupervisoryAuthorityForm()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать надзорный орган'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать надзорный орган'})

@login_required
@admin_required
def authority_edit(request, pk):
    """
    Редактирование надзорного органа.
    """
    auth = get_object_or_404(SupervisoryAuthority, pk=pk)
    if request.method == 'POST':
        form = SupervisoryAuthorityForm(request.POST, instance=auth)
        if form.is_valid():
            form.save()
            messages.success(request, 'Надзорный орган обновлён')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})
    else:
        form = SupervisoryAuthorityForm(instance=auth)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})


@login_required
@admin_required
def authority_delete(request, pk):
    """
    Удаление надзорного органа.
    """
    auth = get_object_or_404(SupervisoryAuthority, pk=pk)
    if request.method == 'POST':
        auth.delete()
        messages.success(request, 'Надзорный орган удалён')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('admin_panel')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'admin_panel/_confirm_delete.html', {'object': auth, 'type': 'надзорный орган'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': auth, 'type': 'надзорный орган'})