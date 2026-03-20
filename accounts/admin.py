from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'get_full_name', 'role', 'employee_id', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('FANS Info', {'fields': ('role', 'employee_id', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('FANS Info', {'fields': ('role', 'employee_id', 'phone')}),
    )
