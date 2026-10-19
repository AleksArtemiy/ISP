from django.contrib import admin
from .models import SupervisoryAuthority, Order, Violation, OrderViolation, File


class ReadOnlyBusinessAdmin(admin.ModelAdmin):
    """Business writes must pass the application workflow, even for superusers.

    Permission hooks reject crafted POSTs as well as hiding editing controls.
    Removing actions also excludes Django's physical bulk-delete operation.
    """
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SupervisoryAuthority)
class SupervisoryAuthorityAdmin(ReadOnlyBusinessAdmin):
    """Администрирование надзорных органов"""
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Order)
class OrderAdmin(ReadOnlyBusinessAdmin):
    """Администрирование предписаний"""
    list_display = ('number', 'institution', 'deadline_date', 'status', 'created_by_user')
    list_filter = ('status', 'institution', 'authority')
    search_fields = ('number',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Violation)
class ViolationAdmin(ReadOnlyBusinessAdmin):
    """Администрирование нарушений"""
    list_display = ('id', 'description')
    search_fields = ('description',)


@admin.register(OrderViolation)
class OrderViolationAdmin(ReadOnlyBusinessAdmin):
    """Администрирование связей предписаний и нарушений"""
    list_display = ('id', 'order', 'violation')
    list_filter = ('order',)


@admin.register(File)
class FileAdmin(ReadOnlyBusinessAdmin):
    """Администрирование файлов"""
    list_display = ('id', 'order', 'original_filename', 'uploaded_at')
    list_filter = ('order',)
