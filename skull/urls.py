from django.urls import path
from . import views

app_name = 'skull'

urlpatterns = [
    path('', views.index, name='index'),
    path('<str:tag>/', views.game, name='game'),
]
