from django import forms

from apps.accounts.models import CustomUser

from .models import DocumentoAziendale, Lavoratore, Sede
from .validators import (
    COMPANY_DOCUMENT_MAX_UPLOAD_SIZE,
    COMPANY_LOGO_MAX_UPLOAD_SIZE,
    validate_company_document_upload,
    validate_company_logo_upload,
)


class CreaAziendaForm(forms.Form):
    # Dati account
    email = forms.EmailField(label='Email account azienda')

    # Dati azienda
    ragione_sociale = forms.CharField(max_length=255)
    codice_univoco = forms.CharField(max_length=20, label='Codice univoco', required=False)
    pec = forms.EmailField(label='PEC', required=False)
    referente_azienda = forms.CharField(max_length=255, label='Referente azienda', required=False)
    codice_fiscale = forms.CharField(max_length=16, required=False)
    partita_iva = forms.CharField(max_length=11, required=False)
    email_contatto = forms.EmailField(label='Email di contatto', required=False)
    telefono = forms.CharField(max_length=20, required=False)
    condizioni_pagamento_riservate = forms.CharField(
        label='Condizioni di pagamento riservate',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
    )
    logo_azienda = forms.FileField(
        label='Logo azienda',
        help_text=(
            'Formati ammessi: PNG, JPG, JPEG, SVG, WEBP. '
            f'Max {COMPANY_LOGO_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
        ),
    )
    protocollo_sanitario = forms.FileField(label='Protocollo sanitario')
    nomina_medico = forms.FileField(label='Nomina del medico')
    verbali_sopralluogo = forms.FileField(
        label='Verbali sopralluogo ambiente di lavoro',
    )
    varie_documento = forms.FileField(label='Altri documenti', required=False)
    varie_note = forms.CharField(
        label='Note altri documenti',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        document_help_text = (
            f'Formati ammessi: PDF, DOCX. Max {COMPANY_DOCUMENT_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
        )
        self.fields['email'].help_text = (
            'La password verrà generata automaticamente e inviata a questo indirizzo email.'
        )
        self.fields['logo_azienda'].help_text = (
            'Obbligatorio. Carica il logo aziendale. '
            f'Formati ammessi: PNG, JPG, JPEG, SVG, WEBP. Max {COMPANY_LOGO_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
        )

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('style', 'width:auto; height:auto')
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()
            if isinstance(field, forms.FileField):
                if field_name == 'logo_azienda':
                    field.widget.attrs.setdefault('accept', '.png,.jpg,.jpeg,.svg,.webp')
                else:
                    field.widget.attrs.setdefault('accept', '.pdf,.docx')

        self.fields['protocollo_sanitario'].help_text = (
            'Obbligatorio. Carica il protocollo sanitario aziendale. '
            f'{document_help_text}'
        )
        self.fields['nomina_medico'].help_text = (
            'Obbligatorio. Carica la nomina del medico competente. '
            f'{document_help_text}'
        )
        self.fields['verbali_sopralluogo'].help_text = (
            "Obbligatorio. Carica i verbali di sopralluogo dell'ambiente di lavoro. "
            f'{document_help_text}'
        )
        self.fields['varie_documento'].help_text = (
            "Facoltativi. Carica eventuali altri documenti aziendali già disponibili. "
            f'{document_help_text}'
        )
        self.fields['varie_note'].help_text = (
            'Facoltative. Aggiungi una breve descrizione degli altri documenti, se utile.'
        )

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Esiste già un account con questa email.')
        return email

    def clean_codice_univoco(self):
        return (self.cleaned_data.get('codice_univoco') or '').strip().upper()

    def clean_logo_azienda(self):
        return validate_company_logo_upload(self.cleaned_data.get('logo_azienda'))

    def clean_protocollo_sanitario(self):
        return validate_company_document_upload(self.cleaned_data.get('protocollo_sanitario'))

    def clean_nomina_medico(self):
        return validate_company_document_upload(self.cleaned_data.get('nomina_medico'))

    def clean_verbali_sopralluogo(self):
        return validate_company_document_upload(self.cleaned_data.get('verbali_sopralluogo'))

    def clean_varie_documento(self):
        return validate_company_document_upload(self.cleaned_data.get('varie_documento'))


class LavoratoreForm(forms.ModelForm):
    class Meta:
        model = Lavoratore
        fields = [
            'nome',
            'cognome',
            'data_nascita',
            'codice_fiscale',
            'telefono',
            'mansione',
            'sede',
            'note',
            'attivo',
        ]
        widgets = {
            'data_nascita': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, azienda=None, include_account_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        if azienda:
            self.fields['sede'].queryset = Sede.objects.filter(azienda=azienda)

        self.fields['telefono'].help_text = 'Campo obbligatorio.'
        self.fields['telefono'].widget.attrs.update({
            'inputmode': 'tel',
            'autocomplete': 'tel',
            'placeholder': 'Es. 333 1234567',
        })

        if include_account_fields and not getattr(self.instance, 'user', None):
            self.fields['account_email'] = forms.EmailField(
                required=False,
                label='Email account lavoratore',
                help_text=(
                    "Facoltativa. Se la inserisci, viene creato subito l'account lavoratore e "
                    "viene inviata una password temporanea via email. Se la lasci vuota, viene "
                    "creata solo la scheda lavoratore e potrai collegare l'account in seguito."
                ),
            )

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('style', 'width:auto; height:auto')
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()

    def clean(self):
        cleaned = super().clean()
        if 'account_email' in self.fields:
            account_email = cleaned.get('account_email')
            if account_email and CustomUser.objects.filter(email=account_email).exists():
                self.add_error('account_email', 'Esiste già un account con questa email.')
        return cleaned


class CreaAccountLavoratoreForm(forms.Form):
    account_email = forms.EmailField(
        label='Email account lavoratore',
        help_text=(
            "Inserisci l'email del lavoratore per creare l'account e inviare una password "
            'temporanea.'
        ),
    )

    def __init__(self, *args, lavoratore=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.lavoratore = lavoratore

        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()

    def clean_account_email(self):
        email = (self.cleaned_data.get('account_email') or '').strip()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Esiste già un account con questa email.')
        return email

    def clean(self):
        cleaned = super().clean()
        if self.lavoratore and getattr(self.lavoratore, 'user_id', None):
            raise forms.ValidationError('Questo lavoratore ha già un account collegato.')
        return cleaned


class DocumentoAziendaleForm(forms.ModelForm):
    class Meta:
        model = DocumentoAziendale
        fields = ['titolo', 'file', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['titolo'].label = 'Titolo documento'
        self.fields['file'].label = 'File'
        self.fields['note'].label = 'Note'
        self.fields['file'].help_text = (
            f'Formati ammessi: PDF, DOCX. Max {COMPANY_DOCUMENT_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
        )

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('style', 'width:auto; height:auto')
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()
            if field_name == 'file':
                field.widget.attrs.setdefault('accept', '.pdf,.docx')

    def clean_file(self):
        return validate_company_document_upload(self.cleaned_data.get('file'))
