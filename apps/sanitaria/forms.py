from django import forms
from .models import DocumentoSanitario, EsitoIdoneita


class DocumentoSanitarioForm(forms.ModelForm):
    class Meta:
        model = DocumentoSanitario
        fields = ['tipo', 'titolo', 'file', 'data', 'note']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.endswith('.pdf'):
                raise forms.ValidationError('Solo file PDF sono accettati.')
            if file.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('Il file non può superare 10MB.')
        return file


class EsitoIdoneitaForm(forms.ModelForm):
    class Meta:
        model = EsitoIdoneita
        fields = ['esito', 'mansione', 'data_visita', 'data_scadenza', 'note']
        widgets = {
            'data_visita': forms.DateInput(attrs={'type': 'date'}),
            'data_scadenza': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }