from django.urls import path, include
from . import views
# ตรวจสอบว่าติดตั้ง djangorestframework-simplejwt แล้ว
# from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)

app_name = 'survey'

# --- กลุ่ม URL สำหรับ Admin UI ---
admin_urlpatterns = [
    # Survey CRUD
    path('surveys/', views.survey_list_view, name='survey_list'),
    # path('surveys/add/', ...), # ลบออกแล้วเพราะใช้ Modal
    path('surveys/edit/<int:pk>/', views.survey_edit_view, name='survey_edit'),
    path('surveys/delete/<int:pk>/', views.SurveyDeleteView.as_view(), name='survey_delete'),
    path('assessments/', views.assessment_results_view, name='assessment_results'),
    path('assessments/suggestions/', views.suggestion_list_view, name='suggestion_list'),
    path('notification/read/<int:notif_id>/', views.mark_notification_read, name='read_notification'),
    path('api/check-notifications/', views.check_notifications, name='check_notifications'),

    # Question CRUD
    path('surveys/<int:survey_id>/questions/', views.question_list_view, name='question_list'),
    path('questions/edit/<int:pk>/', views.QuestionUpdateView.as_view(), name='question_edit'),
    path('questions/delete/<int:pk>/', views.QuestionDeleteView.as_view(), name='question_delete'),

    # Service Point / Group CRUD
    path('service-points/', views.service_point_list_view, name='service_point_list'),
    path('service-points/add/', views.service_point_create_view, name='service_point_add'),
    path('service-points/edit/<int:pk>/', views.service_point_edit_view, name='service_point_edit'),
    path('service-points/delete/<int:pk>/', views.service_point_delete_view, name='service_point_delete'),
    
    path('service-groups/add/', views.service_group_create_view, name='service_group_add'),
    path('service-groups/edit/<int:pk>/', views.service_group_edit_view, name='service_group_edit'),
    path('service-groups/delete/<int:pk>/', views.service_group_delete_view, name='service_group_delete'),

    # Manager CRUD
    path('managers/', views.manager_list_view, name='manager_list'),
    path('managers/add/', views.manager_create_view, name='manager_add'),
    path('managers/edit/<int:pk>/', views.manager_edit_view, name='manager_edit'),
    path('managers/delete/<int:pk>/', views.manager_delete_view, name='manager_delete'),
]

# --- กลุ่ม URL สำหรับ Kiosk Flow ---
kiosk_urlpatterns = [
    # เปลี่ยน parameter ให้ตรงกับ views.py ที่เราจะแก้ (survey_id)
    path('submit/<int:survey_id>/', views.survey_submit_view, name='survey_submit'),
    path('<int:service_point_id>/thank-you/', views.kiosk_thank_you_view, name='kiosk_thank_you'),
    path('<int:service_point_id>/display/', views.survey_display_view, name='survey_display'),
    path('<int:service_point_id>/info/', views.kiosk_user_info_view, name='kiosk_user_info'),
    path('<int:service_point_id>/', views.kiosk_welcome_view, name='kiosk_welcome'),
]

# --- URL หลัก ---
urlpatterns = [
    path('index/', views.index , name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Export
    path('export/csv/', views.export_responses_csv, name='export_csv'),
    path('export/excel/', views.export_responses_excel, name='export_excel'),
    path('export/csv/', views.export_responses_csv, name='export_responses_csv'),
    path('export/excel/', views.export_responses_excel, name='export_excel'),
    
    # Include Groups
    path('', include(admin_urlpatterns)),
    path('kiosk/', include(kiosk_urlpatterns)), # เพิ่ม prefix 'kiosk/' เพื่อไม่ให้ชนกับ admin
]