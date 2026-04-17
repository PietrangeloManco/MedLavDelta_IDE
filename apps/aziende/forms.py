from django import forms

from apps.accounts.models import CustomUser

from .models import (
    DocumentoAziendale,
    Lavoratore,
    Sede,
    normalize_company_notification_cc_emails,
)
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
        required=False,
    )
    protocollo_sanitario = forms.FileField(label='Protocollo sanitario', required=False)
    nomina_medico = forms.FileField(label='Nomina del medico', required=False)
    verbali_sopralluogo = forms.FileField(
        label='Verbali sopralluogo ambiente di lavoro',
        required=False,
    )
    varie_documento = forms.FileField(label='Altri documenti (per azienda)', required=False)
    varie_note = forms.CharField(
        label='Note altri documenti (per azienda)',
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
            'Facoltativo. Puoi caricare il logo aziendale ora oppure aggiungerlo successivamente. '
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
            'Facoltativo. Puoi caricare il protocollo sanitario aziendale ora oppure aggiungerlo successivamente. '
            f'{document_help_text}'
        )
        self.fields['nomina_medico'].help_text = (
            'Facoltativa. Puoi caricare la nomina del medico competente ora oppure aggiungerla successivamente. '
            f'{document_help_text}'
        )
        self.fields['verbali_sopralluogo'].help_text = (
            "Facoltativi. Puoi caricare i verbali di sopralluogo dell'ambiente di lavoro ora oppure aggiungerli successivamente. "
            f'{document_help_text}'
        )
        self.fields['varie_documento'].help_text = (
            "Facoltativi. Carica eventuali altri documenti aziendali già disponibili. "
            f'{document_help_text}'
        )
        self.fields['varie_note'].help_text = (
            'Facoltative. Aggiungi una breve descrizione degli altri documenti aziendali, se utile.'
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
            'sesso',
            'codice_fiscale',
            'telefono',
            'mansione',
            'sede',
            'note',
            'attivo',
        ]
        widgets = {
            'data_nascita': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, azienda=None, include_account_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        if azienda:
            self.fields['sede'].queryset = Sede.objects.filter(azienda=azienda)

        self.fields['telefono'].help_text = 'Facoltativo.'
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

        self.fields['sesso'].widget.attrs.setdefault('autocomplete', 'sex')

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


class CreaAccountAziendaReadOnlyForm(forms.Form):
    account_email = forms.EmailField(
        label='Email account secondario',
        help_text=(
            "Crea un accesso azienda in sola lettura e invia una password temporanea "
            "all'indirizzo indicato."
        ),
    )

    def __init__(self, *args, azienda=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.azienda = azienda

        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()
            field.widget.attrs.setdefault('autocomplete', 'email')

    def clean_account_email(self):
        email = (self.cleaned_data.get('account_email') or '').strip()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Esiste già un account con questa email.')
        return email


class AziendaNotificationCcForm(forms.Form):
    email_notifiche_cc = forms.CharField(
        required=False,
        label='Email in cc per notifiche azienda',
        help_text=(
            'Inserisci uno o più indirizzi email, uno per riga oppure separati da virgole.'
        ),
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'ufficio.hr@example.com\nreferente@example.com',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()

    def clean_email_notifiche_cc(self):
        return normalize_company_notification_cc_emails(self.cleaned_data.get('email_notifiche_cc'))


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


class ReplaceFileForm(forms.Form):
    file = forms.FileField(label='Nuovo file')
    note = forms.CharField(
        label='Note',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(
        self,
        *args,
        validator=None,
        file_help_text='',
        accept='',
        include_note=False,
        note_initial='',
        note_label='Note',
        **kwargs,
    ):
        self.validator = validator
        super().__init__(*args, **kwargs)

        if not include_note:
            self.fields.pop('note')
        else:
            self.fields['note'].initial = note_initial
            self.fields['note'].label = note_label

        self.fields['file'].help_text = file_help_text
        if accept:
            self.fields['file'].widget.attrs.setdefault('accept', accept)

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('style', 'width:auto; height:auto')
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()

    def clean_file(self):
        upload = self.cleaned_data.get('file')
        if self.validator:
            return self.validator(upload)
        return upload
