from django.urls import path

from . import views

app_name = 'claim'

urlpatterns = [
    path('reclamar/<int:place_id>/', views.start_claim, name='start'),
    path('reclamar/verificar/<str:token>/', views.verify_claim, name='verify'),

    path('panel/<int:place_id>/', views.dashboard, name='dashboard'),
    path('panel/<int:place_id>/servicios/nuevo/',
         views.service_create, name='service_create'),
    path('panel/<int:place_id>/servicios/<int:pk>/editar/',
         views.service_edit, name='service_edit'),
    path('panel/<int:place_id>/servicios/<int:pk>/borrar/',
         views.service_delete, name='service_delete'),
]
