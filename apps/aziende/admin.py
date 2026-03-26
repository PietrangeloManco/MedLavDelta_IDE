from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.accounts.models import CustomUser
from .models import Azienda, DocumentoAziendale, Lavoratore, Sede
from .validators import (
    COMPANY_DOCUMENT_MAX_UPLOAD_SIZE,
    COMPANY_LOGO_MAX_UPLOAD_SIZE,
)


class AziendaAdminForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        label='Account azienda esistente',
        help_text='Seleziona un account gia disponibile oppure creane uno nuovo qui sotto.',
    )
    account_email = forms.EmailField(
        required=False,
        label='Email account azienda',
    )
    account_password = forms.CharField(
        required=False,
        label='Nuova password account',
        widget=forms.TextInput(attrs={'autocomplete': 'new-password'}),
        help_text=(
            'La password attuale non e visibile in chiaro. '
            'Inseriscine una nuova per reimpostarla e verificarla prima del salvataggio.'
        ),
    )

    class Meta:
        model = Azienda
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_user = getattr(self.instance, 'user', None)
        document_help_text = (
            f'Formati ammessi: PDF, DOCX. Max {COMPANY_DOCUMENT_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
        )

        user_queryset = CustomUser.objects.filter(role=CustomUser.AZIENDA)
        if current_user:
            user_queryset = user_queryset.filter(Q(azienda__isnull=True) | Q(pk=current_user.pk))
            self.fields['user'].initial = current_user
            self.fields['account_email'].initial = current_user.email
            self.fields['account_email'].help_text = (
                "Lascia l'email corrente oppure modificala per aggiornare l'account collegato."
            )
        else:
            user_queryset = user_queryset.filter(azienda__isnull=True)
            self.fields['account_email'].help_text = (
                "Inseriscila se vuoi creare un nuovo account azienda da questa scheda."
            )
        self.fields['user'].queryset = user_queryset.order_by('email')

        if 'logo_azienda' in self.fields:
            self.fields['logo_azienda'].label = 'Logo azienda'
            self.fields['logo_azienda'].help_text = (
                'Formati ammessi: PNG, JPG, JPEG, SVG, WEBP. '
                f'Max {COMPANY_LOGO_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
            )
            self.fields['logo_azienda'].widget.attrs['accept'] = '.png,.jpg,.jpeg,.svg,.webp'

        for field_name, label in (
            ('codice_univoco', 'Codice univoco'),
            ('pec', 'PEC'),
            ('referente_azienda', 'Referente azienda'),
            ('condizioni_pagamento_riservate', 'Condizioni Pagamento Riservate'),
        ):
            if field_name in self.fields:
                self.fields[field_name].label = label

        for field_name in (
            'protocollo_sanitario',
            'nomina_medico',
            'verbali_sopralluogo',
            'varie_documento',
        ):
            if field_name in self.fields:
                self.fields[field_name].help_text = document_help_text
                self.fields[field_name].widget.attrs['accept'] = '.pdf,.docx'

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get('user')
        current_user = user or getattr(self.instance, 'user', None)
        account_email = (cleaned.get('account_email') or '').strip()
        account_password = cleaned.get('account_password')

        if not self.instance.pk and not user and not account_email:
            raise ValidationError(
                'Per una nuova azienda devi selezionare un account esistente o inserire email e password.'
            )

        if account_password and not current_user and not account_email:
            self.add_error(
                'account_email',
                "Inserisci un'email o seleziona un account prima di impostare la password.",
            )

        if account_email and not current_user and not account_password:
            self.add_error('account_password', 'Inserisci una password per il nuovo account.')

        if account_email:
            conflict_qs = CustomUser.objects.exclude(
                pk=current_user.pk if current_user else None
            ).filter(email=account_email)
            if conflict_qs.exists():
                self.add_error('account_email', 'Esiste gia un utente con questa email.')

        cleaned['account_email'] = account_email
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        user = self.cleaned_data.get('user') or getattr(instance, 'user', None)
        account_email = self.cleaned_data.get('account_email')
        account_password = self.cleaned_data.get('account_password')

        if not self.instance.pk and not user and account_email and account_password:
            user = CustomUser.objects.create_user(
                email=account_email,
                password=account_password,
                role=CustomUser.AZIENDA,
            )
        elif user:
            update_fields = []
            if account_email and account_email != user.email:
                user.email = account_email
                update_fields.append('email')
            if account_password:
                user.set_password(account_password)
                update_fields.append('password')
            if update_fields:
                user.save(update_fields=update_fields)

        if user:
            instance.user = user

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class LavoratoreAdminForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        label='Account operatore esistente',
        help_text='Collega un account gia disponibile oppure creane uno nuovo qui sotto.',
    )
    account_email = forms.EmailField(
        required=False,
        label='Email account operatore',
    )
    account_password = forms.CharField(
        required=False,
        label='Nuova password account',
        widget=forms.TextInput(attrs={'autocomplete': 'new-password'}),
        help_text=(
            'La password attuale non e visibile in chiaro. '
            "Inseriscine una nuova per creare o reimpostare l'accesso."
        ),
    )

    class Meta:
        model = Lavoratore
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_user = getattr(self.instance, 'user', None)
        user_queryset = CustomUser.objects.filter(role=CustomUser.OPERATORE)
        if current_user:
            user_queryset = user_queryset.filter(Q(lavoratore__isnull=True) | Q(pk=current_user.pk))
            self.fields['user'].initial = current_user
            self.fields['account_email'].initial = current_user.email
            self.fields['account_email'].help_text = (
                "Lascia l'email corrente oppure modificala per aggiornare l'account collegato."
            )
        else:
            user_queryset = user_queryset.filter(lavoratore__isnull=True)
            self.fields['account_email'].help_text = (
                "Inseriscila se vuoi creare un nuovo account operatore da questa scheda."
            )
        self.fields['user'].queryset = user_queryset.order_by('email')

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get('user')
        current_user = user or getattr(self.instance, 'user', None)
        account_email = (cleaned.get('account_email') or '').strip()
        account_password = cleaned.get('account_password')

        if account_password and not current_user and not account_email:
            self.add_error(
                'account_email',
                "Inserisci un'email o seleziona un account prima di impostare la password.",
            )

        if account_email and not current_user and not account_password:
            self.add_error('account_password', 'Inserisci una password per il nuovo account.')

        if account_email:
            conflict_qs = CustomUser.objects.exclude(
                pk=current_user.pk if current_user else None
            ).filter(email=account_email)
            if conflict_qs.exists():
                self.add_error('account_email', 'Esiste gia un utente con questa email.')

        cleaned['account_email'] = account_email
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        user = self.cleaned_data.get('user') or getattr(instance, 'user', None)
        account_email = self.cleaned_data.get('account_email')
        account_password = self.cleaned_data.get('account_password')

        if not user and account_email and account_password:
            user = CustomUser.objects.create_user(
                email=account_email,
                password=account_password,
                role=CustomUser.OPERATORE,
            )
        elif user:
            update_fields = []
            if account_email and account_email != user.email:
                user.email = account_email
                update_fields.append('email')
            if account_password:
                user.set_password(account_password)
                update_fields.append('password')
            if update_fields:
                user.save(update_fields=update_fields)

        if user:
            instance.user = user

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class SedeInline(admin.TabularInline):
    model = Sede
    extra = 1


