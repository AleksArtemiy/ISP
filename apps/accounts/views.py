from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

# Получаем кастомную модель User
User = get_user_model()

def login_view(request):
    if request.user.is_authenticated:
        return redirect('committee_dashboard') 
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        if not email:
            messages.error(request, 'Пожалуйста, введите email')
            return render(request, 'accounts/login.html')
        
        if not password:
            messages.error(request, 'Пожалуйста, введите пароль')
            return render(request, 'accounts/login.html')
        
        # Только аутентификация, без автоматического создания
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'committee_dashboard')
            return redirect(next_url)
        else:
            # Проверяем, существует ли пользователь
            try:
                User.objects.get(email=email)
                messages.error(request, 'Неверный пароль')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь с таким email не найден. Зарегистрируйтесь сначала.')
    
    return render(request, 'accounts/login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')