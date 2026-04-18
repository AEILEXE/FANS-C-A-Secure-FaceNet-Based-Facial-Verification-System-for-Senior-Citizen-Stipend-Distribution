from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .forms import LoginForm, PasswordChangeForm, AdminPasswordResetForm
from .models import CustomUser
from logs.models import AuditLog


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('beneficiaries:dashboard')

    form = LoginForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            AuditLog.log(
                action=AuditLog.ACTION_LOGIN,
                user=user,
                details={'username': user.username},
                request=request
            )
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('beneficiaries:dashboard')
        else:
            username = request.POST.get('username', '')
            AuditLog.log(
                action=AuditLog.ACTION_LOGIN_FAILED,
                details={'username': username, 'reason': 'Invalid credentials'},
                request=request
            )
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    AuditLog.log(
        action=AuditLog.ACTION_LOGOUT,
        user=request.user,
        details={'username': request.user.username},
        request=request
    )
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


# ─── Password Management ──────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET', 'POST'])
def change_password(request):
    """Any logged-in user may change their own password."""
    form = PasswordChangeForm(user=request.user, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        # Keep the session alive after password change so the user isn't logged out.
        update_session_auth_hash(request, form.user)
        AuditLog.log(
            action=AuditLog.ACTION_PASSWORD_CHANGE,
            user=request.user,
            target_type='CustomUser',
            target_id=request.user.id,
            details={'username': request.user.username},
            request=request,
        )
        messages.success(request, 'Your password has been changed successfully.')
        return redirect('beneficiaries:dashboard')

    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def admin_reset_password(request, user_id):
    """
    Head Barangay or IT/Admin resets another user's password.
    Staff may NOT use this view. A user cannot reset their own password here
    (use change_password instead).
    """
    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    target_user = get_object_or_404(CustomUser, pk=user_id)

    if target_user == request.user:
        messages.info(request, 'Use "Change Password" to update your own password.')
        return redirect('accounts:change_password')

    # IT/Admin cannot reset another IT/Admin or Head Barangay account;
    # only Head Barangay can reset any account.
    if not request.user.is_head_barangay and target_user.is_admin:
        messages.error(
            request,
            'Only the Head Barangay can reset passwords for admin-level accounts.'
        )
        return redirect('beneficiaries:user_list')

    form = AdminPasswordResetForm(data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        target_user.set_password(form.cleaned_data['new_password1'])
        target_user.save()
        AuditLog.log(
            action=AuditLog.ACTION_PASSWORD_RESET,
            user=request.user,
            target_type='CustomUser',
            target_id=target_user.id,
            details={
                'reset_by': request.user.username,
                'target_user': target_user.username,
                'target_role': target_user.role,
            },
            request=request,
        )
        messages.success(
            request,
            f'Password for {target_user.get_full_name() or target_user.username} has been reset.'
        )
        return redirect('beneficiaries:user_list')

    return render(request, 'accounts/admin_reset_password.html', {
        'form': form,
        'target_user': target_user,
    })
