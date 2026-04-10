from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from apps.aziende.models import Azienda, Sede

from .models import Fattura, FatturaVoce, Preventivo, PreventivoVoce


class BaseVociFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        righe_attive = 0
        for form in self.forms:
            cleaned = getattr(form, 'cleaned_data', None) or {}
            if not cleaned or cleaned.get('DELETE'):
                continue
            if cleaned.get('descrizione'):
                righe_attive += 1
        if righe_attive == 0:
            raise ValidationError('Inserisci almeno una riga di dettaglio.')


class DocumentoCommercialeFormMixin:
    condizioni_field_name = 'condizioni_pagamento_riservate'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['azienda'].queryset = Azienda.objects.order_by('ragione_sociale')

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('style', 'width:auto; height:auto')
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()

        if self.condizioni_field_name in self.fields:
            self.fields[self.condizioni_field_name].required = False

        azienda = self._selected_azienda()
        if azienda and not self.instance.pk and not self.initial.get(self.condizioni_field_name):
            self.initial[self.condizioni_field_name] = azienda.condizioni_pagamento_riservate

    def clean(self):
        cleaned = super().clean()
        azienda = cleaned.get('azienda')
        condizioni = cleaned.get(self.condizioni_field_name)
        if azienda and not condizioni:
            cleaned[self.condizioni_field_name] = azienda.condizioni_pagamento_riservate
        return cleaned

    def _selected_azienda(self):
        if getattr(self.instance, 'azienda_id', None):
            return self.instance.azienda
        if self.is_bound:
            azienda_id = self.data.get(self.add_prefix('azienda'))
            if azienda_id:
                return Azienda.objects.filter(pk=azienda_id).first()
        initial_azienda = self.initial.get('azienda')
        if isinstance(initial_azienda, Azienda):
            return initial_azienda
        if initial_azienda:
            return Azienda.objects.filter(pk=initial_azienda).first()
        return None


