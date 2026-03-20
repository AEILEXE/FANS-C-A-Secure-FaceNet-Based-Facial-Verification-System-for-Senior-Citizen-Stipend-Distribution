from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'target_type', 'ip_address']
    list_filter = ['action']
    search_fields = ['user__username', 'target_id']
    readonly_fields = ['id', 'timestamp', 'ip_address', 'user_agent']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
