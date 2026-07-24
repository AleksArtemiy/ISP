from django.urls import path
from . import views

"""
Маршруты панели администратора.

Содержит URL-адреса для управления:
    - учреждениями (Institution)
    - пользователями (User)
    - надзорными органами (SupervisoryAuthority)

Все URL используют префикс admin-panel/ (задаётся в корневом urls.py).
"""

from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Главная страница админ-панели
    path('', views.admin_panel, name='admin_panel'),
    
    # Учреждения
    path('institution/create/', views.institution_create, name='admin_institution_create'),
    path('institution/<int:pk>/edit/', views.institution_edit, name='admin_institution_edit'),
    path('institution/<int:pk>/delete/', views.institution_delete, name='admin_institution_delete'),
    
    # Пользователи (вместо сотрудников)
    path('user/create/', views.user_create, name='admin_user_create'),
    path('user/<int:pk>/edit/', views.user_edit, name='admin_user_edit'),
    path('user/<int:pk>/delete/', views.user_delete, name='admin_user_delete'),
    
    # Надзорные органы
    path('authority/create/', views.authority_create, name='admin_authority_create'),
    path('authority/<int:pk>/edit/', views.authority_edit, name='admin_authority_edit'),
    path('authority/<int:pk>/delete/', views.authority_delete, name='admin_authority_delete'),

    # Типы учреждений
    path('institution-type/create/', views.institution_type_create, name='admin_institution_type_create'),
    path('institution-type/<int:pk>/edit/', views.institution_type_edit, name='admin_institution_type_edit'),
    path('institution-type/<int:pk>/delete/', views.institution_type_delete, name='admin_institution_type_delete'),
]