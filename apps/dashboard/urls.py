from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.committee_dashboard, name='committee_dashboard'),
    path('institution/<int:institution_id>/', views.institution_dashboard, name='institution_dashboard'),
]