from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role


class UserAdmin(BaseUserAdmin):
    """Кастомный админ для User модели с email вместо username."""
    
    list_display = ('email', 'get_full_name', 'is_staff', 'is_active', 'created_at')
    list_filter = ('is_staff', 'is_active', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'patronymic', 'phone')}),
        ('Роль и учреждение', {'fields': ('role', 'institution')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'patronymic', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'last_login')
    
    def get_full_name(self, obj):
        """Показывает полное имя пользователя в списке."""
        return obj.get_full_name()
    get_full_name.short_description = 'ФИО'


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


admin.site.register(User, UserAdmin)
