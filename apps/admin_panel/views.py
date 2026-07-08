# apps/admin_panel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from apps.institutions.models import Institution, Employee
from apps.prescriptions.models import Authority, Status
from .forms import InstitutionForm, EmployeeForm, AuthorityForm, StatusForm


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
    context = {
        'institutions': Institution.objects.all(),
        'employees': Employee.objects.select_related('institution').all(),
        'authorities': Authority.objects.all(),
        'statuses': Status.objects.all(),
    }
    return render(request, 'admin_panel/index.html', context)


# ------------------- УЧРЕЖДЕНИЯ -------------------
@login_required
@admin_required
def institution_create(request):
    if request.method == 'POST':
        form = InstitutionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Учреждение создано')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать учреждение'})
    else:
        form = InstitutionForm()
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать учреждение'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать учреждение'})


@login_required
@admin_required
def institution_edit(request, pk):
    inst = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        form = InstitutionForm(request.POST, instance=inst)
        if form.is_valid():
            form.save()
            messages.success(request, 'Учреждение обновлено')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать учреждение'})
    else:
        form = InstitutionForm(instance=inst)
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать учреждение'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать учреждение'})


@login_required
@admin_required
def institution_delete(request, pk):
    inst = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        inst.delete()
        messages.success(request, 'Учреждение удалено')
        if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('admin_panel')
    if request.GET.get('modal'):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': inst, 'type': 'учреждение'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': inst, 'type': 'учреждение'})


# ------------------- СОТРУДНИКИ -------------------
@login_required
@admin_required
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Сотрудник добавлен')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Добавить сотрудника'})
    else:
        form = EmployeeForm()
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Добавить сотрудника'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Добавить сотрудника'})


@login_required
@admin_required
def employee_edit(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=emp)
        if form.is_valid():
            form.save()
            messages.success(request, 'Сотрудник обновлён')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать сотрудника'})
    else:
        form = EmployeeForm(instance=emp)
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать сотрудника'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать сотрудника'})


@login_required
@admin_required
def employee_delete(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        emp.delete()
        messages.success(request, 'Сотрудник удалён')
        if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('admin_panel')
    if request.GET.get('modal'):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': emp, 'type': 'сотрудника'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': emp, 'type': 'сотрудника'})


# ------------------- НАДЗОРНЫЕ ОРГАНЫ -------------------
@login_required
@admin_required
def authority_create(request):
    if request.method == 'POST':
        form = AuthorityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Надзорный орган создан')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать надзорный орган'})
    else:
        form = AuthorityForm()
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать надзорный орган'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать надзорный орган'})


@login_required
@admin_required
def authority_edit(request, pk):
    auth = get_object_or_404(Authority, pk=pk)
    if request.method == 'POST':
        form = AuthorityForm(request.POST, instance=auth)
        if form.is_valid():
            form.save()
            messages.success(request, 'Надзорный орган обновлён')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})
    else:
        form = AuthorityForm(instance=auth)
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать надзорный орган'})


@login_required
@admin_required
def authority_delete(request, pk):
    auth = get_object_or_404(Authority, pk=pk)
    if request.method == 'POST':
        auth.delete()
        messages.success(request, 'Надзорный орган удалён')
        if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('admin_panel')
    if request.GET.get('modal'):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': auth, 'type': 'надзорный орган'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': auth, 'type': 'надзорный орган'})


# ------------------- СТАТУСЫ -------------------
@login_required
@admin_required
def status_create(request):
    if request.method == 'POST':
        form = StatusForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Статус создан')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать статус'})
    else:
        form = StatusForm()
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Создать статус'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Создать статус'})


@login_required
@admin_required
def status_edit(request, pk):
    st = get_object_or_404(Status, pk=pk)
    if request.method == 'POST':
        form = StatusForm(request.POST, instance=st)
        if form.is_valid():
            form.save()
            messages.success(request, 'Статус обновлён')
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_panel')
        else:
            if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать статус'})
    else:
        form = StatusForm(instance=st)
        if request.GET.get('modal'):
            return render(request, 'admin_panel/_form.html', {'form': form, 'title': 'Редактировать статус'})
    return render(request, 'admin_panel/generic_form.html', {'form': form, 'title': 'Редактировать статус'})


@login_required
@admin_required
def status_delete(request, pk):
    st = get_object_or_404(Status, pk=pk)
    if request.method == 'POST':
        st.delete()
        messages.success(request, 'Статус удалён')
        if request.GET.get('modal') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('admin_panel')
    if request.GET.get('modal'):
        return render(request, 'admin_panel/_confirm_delete.html', {'object': st, 'type': 'статус'})
    return render(request, 'admin_panel/confirm_delete.html', {'object': st, 'type': 'статус'})