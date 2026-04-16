from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """Allow management-level roles: Head Barangay, IT/Admin, and legacy admin.
    Use this for pages that both operational and technical admins can access."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin:
            messages.error(request, 'Admin access required.')
            return redirect('beneficiaries:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def it_admin_required(view_func):
    """Restrict to technical administrators only (IT/Admin or legacy admin role).
    Head Barangay and Staff are denied — use for system diagnostics and
    network/connection pages that non-technical users should never see.
    Django is_superuser does NOT bypass this check; access is role-based only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_it:
            messages.error(request, 'IT/Admin access required.')
            return redirect('beneficiaries:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_custom(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper
