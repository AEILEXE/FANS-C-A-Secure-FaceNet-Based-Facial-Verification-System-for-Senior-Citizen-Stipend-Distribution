from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render

from fans.context_processors import _detect_lan_ip


def health_check(request):
    """GET /health/ — returns {"status": "ok"} for uptime monitoring."""
    return JsonResponse({'status': 'ok'})


def health_network(request):
    """
    GET /health/network/ — returns LAN IP and connection info as JSON.
    No login required; used by the installer during setup to verify
    that the server is reachable on the LAN.
    """
    lan_ip = _detect_lan_ip()
    return JsonResponse({
        'status': 'ok',
        'lan_ip': lan_ip,
        'reachable_from_lan': lan_ip is not None,
        'scheme': 'https' if request.is_secure() else 'http',
        'host': request.get_host(),
    })


@login_required
def connect_help(request):
    """
    GET /help/connect/ — connection guide page.
    Restricted to IT/Admin (and superuser); Head Barangay and Staff are denied
    because this page contains technical network details they don't need.
    """
    if not request.user.is_admin_it:
        raise PermissionDenied
    return render(request, 'help/connect.html')


@login_required
def system_connection(request):
    """
    GET /system/connection/ — full technical status page, IT/Admin only.
    Shows effective ALLOWED_HOSTS, CSRF origins, LAN IP, access mode, and
    troubleshooting hints.  Not linked from Head Barangay or Staff UI.
    """
    if not request.user.is_admin_it:
        raise PermissionDenied
    from django.conf import settings
    try:
        csrf_origins = settings.CSRF_TRUSTED_ORIGINS
    except AttributeError:
        csrf_origins = None
    return render(request, 'system/connection.html', {
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'csrf_origins': csrf_origins,
        'secure_cookies': settings.SESSION_COOKIE_SECURE,
        'debug': settings.DEBUG,
        'lan_ip': _detect_lan_ip(),
    })
