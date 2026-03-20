from django.urls import path
from . import views

app_name = 'logs'

urlpatterns = [
    path('audit/', views.audit_log_list, name='audit_logs'),
    path('verification/', views.verification_log_list, name='verification_logs'),
]
