from django.contrib import admin
from django.urls import path
from monitor import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('api/latest/', views.latest, name='api_latest'),
    path('api/history/', views.history, name='api_history'),
    path('api/control/', views.control, name='api_control'),
]
