from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)
from django.urls import path
from . import views
app_name = 'survey'
urlpatterns = [
    path('index/', views.index , name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    path('token/', TokenObtainPairView.as_view(), name = 'token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name ='token_refresh'), 
    path('register-manager/', views.ManagerCreateView.as_view(), name = 'register_manager'),
    path('user/me/', views.UserMeView.as_view(), name = 'user_me'),
    
    path('export/csv/', views.export_responses_csv, name='export_csv'),
    path('export/excel/', views.export_responses_excel, name='export_excel'),

    path('management/', views.QuestionListView.as_view(), name='survey_management'),
    path('questions/add/', views.QuestionCreateView.as_view(), name='question_add'),
    path('questions/<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='question_edit'),
    path('questions/<int:pk>/delete/', views.QuestionDeleteView.as_view(), name='question_delete'), # (เพิ่ม)

    # --- 6. CRUD: Versions ---
    path('versions/add/', views.SurveyVersionCreateView.as_view(), name='version_add'),
    path('versions/<int:pk>/edit/', views.SurveyVersionUpdateView.as_view(), name='version_edit'),

    # --- 7. CRUD: Surveys ---
    path('surveys/add/', views.SurveyCreateView.as_view(), name='survey_add'),
    path('surveys/<int:pk>/edit/', views.SurveyUpdateView.as_view(), name='survey_edit'),

    path('service-points/', views.ServicePointListView.as_view(), name='servicepoint-list'),
    path('<str:service_point_id>/', views.survey_display_view, name='survey_display'),

    path('submit/<int:version_id>/',views.survey_submit_view,name='survey_submit'),
    path('<int:pk>/', views.survey_display_view, name='survey_display'),    
    

]