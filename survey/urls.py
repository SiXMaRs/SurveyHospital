from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)
from django.urls import path
from . import views
app_name = 'survey'
urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('token/', TokenObtainPairView.as_view(), name = 'token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name ='token_refresh'), 
    path('register-manager/', views.ManagerCreateView.as_view(), name = 'register_manager'),
    path('user/me/', views.UserMeView.as_view(), name = 'user_me'),
    path('service-points/', views.ServicePointListView.as_view(), name='servicepoint-list'),
    path('<str:service_point_id>/', views.survey_display_view, name='survey_display'),
    path('submit/<int:version_id>/',views.survey_submit_view,name='survey_submit'),
    path('export/csv/', views.export_responses_csv, name='export_csv'),
    path('export/excel/', views.export_responses_excel, name='export_excel'),
    path('<int:pk>/', views.survey_display_view, name='survey_display'),    
    

]