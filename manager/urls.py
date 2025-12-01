from django.urls import path
from . import views

app_name = 'manager'

urlpatterns = [
    path('notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),

    path('dashboard/', views.dashboard_view, name='dashboard'),

    path('managers/', views.manager_list_view, name='manager_list'),

    path('surveys/', views.survey_list_view, name='survey_list'),
    path('surveys/delete/<int:pk>/', views.survey_delete_view, name='survey_delete'),
    path('surveys/edit/<int:pk>/', views.survey_edit_view, name='survey_edit'),

     # Export
    # === Export (แก้ไขให้เรียก function ของ Manager) ===
    # 1. Dashboard Summary
    path('export/dashboard/summary/', views.export_manager_dashboard_summary, name='export_dashboard_summary'),
    
    # 2. Assessment Data (Excel & CSV)
    path('export/assessment/excel/', views.export_manager_assessment_excel, name='export_assessment_excel'),
    path('export/assessment/csv/', views.export_manager_assessment_csv, name='export_assessment_csv'),
    
    # 3. Suggestion Data (Excel & CSV)
    path('export/suggestion/excel/', views.export_manager_suggestion_excel, name='export_suggestion_excel'),
    path('export/suggestion/csv/', views.export_manager_suggestion_csv, name='export_suggestion_csv'),

    # Question Management
    path('surveys/<int:survey_id>/questions/', views.question_list_view, name='question_list'),
    path('questions/edit/<int:pk>/', views.QuestionUpdateView.as_view(), name='question_edit'),
    path('questions/delete/<int:pk>/', views.QuestionDeleteView.as_view(), name='question_delete'),

    path('response/', views.manager_assessment_results_view, name='assessment_results'),
    path('suggestions/', views.suggestion_list_view, name='suggestion_list'),
]
