from django import forms
from .models import Azienda, Lavoratore, Sede
from apps.accounts.models import CustomUser


class CreaAziendaForm(forms.Form):
    # Dati account
    email = forms.EmailField(label='Email account azienda')
    password = forms.CharField(widget=forms.PasswordInput, label='Password')

    # Dati azienda
    ragione_sociale = forms.CharField(max_length=255)
    codice_fiscale = forms.CharField(max_length=16, required=False)
    partita_iva = forms.CharField(max_length=11, required=False)
    email_contatto = forms.EmailField(label='Email di contatto')
    telefono = forms.CharField(max_length=20, required=False)

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Esiste già un account con questa email.')
        return email


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
                help_text='Opzionale: crea subito l\'account per accesso al portale.',
            )
            self.fields['account_password'] = forms.CharField(
                required=False,
                label='Password temporanea',
                widget=forms.PasswordInput(render_value=False),
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
            account_password = cleaned.get('account_password')
            if account_email or account_password:
                if not account_email or not account_password:
                    raise forms.ValidationError(
                        'Per creare un account lavoratore devi inserire sia email sia password.'
                    )
                if CustomUser.objects.filter(email=account_email).exists():
                    self.add_error('account_email', 'Esiste gia un account con questa email.')
        return cleaned
