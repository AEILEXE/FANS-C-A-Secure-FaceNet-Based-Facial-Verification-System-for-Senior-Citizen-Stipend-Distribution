from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from .models import AuditLog
from verification.models import VerificationAttempt


@login_required
def audit_log_list(request):
    logs = AuditLog.objects.select_related('user').order_by('-timestamp')

    # Filters
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')

    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)

    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)

    return render(request, 'logs/audit_logs.html', {
        'logs': logs_page,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'action_choices': AuditLog.ACTION_CHOICES,
    })


@login_required
def verification_log_list(request):
    if not request.user.is_admin:
        # Staff see only their own
        attempts = VerificationAttempt.objects.filter(
            performed_by=request.user
        ).select_related('beneficiary', 'performed_by')
    else:
        attempts = VerificationAttempt.objects.select_related('beneficiary', 'performed_by')

    # Filters
    decision_filter = request.GET.get('decision', '')
    if decision_filter:
        attempts = attempts.filter(decision=decision_filter)

    attempts = attempts.order_by('-timestamp')
    paginator = Paginator(attempts, 50)
    page = request.GET.get('page', 1)
    attempts_page = paginator.get_page(page)

    return render(request, 'logs/verification_logs.html', {
        'attempts': attempts_page,
        'decision_filter': decision_filter,
        'decision_choices': VerificationAttempt.DECISION_CHOICES,
    })
