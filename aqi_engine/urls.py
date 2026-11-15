from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='dashboard'), name='logout'),
    path('register/', views.register_view, name='register'),
    path('workspace/', views.scientist_workspace_view, name='scientist_workspace'),
    path('algorithms/visualize/', views.algorithm_visualizer_view, name='algorithm_visualizer'),
    path('validation/', views.verifier_queue_view, name='verifier_queue'),
]

