from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError

User = get_user_model()


def get_redirect_url(user):
    """
    Определяет URL для перенаправления после входа в зависимости от роли пользователя.
    """
    if user.is_superuser:
        return reverse('admin_panel:admin_panel')
    
    # Проверяем, есть ли у пользователя роль "Комитет" (регистронезависимо)
    if user.role and 'комитет' in user.role.name.lower():
        return reverse('committee_dashboard')
    
    # Если пользователь привязан к учреждению, перенаправляем на дашборд учреждения
    if user.institution:
        return reverse('institution_dashboard', kwargs={'institution_id': user.institution.id})
    
    # По умолчанию – дашборд комитета
    return reverse('committee_dashboard')


def login_view(request):
    # Если пользователь уже залогинен, сразу перенаправляем
    if request.user.is_authenticated:
        return redirect(get_redirect_url(request.user))
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        if not email:
            messages.error(request, 'Пожалуйста, введите email')
            return render(request, 'accounts/login.html')
        
        if not password:
            messages.error(request, 'Пожалуйста, введите пароль')
            return render(request, 'accounts/login.html')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect(get_redirect_url(user))
        else:
            try:
                User.objects.get(email=email)
                messages.error(request, 'Неверный пароль')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь с таким email не найден.')
    
    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')