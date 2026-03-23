from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.accounts.models import CustomUser
from .models import Azienda, Sede, Lavoratore
from .validators import (
    COMPANY_DOCUMENT_MAX_UPLOAD_SIZE,
    COMPANY_LOGO_MAX_UPLOAD_SIZE,
)


class AziendaAdminForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role=CustomUser.AZIENDA),
        required=False,
        label='Account azienda esistente',
        help_text='Se non selezioni un account, ne verra creato uno nuovo.',
    )
    account_email = forms.EmailField(
        required=False,
        label='Email nuovo account azienda',
    )
    account_password = forms.CharField(
        required=False,
        label='Password nuovo account',
        widget=forms.PasswordInput(render_value=False),
    )

    class Meta:
        model = Azienda
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        document_help_text = (
            f'Formati ammessi: PDF, DOCX. Max {COMPANY_DOCUMENT_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
        )

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
        account_email = cleaned.get('account_email')
        account_password = cleaned.get('account_password')

        if user and (account_email or account_password):
            raise ValidationError(
                'Scegli un account esistente oppure inserisci email/password per crearne uno nuovo.'
            )

        if not self.instance.pk and not user:
            if not account_email or not account_password:
                raise ValidationError(
                    'Per una nuova azienda devi selezionare un account esistente o inserire email e password.'
                )
            if CustomUser.objects.filter(email=account_email).exists():
                self.add_error('account_email', 'Esiste gia un utente con questa email.')

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        user = self.cleaned_data.get('user')
        account_email = self.cleaned_data.get('account_email')
        account_password = self.cleaned_data.get('account_password')

        if self.instance.pk and not user:
            user = self.instance.user

        if not self.instance.pk and not user and account_email and account_password:
            user = CustomUser.objects.create_user(
                email=account_email,
                password=account_password,
                role=CustomUser.AZIENDA,
            )

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
    inlines = [SedeInline, LavoratoreInline]


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ['nome', 'azienda', 'citta']
    list_filter = ['azienda']


@admin.register(Lavoratore)
class LavoratoreAdmin(admin.ModelAdmin):
    list_display = ['cognome', 'nome', 'azienda', 'sede', 'mansione', 'attivo', 'user']
    list_filter = ['azienda', 'attivo']
    search_fields = ['cognome', 'nome', 'codice_fiscale']

    def has_add_permission(self, request):
        return False
