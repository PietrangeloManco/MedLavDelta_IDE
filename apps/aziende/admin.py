from django.contrib import admin
from .models import Azienda, Sede, Lavoratore


class SedeInline(admin.TabularInline):
    model = Sede
    extra = 1


class LavoratoreInline(admin.TabularInline):
    model = Lavoratore
    extra = 0
    fields = ['cognome', 'nome', 'mansione', 'sede', 'attivo']


@admin.register(Azienda)
class AziendaAdmin(admin.ModelAdmin):
    list_display = ['ragione_sociale', 'partita_iva', 'email_contatto']
    inlines = [SedeInline, LavoratoreInline]


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ['nome', 'azienda', 'citta']
    list_filter = ['azienda']


@admin.register(Lavoratore)
class LavoratoreAdmin(admin.ModelAdmin):
    list_display = ['cognome', 'nome', 'azienda', 'sede', 'mansione', 'attivo']
    list_filter = ['azienda', 'attivo']
    search_fields = ['cognome', 'nome', 'codice_fiscale']