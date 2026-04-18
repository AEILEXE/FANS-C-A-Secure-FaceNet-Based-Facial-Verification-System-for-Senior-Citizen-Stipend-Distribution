from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Password management
    path('password/change/', views.change_password, name='change_password'),
    path('password/reset/<int:user_id>/', views.admin_reset_password, name='admin_reset_password'),
]
