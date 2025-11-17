from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)
from django.urls import path
from . import views
app_name = 'survey'
urlpatterns = [
    path('index/', views.index , name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    path('export/csv/', views.export_responses_csv, name='export_csv'),
    path('export/excel/', views.export_responses_excel, name='export_excel'),

    path('service-points/', views.service_point_list_view, name='service_point_list'),
    path('service-points/add/', views.service_point_create_view, name='service_point_add'),
    path('service-points/<int:pk>/edit/', views.service_point_edit_view, name='service_point_edit'),
    path('service-points/<int:pk>/delete/', views.service_point_delete_view, name='service_point_delete'),
    path('service-groups/add/', views.service_group_create_view, name='service_group_add'),
    path('service-groups/<int:pk>/edit/', views.service_group_edit_view, name='service_group_edit'),
    path('service-groups/<int:pk>/delete/', views.service_group_delete_view, name='service_group_delete'),

    path('managers/', views.manager_list_view, name='manager_list'),
    path('managers/add/', views.manager_create_view, name='manager_add'),
    path('managers/<int:pk>/edit/', views.manager_edit_view, name='manager_edit'),
    path('managers/<int:pk>/delete/', views.manager_delete_view, name='manager_delete'),

    path('surveys/', views.SurveyListView.as_view(), name='survey_list'),
    path('surveys/add/', views.SurveyCreateView.as_view(), name='survey_add'),
    path('surveys/<int:pk>/edit/', views.SurveyUpdateView.as_view(), name='survey_edit'),
    path('surveys/<int:pk>/delete/', views.SurveyDeleteView.as_view(), name='survey_delete'),
    path('surveys/<int:survey_id>/versions/add/', views.version_create_view, name='version_add'),
    path('surveys/<int:survey_id>/versions/', views.survey_version_list_view, name='survey_version_list'),
    path('versions/<int:version_id>/questions/', views.question_list_view, name='question_list'),
    path('versions/<int:version_id>/questions/add/', views.question_create_view, name='question_add'),
    path('versions/<int:pk>/edit/', views.version_edit_view, name='version_edit')

]