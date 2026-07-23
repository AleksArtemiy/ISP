"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.dashboard.views import committee_dashboard, institution_dashboard
from apps.accounts.views import login_view, logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', committee_dashboard, name='committee_dashboard'),
    path('institution/<int:institution_id>/', institution_dashboard, name='institution_dashboard'),
    path('prescriptions/', include('apps.prescriptions.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('admin-panel/', include('apps.admin_panel.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
]

# Добавляем обслуживание медиа-файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)