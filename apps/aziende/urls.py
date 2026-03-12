from django.urls import path
from . import views

urlpatterns = [
    # Admin
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('dashboard/aziende/<int:pk>/contratto/', views.AdminAggiornaContrattoView.as_view(), name='admin_azienda_contratto'),
    path('dashboard/aziende/nuova/', views.AdminCreaAziendaView.as_view(), name='admin_crea_azienda'),
    path('dashboard/lavoratori/', views.AdminLavoratoriView.as_view(), name='admin_lavoratori'),
    path('dashboard/lavoratori/<int:pk>/', views.AdminLavoratoreDetailView.as_view(), name='admin_lavoratore_detail'),
    path('dashboard/lavoratori/<int:pk>/documento/', views.AdminCaricaDocumentoView.as_view(), name='admin_carica_documento'),
    path('dashboard/lavoratori/<int:pk>/esito/', views.AdminRegistraEsitoView.as_view(), name='admin_registra_esito'),

    # Azienda
    path('azienda/dashboard/', views.AziendaDashboardView.as_view(), name='azienda_dashboard'),
    path('azienda/lavoratori/nuovo/', views.AziendaLavoratoreCreateView.as_view(), name='azienda_lavoratore_nuovo'),
    path('azienda/lavoratori/<int:pk>/', views.AziendaLavoratoreDetailView.as_view(), name='azienda_lavoratore'),
    path('azienda/lavoratori/<int:pk>/modifica/', views.AziendaLavoratoreEditView.as_view(), name='azienda_lavoratore_modifica'),

    # Operatore
    path('operatore/dashboard/', views.OperatoreDashboardView.as_view(), name='operatore_dashboard'),
    path('dashboard/lavoratori/<int:pk>/crea-account/', views.AdminCreaAccountOperatoreView.as_view(), name='admin_crea_account_operatore'),
]
