from django.urls import path
from . import views

app_name = 'verification'

urlpatterns = [
    path('', views.verify_select, name='verify_select'),
    path('start/<uuid:pk>/', views.verify_start, name='verify_start'),
    path('check-liveness/', views.verify_check_liveness, name='verify_check_liveness'),
    path('submit/', views.verify_submit, name='verify_submit'),
    path('result/<uuid:attempt_id>/', views.verify_result, name='verify_result'),
    path('fallback/<uuid:attempt_id>/', views.verify_fallback, name='verify_fallback'),
    path('override/<uuid:attempt_id>/', views.admin_override, name='admin_override'),
    path('manual-review/', views.manual_review_list, name='manual_review'),
    path('manual-review/verify/<uuid:request_id>/', views.manual_verify_review, name='manual_verify_review'),
    path('manual-review/face-update/<uuid:request_id>/', views.face_update_review, name='face_update_review'),
    path('manual-review/special-claim/<uuid:request_id>/', views.special_claim_review, name='special_claim_review'),
    path('special-claim-request/<uuid:pk>/', views.special_claim_request, name='special_claim_request'),
    path('config/', views.verify_config, name='config'),
    path('stipend/', views.stipend_list, name='stipend_list'),
    path('stipend/create/', views.stipend_create, name='stipend_create'),
    path('stipend/<uuid:event_id>/edit/', views.stipend_edit, name='stipend_edit'),
    path('stipend/<uuid:event_id>/delete/', views.stipend_delete, name='stipend_delete'),
    path('update-face/<uuid:pk>/', views.update_face_data, name='update_face_data'),
    path('update-face/<uuid:pk>/submit/', views.update_face_submit, name='update_face_submit'),
]
