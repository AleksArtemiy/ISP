# apps/admin_panel/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_panel, name='admin_panel'),
    
    # Учреждения
    path('institution/create/', views.institution_create, name='admin_institution_create'),
    path('institution/<int:pk>/edit/', views.institution_edit, name='admin_institution_edit'),
    path('institution/<int:pk>/delete/', views.institution_delete, name='admin_institution_delete'),
    
    # Сотрудники
    path('employee/create/', views.employee_create, name='admin_employee_create'),
    path('employee/<int:pk>/edit/', views.employee_edit, name='admin_employee_edit'),
    path('employee/<int:pk>/delete/', views.employee_delete, name='admin_employee_delete'),
    
    # Надзорные органы
    path('authority/create/', views.authority_create, name='admin_authority_create'),
    path('authority/<int:pk>/edit/', views.authority_edit, name='admin_authority_edit'),
    path('authority/<int:pk>/delete/', views.authority_delete, name='admin_authority_delete'),
    
    # Статусы
    path('status/create/', views.status_create, name='admin_status_create'),
    path('status/<int:pk>/edit/', views.status_edit, name='admin_status_edit'),
    path('status/<int:pk>/delete/', views.status_delete, name='admin_status_delete'),
]