class LavoratoreInline(admin.TabularInline):
    model = Lavoratore
    extra = 0
    fields = ['cognome', 'nome', 'mansione', 'sede', 'attivo']

    def has_add_permission(self, request, obj=None):
        return False


class DocumentoAziendaleInline(admin.TabularInline):
    model = DocumentoAziendale
    extra = 0
    fields = ['titolo', 'file', 'origine', 'caricato_da', 'data_caricamento', 'note']
    readonly_fields = ['origine', 'caricato_da', 'data_caricamento']


@admin.register(Azienda)
class AziendaAdmin(admin.ModelAdmin):
    form = AziendaAdminForm
    list_display = [
        'ragione_sociale',
        'codice_univoco',
        'partita_iva',
        'pec',
        'referente_azienda',
        'email_contatto',
        'contratto_saldato',
        'user',
    ]
    list_filter = ['contratto_saldato']
    search_fields = ['ragione_sociale', 'partita_iva', 'codice_univoco', 'pec', 'referente_azienda']
    inlines = [SedeInline, LavoratoreInline, DocumentoAziendaleInline]
    fieldsets = (
        ('Profilo azienda', {
            'fields': (
                'ragione_sociale',
                'codice_univoco',
                'pec',
                'referente_azienda',
                'codice_fiscale',
                'partita_iva',
                'email_contatto',
                'telefono',
                'condizioni_pagamento_riservate',
                'contratto_saldato',
            ),
        }),
        ('Account azienda', {
            'fields': ('user', 'account_email', 'account_password'),
        }),
        ('Documenti', {
            'fields': (
                'logo_azienda',
                'protocollo_sanitario',
                'nomina_medico',
                'verbali_sopralluogo',
                'varie_documento',
                'varie_note',
            ),
        }),
    )


@admin.register(DocumentoAziendale)
class DocumentoAziendaleAdmin(admin.ModelAdmin):
    list_display = ['titolo', 'azienda', 'origine', 'caricato_da', 'data_caricamento']
    list_filter = ['origine', 'azienda']
    search_fields = ['titolo', 'azienda__ragione_sociale']


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ['nome', 'azienda', 'citta']
    list_filter = ['azienda']


@admin.register(Lavoratore)
class LavoratoreAdmin(admin.ModelAdmin):
    form = LavoratoreAdminForm
    list_display = ['cognome', 'nome', 'azienda', 'sede', 'mansione', 'attivo', 'user']
    list_filter = ['azienda', 'attivo']
    search_fields = ['cognome', 'nome', 'codice_fiscale']
    fieldsets = (
        ('Anagrafica', {
            'fields': (
                'azienda',
                'sede',
                'nome',
                'cognome',
                'data_nascita',
                'codice_fiscale',
                'mansione',
                'attivo',
                'note',
            ),
        }),
        ('Account operatore', {
            'fields': ('user', 'account_email', 'account_password'),
        }),
    )

    def has_add_permission(self, request):
        return False
