from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .models import CustomUser
from .services import generate_temporary_password, send_account_credentials_email


class CustomUserCreationForm(forms.ModelForm):
    is_active = forms.BooleanField(required=False, initial=True, label='Attivo')
    is_superuser = forms.BooleanField(required=False, label='Super amministratore')
    admin_permissions = forms.MultipleChoiceField(
        required=False,
        label='Permessi admin limitato',
        choices=CustomUser.ADMIN_PERMISSION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            'Elenco provvisorio dei permessi per gli account admin non superuser. '
            'Se selezioni "Super amministratore", questi permessi vengono ignorati.'
        ),
    )
    class Meta:
        model = CustomUser
        fields = ('email', 'role', 'is_active', 'is_superuser', 'admin_permissions')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].help_text = (
            'La password verra generata automaticamente e inviata a questo indirizzo email.'
        )

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        is_superuser = cleaned.get('is_superuser')
        admin_permissions = cleaned.get('admin_permissions') or []

        if is_superuser and role != CustomUser.ADMIN:
            self.add_error('role', 'Solo un utente con ruolo amministratore puo essere super amministratore.')

        if role == CustomUser.ADMIN and not is_superuser and not admin_permissions:
            self.add_error(
                'admin_permissions',
                'Se crei un admin limitato devi selezionare almeno un permesso.',
            )

        if role != CustomUser.ADMIN:
            cleaned['admin_permissions'] = []
            cleaned['is_superuser'] = False
        elif is_superuser:
            cleaned['admin_permissions'] = []

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        self.generated_password = generate_temporary_password()
        user.set_password(self.generated_password)
        user.admin_permissions = self.cleaned_data.get('admin_permissions') or []
        role = self.cleaned_data.get('role')
        is_superuser = self.cleaned_data.get('is_superuser', False)
        user.is_active = self.cleaned_data.get('is_active', True)
        user.is_superuser = bool(role == CustomUser.ADMIN and is_superuser)
        user.is_staff = bool(role == CustomUser.ADMIN and is_superuser)
        if role != CustomUser.ADMIN:
            user.admin_permissions = []
        if commit:
            user.save()
            self.save_m2m()
        return user


class CustomUserChangeForm(forms.ModelForm):
    admin_permissions = forms.MultipleChoiceField(
        required=False,
        label='Permessi admin limitato',
        choices=CustomUser.ADMIN_PERMISSION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            'Elenco provvisorio dei permessi per gli account admin non superuser. '
            'Se l\'utente e super amministratore, questi permessi vengono ignorati.'
        ),
    )
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
        self.initial['admin_permissions'] = self.instance.admin_permissions or []
        self.fields['email'].label = 'Email'
        self.fields['role'].label = 'Ruolo'
        self.fields['is_active'].label = 'Attivo'
        self.fields['is_superuser'].label = 'Super amministratore'
        self.fields['is_superuser'].help_text = 'Concede tutti i permessi senza assegnazioni aggiuntive.'
        self.fields['is_staff'].label = 'Accesso amministrazione'
        self.fields['is_staff'].help_text = 'Viene gestito automaticamente per i super amministratori.'

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        is_superuser = cleaned.get('is_superuser')
        admin_permissions = cleaned.get('admin_permissions') or []

        if is_superuser and role != CustomUser.ADMIN:
            self.add_error('role', 'Solo un utente con ruolo amministratore puo essere super amministratore.')

        if role == CustomUser.ADMIN and not is_superuser and not admin_permissions:
            self.add_error(
                'admin_permissions',
                'Se mantieni un admin limitato devi selezionare almeno un permesso.',
            )

        if role != CustomUser.ADMIN:
            cleaned['admin_permissions'] = []
            cleaned['is_superuser'] = False
            cleaned['is_staff'] = False
        elif is_superuser:
            cleaned['admin_permissions'] = []

        return cleaned

    def clean_password(self):
        return self.initial.get('password')

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get('new_password')
        role = self.cleaned_data.get('role')
        is_superuser = self.cleaned_data.get('is_superuser', False)
        user.admin_permissions = self.cleaned_data.get('admin_permissions') or []
        user.is_superuser = bool(role == CustomUser.ADMIN and is_superuser)
        user.is_staff = bool(role == CustomUser.ADMIN and is_superuser)
        if role != CustomUser.ADMIN:
            user.admin_permissions = []
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
    list_display = ['email', 'role', 'admin_access_level', 'is_active', 'data_creazione']
    list_filter = ['role', 'is_active']
    ordering = ['email']

    fieldsets = (
        (None, {'fields': ('email', 'password', 'new_password')}),
        ('Ruolo', {'fields': ('role',)}),
        ('Permessi accesso', {'fields': ('is_active', 'is_superuser', 'is_staff')}),
        ('Permessi area amministrativa', {'fields': ('admin_permissions',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'role',
                'is_active',
                'is_superuser',
                'admin_permissions',
            ),
        }),
    )
    search_fields = ['email']
    readonly_fields = ['is_staff']

    @admin.display(description='Profilo admin')
    def admin_access_level(self, obj):
        if obj.role != CustomUser.ADMIN:
            return '-'
        if obj.is_superuser:
            return 'Super amministratore'
        if not obj.admin_permissions:
            return 'Admin senza permessi'
        return f'Admin limitato ({len(obj.admin_permissions)})'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and getattr(form, 'generated_password', None):
            send_account_credentials_email(obj, form.generated_password, request=request)


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass
