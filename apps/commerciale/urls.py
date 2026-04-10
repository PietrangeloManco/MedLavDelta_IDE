from django.urls import path

from . import views


urlpatterns = [
    path('dashboard/preventivi/', views.AdminPreventiviListView.as_view(), name='admin_preventivi'),
    path('dashboard/preventivi/nuovo/', views.AdminPreventivoCreateView.as_view(), name='admin_preventivo_nuovo'),
    path('dashboard/preventivi/<int:pk>/modifica/', views.AdminPreventivoUpdateView.as_view(), name='admin_preventivo_modifica'),
    path('dashboard/preventivi/<int:pk>/pdf/', views.AdminPreventivoPdfView.as_view(), name='admin_preventivo_pdf'),
    path('dashboard/fatture/', views.AdminFattureListView.as_view(), name='admin_fatture'),
    path('dashboard/fatture/nuova/', views.AdminFatturaCreateView.as_view(), name='admin_fattura_nuova'),
    path('dashboard/fatture/<int:pk>/modifica/', views.AdminFatturaUpdateView.as_view(), name='admin_fattura_modifica'),
    path('dashboard/fatture/<int:pk>/pdf/', views.AdminFatturaPdfView.as_view(), name='admin_fattura_pdf'),
    path('dashboard/fatture/<int:pk>/xml/', views.AdminFatturaXmlView.as_view(), name='admin_fattura_xml'),
    path(
        'dashboard/api/aziende/<int:pk>/condizioni-pagamento/',
        views.AdminAziendaCondizioniPagamentoApiView.as_view(),
        name='admin_api_azienda_condizioni_pagamento',
    ),
]
