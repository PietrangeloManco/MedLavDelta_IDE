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
    codice_univoco = forms.CharField(max_length=20, label='Codice univoco')
    pec = forms.EmailField(label='PEC')
    referente_azienda = forms.CharField(max_length=255, label='Referente azienda')
    codice_fiscale = forms.CharField(max_length=16, required=False)
    partita_iva = forms.CharField(max_length=11, required=False)
    email_contatto = forms.EmailField(label='Email di contatto')
    telefono = forms.CharField(max_length=20, required=False)
    condizioni_pagamento_riservate = forms.CharField(
        label='Condizioni di pagamento riservate',
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    logo_azienda = forms.FileField(
        label='Logo azienda',
        required=True,
        help_text=(
            'Formati ammessi: PNG, JPG, JPEG, SVG, WEBP. '
            f'Max {COMPANY_LOGO_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
        ),
    )
    protocollo_sanitario = forms.FileField(label='Protocollo sanitario', required=True)
    nomina_medico = forms.FileField(label='Nomina del medico', required=True)
    verbali_sopralluogo = forms.FileField(
        label='Verbali sopralluogo ambiente di lavoro', required=True
    )
    varie_documento = forms.FileField(label='Varie (documento)', required=False)
    varie_note = forms.CharField(
        label='Note',
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

        for field_name in (
            'protocollo_sanitario',
            'nomina_medico',
            'verbali_sopralluogo',
            'varie_documento',
        ):
            self.fields[field_name].help_text = document_help_text

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Esiste già un account con questa email.')
        return email

    def clean_codice_univoco(self):
        return self.cleaned_data['codice_univoco'].strip().upper()

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
            'nome', 'cognome', 'data_nascita', 'codice_fiscale',
            'mansione', 'sede', 'note', 'attivo'
        ]
        widgets = {
            'data_nascita': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, azienda=None, include_account_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        if azienda:
            self.fields['sede'].queryset = Sede.objects.filter(azienda=azienda)

        if include_account_fields and not getattr(self.instance, 'user', None):
            self.fields['account_email'] = forms.EmailField(
                required=False,
                label='Email account lavoratore',
                help_text='Opzionale: crea subito l\'account e invia via email una password generata automaticamente.',
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
