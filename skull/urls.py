from django.urls import path, include
from . import views
import django_eventstream

app_name = 'skull'

urlpatterns = [
    path('', views.index, name='index'),
    path('<str:tag>/', views.game, name='game'),
]
