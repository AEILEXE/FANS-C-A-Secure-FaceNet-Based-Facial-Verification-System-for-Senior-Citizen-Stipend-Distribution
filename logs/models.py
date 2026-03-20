from django.db import models
from django.conf import settings
import uuid


class AuditLog(models.Model):
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_LOGIN_FAILED = 'login_failed'
    ACTION_REGISTER = 'register'
    ACTION_VERIFY = 'verify'
    ACTION_OVERRIDE = 'override'
    ACTION_USER_CREATE = 'user_create'
    ACTION_USER_UPDATE = 'user_update'
    ACTION_USER_DEACTIVATE = 'user_deactivate'
    ACTION_CONFIG_CHANGE = 'config_change'
    ACTION_FALLBACK = 'fallback'
    ACTION_UPDATE = 'update'

    ACTION_CHOICES = [
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_LOGIN_FAILED, 'Login Failed'),
        (ACTION_REGISTER, 'Registration'),
        (ACTION_VERIFY, 'Verification'),
        (ACTION_OVERRIDE, 'Override'),
        (ACTION_USER_CREATE, 'User Created'),
        (ACTION_USER_UPDATE, 'User Updated'),
        (ACTION_USER_DEACTIVATE, 'User Deactivated'),
        (ACTION_CONFIG_CHANGE, 'Config Changed'),
        (ACTION_FALLBACK, 'Fallback Triggered'),
        (ACTION_UPDATE, 'Record Updated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fans_audit_logs'
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user.username if self.user else 'Anonymous'
        return f'[{self.timestamp}] {user_str} - {self.action}'

    @classmethod
    def log(cls, action, user=None, target_type='', target_id='', details=None, request=None):
        ip = None
        ua = ''
        if request:
            ip = get_client_ip(request)
            ua = request.META.get('HTTP_USER_AGENT', '')[:500]
        return cls.objects.create(
            user=user,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else '',
            details=details or {},
            ip_address=ip,
            user_agent=ua,
        )


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
