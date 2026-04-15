from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from . import views as fans_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('beneficiaries.urls')),
    path('verification/', include('verification.urls')),
    path('logs/', include('logs.urls')),
    # Health + system info (installer / superuser tools)
    path('health/', fans_views.health_check, name='health_check'),
    path('health/network/', fans_views.health_network, name='health_network'),
    path('help/connect/', fans_views.connect_help, name='connect_help'),
    path('system/connection/', fans_views.system_connection, name='system_connection'),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]

# Serve uploaded media files through Django only in local development.
# In centralized server deployments, configure nginx to serve /media/ directly:
#   location /media/ { alias /path/to/fans-c/media/; }
# This avoids routing large image files through the Python process.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
