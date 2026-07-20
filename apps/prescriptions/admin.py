from django.contrib import admin
from .models import SupervisoryAuthority, Order, Violation, OrderViolation, File


@admin.register(SupervisoryAuthority)
class SupervisoryAuthorityAdmin(admin.ModelAdmin):
    """Администрирование надзорных органов"""
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Администрирование предписаний"""
    list_display = ('number', 'institution', 'deadline_date', 'status', 'created_by_user')
    list_filter = ('status', 'institution', 'authority')
    search_fields = ('number',)
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('institution', 'authority', 'created_by_user')


@admin.register(Violation)
class ViolationAdmin(admin.ModelAdmin):
    """Администрирование нарушений"""
    list_display = ('id', 'description')
    search_fields = ('description',)


@admin.register(OrderViolation)
class OrderViolationAdmin(admin.ModelAdmin):
    """Администрирование связей предписаний и нарушений"""
    list_display = ('id', 'order', 'violation')
    list_filter = ('order',)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    """Администрирование файлов"""
    list_display = ('id', 'order', 'original_filename', 'uploaded_at')
    list_filter = ('order',)