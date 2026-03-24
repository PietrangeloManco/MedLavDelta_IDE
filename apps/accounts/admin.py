from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .models import CustomUser


class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.TextInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Conferma password',
        widget=forms.TextInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'role')

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Le password non coincidono.')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            self.save_m2m()
        return user


class CustomUserChangeForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        label='Password salvata',
        widget=forms.TextInput(attrs={'readonly': 'readonly'}),
        help_text=(
            'La password attuale non e visibile in chiaro. '
            'Per sostituirla, inserisci una nuova password qui sotto.'
        ),
    )
    new_password = forms.CharField(
        required=False,
        label='Nuova password',
        widget=forms.TextInput(attrs={'autocomplete': 'new-password'}),
        help_text='La nuova password resta visibile in questa schermata fino al salvataggio.',
    )

    class Meta:
        model = CustomUser
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['password'] = 'Password gia impostata'
        self.fields['email'].label = 'Email'
        self.fields['role'].label = 'Ruolo'
        self.fields['is_active'].label = 'Attivo'
        self.fields['is_staff'].label = 'Accesso amministrazione'
        self.fields['is_staff'].help_text = 'Consente l accesso al pannello amministrativo.'
        self.fields['is_superuser'].label = 'Super amministratore'
        self.fields['is_superuser'].help_text = 'Concede tutti i permessi senza assegnazioni aggiuntive.'

    def clean_password(self):
        return self.initial.get('password')

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    list_display = ['email', 'role', 'is_active', 'data_creazione']
    list_filter = ['role', 'is_active']
    ordering = ['email']

    fieldsets = (
        (None, {'fields': ('email', 'password', 'new_password')}),
        ('Ruolo', {'fields': ('role',)}),
        ('Permessi', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role'),
        }),
    )
    search_fields = ['email']


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass
