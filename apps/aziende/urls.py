from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('dashboard/lavoratori/', views.AdminLavoratoriView.as_view(), name='admin_lavoratori'),
    path('azienda/dashboard/', views.AziendaDashboardView.as_view(), name='azienda_dashboard'),
    path('azienda/lavoratore/<int:pk>/', views.AziendaLavoratoreDetailView.as_view(), name='azienda_lavoratore'),
    path('operatore/dashboard/', views.OperatoreDashboardView.as_view(), name='operatore_dashboard'),
]