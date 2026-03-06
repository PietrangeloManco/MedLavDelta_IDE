from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.accounts.models import CustomUser
from .models import Azienda, Sede, Lavoratore


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


class LavoratoreAdminForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role=CustomUser.OPERATORE),
        required=False,
        label='Account lavoratore esistente',
        help_text='Opzionale: collega un account gia presente oppure creane uno nuovo.',
    )
    account_email = forms.EmailField(
        required=False,
        label='Email nuovo account lavoratore',
    )
    account_password = forms.CharField(
        required=False,
        label='Password nuovo account',
        widget=forms.PasswordInput(render_value=False),
    )

    class Meta:
        model = Lavoratore
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get('user')
        account_email = cleaned.get('account_email')
        account_password = cleaned.get('account_password')

        if user and (account_email or account_password):
            raise ValidationError(
                'Scegli un account esistente oppure inserisci email/password per crearne uno nuovo.'
            )

        if account_email or account_password:
            if not account_email or not account_password:
                raise ValidationError(
                    'Per creare un nuovo account lavoratore devi inserire sia email sia password.'
                )
            if CustomUser.objects.filter(email=account_email).exists():
                self.add_error('account_email', 'Esiste gia un utente con questa email.')

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        user = self.cleaned_data.get('user')
        account_email = self.cleaned_data.get('account_email')
        account_password = self.cleaned_data.get('account_password')

        if account_email and account_password:
            user = CustomUser.objects.create_user(
                email=account_email,
                password=account_password,
                role=CustomUser.OPERATORE,
            )

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


@admin.register(Azienda)
class AziendaAdmin(admin.ModelAdmin):
    form = AziendaAdminForm
    list_display = ['ragione_sociale', 'partita_iva', 'email_contatto', 'user']
    inlines = [SedeInline, LavoratoreInline]


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
