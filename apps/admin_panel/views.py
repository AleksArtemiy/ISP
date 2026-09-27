# apps/admin_panel/views.py
"""
Представления для панели администратора.
Обеспечивают CRUD-операции для управления:
    - учреждениями (Institution)
    - пользователями (User)
    - надзорными органами (SupervisoryAuthority)
    - типами учреждений (InstitutionType)

Все представления доступны только суперпользователям.
Поддерживают работу через модальные окна (AJAX) и обычные GET/POST-запросы.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import get_user_model

from apps.institutions.models import Institution, InstitutionType
from apps.prescriptions.models import SupervisoryAuthority
from .forms import InstitutionForm, UserForm, SupervisoryAuthorityForm, InstitutionTypeForm

User = get_user_model()


def admin_required(view_func):
    """Декоратор: доступ только для суперпользователей."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Доступ запрещён. Требуются права администратора.")
            return redirect('committee_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def is_ajax(request):
    """Проверка, является ли запрос AJAX."""
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


# ------------------- ГЛАВНАЯ СТРАНИЦА -------------------

@login_required
@admin_required
def admin_panel(request):
    """Главная страница панели администратора."""
    context = {
        'institutions': Institution.objects.all().select_related('institution_type'),
        'users': User.objects.all().select_related('institution', 'role'),
        'authorities': SupervisoryAuthority.objects.all(),
        'institution_types': InstitutionType.objects.all(),
    }
    return render(request, 'admin_panel/index.html', context)


# ------------------- УЧРЕЖДЕНИЯ -------------------

@login_required
@admin_required
def institution_create(request):
    """Создание учреждения."""
    if request.method == 'POST':
        form = InstitutionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Учреждение создано')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать учреждение'})
    else:
        form = InstitutionForm()
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать учреждение'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать учреждение'})


@login_required
@admin_required
def institution_edit(request, pk):
    """Редактирование учреждения."""
    inst = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        form = InstitutionForm(request.POST, instance=inst)
        if form.is_valid():
            form.save()
            messages.success(request, 'Учреждение обновлено')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать учреждение'})
    else:
        form = InstitutionForm(instance=inst)
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать учреждение'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать учреждение'})


@login_required
@admin_required
def institution_delete(request, pk):
    """Удаление учреждения с подтверждением."""
    inst = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        inst.delete()
        messages.success(request, 'Учреждение удалено')
        if is_ajax(request):
            return JsonResponse({'success': True})
        return redirect('admin_panel:admin_panel')
    # GET-запрос – показываем страницу подтверждения
    if is_ajax(request):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': inst, 'type': 'учреждение'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': inst, 'type': 'учреждение'})


# ------------------- ПОЛЬЗОВАТЕЛИ -------------------

@login_required
@admin_required
def user_create(request):
    """Создание пользователя."""
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Пользователь {user.email} создан')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать пользователя'})
    else:
        form = UserForm()
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать пользователя'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать пользователя'})


@login_required
@admin_required
def user_edit(request, pk):
    """Редактирование пользователя."""
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Пользователь обновлён')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать пользователя'})
    else:
        form = UserForm(instance=user)
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать пользователя'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать пользователя'})


@login_required
@admin_required
def user_delete(request, pk):
    """Удаление пользователя."""
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'Пользователь удалён')
        if is_ajax(request):
            return JsonResponse({'success': True})
        return redirect('admin_panel:admin_panel')
    if is_ajax(request):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': user, 'type': 'пользователя'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': user, 'type': 'пользователя'})


# ------------------- НАДЗОРНЫЕ ОРГАНЫ -------------------

@login_required
@admin_required
def authority_create(request):
    """Создание надзорного органа."""
    if request.method == 'POST':
        form = SupervisoryAuthorityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Надзорный орган создан')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать надзорный орган'})
    else:
        form = SupervisoryAuthorityForm()
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать надзорный орган'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать надзорный орган'})


@login_required
@admin_required
def authority_edit(request, pk):
    """Редактирование надзорного органа."""
    auth = get_object_or_404(SupervisoryAuthority, pk=pk)
    if request.method == 'POST':
        form = SupervisoryAuthorityForm(request.POST, instance=auth)
        if form.is_valid():
            form.save()
            messages.success(request, 'Надзорный орган обновлён')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})
    else:
        form = SupervisoryAuthorityForm(instance=auth)
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})


@login_required
@admin_required
def authority_delete(request, pk):
    """Удаление надзорного органа."""
    auth = get_object_or_404(SupervisoryAuthority, pk=pk)
    if request.method == 'POST':
        auth.delete()
        messages.success(request, 'Надзорный орган удалён')
        if is_ajax(request):
            return JsonResponse({'success': True})
        return redirect('admin_panel:admin_panel')
    if is_ajax(request):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': auth, 'type': 'надзорный орган'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': auth, 'type': 'надзорный орган'})


# ------------------- ТИПЫ УЧРЕЖДЕНИЙ -------------------

@login_required
@admin_required
def institution_type_create(request):
    """Создание типа учреждения."""
    if request.method == 'POST':
        form = InstitutionTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тип учреждения создан')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать тип учреждения'})
    else:
        form = InstitutionTypeForm()
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать тип учреждения'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать тип учреждения'})


@login_required
@admin_required
def institution_type_edit(request, pk):
    """Редактирование типа учреждения."""
    inst_type = get_object_or_404(InstitutionType, pk=pk)
    if request.method == 'POST':
        form = InstitutionTypeForm(request.POST, instance=inst_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тип учреждения обновлён')
            if is_ajax(request):
                return JsonResponse({'success': True})
            return redirect('admin_panel:admin_panel')
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать тип учреждения'})
    else:
        form = InstitutionTypeForm(instance=inst_type)
        if is_ajax(request):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать тип учреждения'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать тип учреждения'})


@login_required
@admin_required
def institution_type_delete(request, pk):
    """Удаление типа учреждения."""
    inst_type = get_object_or_404(InstitutionType, pk=pk)
    if request.method == 'POST':
        inst_type.delete()
        messages.success(request, 'Тип учреждения удалён')
        if is_ajax(request):
            return JsonResponse({'success': True})
        return redirect('admin_panel:admin_panel')
    if is_ajax(request):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': inst_type, 'type': 'тип учреждения'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': inst_type, 'type': 'тип учреждения'})