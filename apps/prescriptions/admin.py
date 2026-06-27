from django.contrib import admin
from .models import Status, Authority, Order, Violation

@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'institution', 'deadline_date', 'status', 'year')
    list_filter = ('status', 'year', 'institution')
    search_fields = ('order_number',)

@admin.register(Violation)
class ViolationAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'description')
    list_filter = ('order',)