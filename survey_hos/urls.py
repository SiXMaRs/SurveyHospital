from django.contrib import admin
from django.urls import path, include
from survey import views as survey_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("__reload__/", include("django_browser_reload.urls")),
    path('survey/', include('survey.urls')),
    
    path('', survey_views.Home, name='homepage'),
    path('login/', auth_views.LoginView.as_view(
        template_name = 'survey/login.html',
        redirect_authenticated_user = True,
        
        next_page = 'survey:dashboard'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        next_page = 'homepage'
    ), name = 'logout'),
]
