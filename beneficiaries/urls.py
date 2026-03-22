from django.urls import path
from . import views

app_name = 'beneficiaries'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('beneficiaries/', views.beneficiary_list, name='beneficiary_list'),
    path('beneficiaries/<uuid:pk>/', views.beneficiary_detail, name='beneficiary_detail'),
    path('beneficiaries/<uuid:pk>/edit/', views.beneficiary_edit, name='beneficiary_edit'),
    path('beneficiaries/<uuid:pk>/deactivate/', views.beneficiary_deactivate, name='beneficiary_deactivate'),
    path('beneficiaries/<uuid:pk>/reactivate/', views.beneficiary_reactivate, name='beneficiary_reactivate'),
    path('register/step1/', views.register_step1, name='register_step1'),
    path('register/step2/', views.register_step2, name='register_step2'),
    path('register/step3/', views.register_step3, name='register_step3'),
    path('register/face/', views.register_face, name='register_face'),
    path('register/submit-face/', views.register_submit_face, name='register_submit_face'),
    path('beneficiaries/<uuid:pk>/representative/add/', views.add_representative, name='add_representative'),
    path('beneficiaries/<uuid:pk>/representative/<uuid:rep_pk>/deactivate/', views.deactivate_representative, name='deactivate_representative'),
    path('api/municipalities/', views.address_municipalities, name='address_municipalities'),
    path('api/barangays/', views.address_barangays, name='address_barangays'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
]
