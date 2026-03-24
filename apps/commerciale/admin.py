from django.contrib import admin

from .models import Fattura, FatturaVoce, Preventivo, PreventivoVoce


class PreventivoVoceInline(admin.TabularInline):
    model = PreventivoVoce
    extra = 0


@admin.register(Preventivo)
class PreventivoAdmin(admin.ModelAdmin):
    list_display = ['numero_formattato', 'data_preventivo', 'azienda', 'totale_imponibile', 'totale_complessivo']
    list_filter = ['data_preventivo', 'azienda']
    search_fields = ['numero_preventivo', 'azienda__ragione_sociale', 'oggetto']
    inlines = [PreventivoVoceInline]


class FatturaVoceInline(admin.TabularInline):
    model = FatturaVoce
    extra = 0


@admin.register(Fattura)
class FatturaAdmin(admin.ModelAdmin):
    list_display = [
        'numero_completo',
        'data_fattura',
        'data_accettazione_campione',
        'azienda',
        'totale_imponibile',
        'totale_complessivo',
    ]
    list_filter = ['anno_fattura', 'azienda']
    search_fields = ['numero_progressivo', 'azienda__ragione_sociale']
    inlines = [FatturaVoceInline]
