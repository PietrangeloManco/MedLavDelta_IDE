from django.contrib import admin
from .models import CartellaClinica, DocumentoSanitario, EsitoIdoneita


class DocumentoInline(admin.TabularInline):
    model = DocumentoSanitario
    extra = 0


@admin.register(CartellaClinica)
class CartellaClinicaAdmin(admin.ModelAdmin):
    list_display = ['lavoratore', 'data_apertura']
    inlines = [DocumentoInline]


@admin.register(DocumentoSanitario)
class DocumentoSanitarioAdmin(admin.ModelAdmin):
    list_display = ['titolo', 'tipo', 'cartella', 'data']
    list_filter = ['tipo']


@admin.register(EsitoIdoneita)
class EsitoIdoneitaAdmin(admin.ModelAdmin):
    list_display = ['lavoratore', 'esito', 'mansione', 'data_visita', 'data_scadenza', 'comunicato_azienda']
    list_filter = ['esito', 'comunicato_azienda']