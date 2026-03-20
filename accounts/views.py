from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .forms import LoginForm
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