class PreventivoForm(DocumentoCommercialeFormMixin, forms.ModelForm):
    class Meta:
        model = Preventivo
        fields = [
            'numero_preventivo',
            'data_preventivo',
            'azienda',
            'oggetto',
            'descrizione_oggetto',
            'note',
            'riferimento_commerciale',
            'assistente_tecnico',
            'giorni_lavorativi',
            'durata_offerta',
            'condizioni_pagamento_riservate',
            'aliquota_iva',
        ]
        labels = {
            'numero_preventivo': 'N. preventivo',
            'data_preventivo': 'Data preventivo',
            'azienda': 'Cliente',
            'descrizione_oggetto': 'Descrizione oggetto',
            'riferimento_commerciale': 'Referente commerciale',
            'assistente_tecnico': 'Assistente tecnico',
            'giorni_lavorativi': 'Giorni lavorativi',
            'durata_offerta': 'Durata offerta',
            'condizioni_pagamento_riservate': 'Condizioni di pagamento riservate',
            'aliquota_iva': 'IVA (%)',
        }
        widgets = {
            'data_preventivo': forms.DateInput(attrs={'type': 'date'}),
            'durata_offerta': forms.DateInput(attrs={'type': 'date'}),
            'descrizione_oggetto': forms.Textarea(attrs={'rows': 3}),
            'note': forms.Textarea(attrs={'rows': 3}),
            'condizioni_pagamento_riservate': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.initial.get('numero_preventivo'):
            prossimo = Preventivo.objects.aggregate(max_numero=Max('numero_preventivo'))['max_numero'] or 0
            self.fields['numero_preventivo'].initial = prossimo + 1


class FatturaForm(DocumentoCommercialeFormMixin, forms.ModelForm):
    class Meta:
        model = Fattura
        fields = [
            'anno_fattura',
            'prefisso_numero',
            'numero_progressivo',
            'data_fattura',
            'data_accettazione_campione',
            'azienda',
            'categoria_merceologica',
            'indirizzo_fatturazione',
            'cap_fatturazione',
            'comune_fatturazione',
            'provincia_fatturazione',
            'condizioni_pagamento_riservate',
            'modalita_pagamento',
            'aliquota_iva',
            'esente_iva',
            'esigibilita_iva',
            'gdd',
            'fine_mese',
            'scadenza',
            'banca_appoggio',
            'causale',
            'note',
            'inviata_il',
            'data_incasso',
        ]
        labels = {
            'anno_fattura': 'Anno fattura',
            'prefisso_numero': 'Prefisso',
            'numero_progressivo': 'N. fattura',
            'data_fattura': 'Data fattura',
            'data_accettazione_campione': 'Data accettazione campione',
            'azienda': 'Intestatario',
            'categoria_merceologica': 'Categoria merceologica',
            'indirizzo_fatturazione': 'Indirizzo',
            'cap_fatturazione': 'CAP',
            'comune_fatturazione': 'Comune',
            'provincia_fatturazione': 'Provincia',
            'condizioni_pagamento_riservate': 'Condizioni di pagamento riservate',
            'modalita_pagamento': 'Modalità di pagamento',
            'aliquota_iva': 'IVA (%)',
            'esente_iva': 'Esente IVA',
            'esigibilita_iva': 'Esigibilità IVA',
            'gdd': 'G.D.D.',
            'fine_mese': 'Fine mese',
            'banca_appoggio': 'Banca appoggio',
            'causale': 'Causale documento',
            'note': 'Note interne',
            'inviata_il': 'Inviata il',
            'data_incasso': 'Incassata il',
        }
        widgets = {
            'data_fattura': forms.DateInput(attrs={'type': 'date'}),
            'data_accettazione_campione': forms.DateInput(attrs={'type': 'date'}),
            'scadenza': forms.DateInput(attrs={'type': 'date'}),
            'inviata_il': forms.DateInput(attrs={'type': 'date'}),
            'data_incasso': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
            'condizioni_pagamento_riservate': forms.Textarea(attrs={'rows': 3}),
            'causale': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['anno_fattura'].initial = self.initial.get('anno_fattura') or timezone.localdate().year
            if not self.initial.get('prefisso_numero'):
                self.fields['prefisso_numero'].initial = 'FPR'
            if not self.initial.get('numero_progressivo'):
                anno = self.fields['anno_fattura'].initial
                prefisso = self.fields['prefisso_numero'].initial or 'FPR'
                prossimo = Fattura.objects.filter(
                    anno_fattura=anno,
                    prefisso_numero=prefisso,
                ).aggregate(max_numero=Max('numero_progressivo'))['max_numero'] or 0
                self.fields['numero_progressivo'].initial = prossimo + 1
            self._apply_company_billing_defaults()

    def _apply_company_billing_defaults(self):
        azienda = self._selected_azienda()
        if not azienda:
            return
        sede = Sede.objects.filter(azienda=azienda).order_by('id').first()
        defaults = {
            'indirizzo_fatturazione': sede.indirizzo if sede else '',
            'cap_fatturazione': sede.cap if sede else '',
            'comune_fatturazione': sede.citta if sede else '',
            'provincia_fatturazione': sede.provincia if sede else '',
        }
        for field_name, default_value in defaults.items():
            if not self.initial.get(field_name):
                self.fields[field_name].initial = default_value


class PreventivoVoceForm(forms.ModelForm):
    class Meta:
        model = PreventivoVoce
        fields = ['descrizione', 'quantita', 'costo_unitario', 'sconto_percentuale', 'ordine']
        widgets = {
            'descrizione': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': "Prima riga: attivita. Righe successive: dettaglio attivita.",
            }),
            'ordine': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'ordine':
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()


class FatturaVoceForm(forms.ModelForm):
    class Meta:
        model = FatturaVoce
        fields = ['descrizione', 'quantita', 'costo_unitario', 'sconto_percentuale', 'ordine']
        widgets = {
            'ordine': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'ordine':
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()


PreventivoVoceFormSet = inlineformset_factory(
    Preventivo,
    PreventivoVoce,
    form=PreventivoVoceForm,
    formset=BaseVociFormSet,
    extra=1,
    can_delete=True,
)

FatturaVoceFormSet = inlineformset_factory(
    Fattura,
    FatturaVoce,
    form=FatturaVoceForm,
    formset=BaseVociFormSet,
    extra=1,
    can_delete=True,
)
