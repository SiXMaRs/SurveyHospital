from django.urls import path
from . import views

app_name = 'manager'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),

    path('managers/', views.manager_list_view, name='manager_list'),

    path('surveys/', views.survey_list_view, name='survey_list'),
    path('surveys/delete/<int:pk>/', views.survey_delete_view, name='survey_delete'),
    path('surveys/edit/<int:pk>/', views.survey_edit_view, name='survey_edit'),

    # Question Management
    path('surveys/<int:survey_id>/questions/', views.question_list_view, name='question_list'),
    path('questions/edit/<int:pk>/', views.QuestionUpdateView.as_view(), name='question_edit'),
    path('questions/delete/<int:pk>/', views.QuestionDeleteView.as_view(), name='question_delete'),

    path('response/', views.manager_assessment_results_view, name='assessment_results'),
    path('suggestions/', views.suggestion_list_view, name='suggestion_list'),
]
