from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

# Получаем кастомную модель User
User = get_user_model()

def login_view(request):
    if request.user.is_authenticated:
        return redirect('committee_dashboard') 
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(password)
            user.save()
        
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next', 'committee_dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Ошибка входа')
    
    return render(request, 'accounts/login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')