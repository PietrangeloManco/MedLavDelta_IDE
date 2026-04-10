from django import forms
from pathlib import Path

from .models import DocumentoSanitario, EsitoIdoneita

ALLOWED_DOC_EXTENSIONS = {'.pdf', '.docx'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def validate_document_upload(upload):
    if not upload:
        return upload
    ext = Path(upload.name).suffix.lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise forms.ValidationError('Sono accettati solo file PDF o DOCX.')
    if upload.size > MAX_UPLOAD_SIZE:
        raise forms.ValidationError('Il file non può superare 10 MB.')
    return upload


class DocumentoSanitarioForm(forms.ModelForm):
    class Meta:
        model = DocumentoSanitario
        fields = ['tipo', 'titolo', 'file', 'data', 'note']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()
            if isinstance(field, forms.FileField):
                field.widget.attrs.setdefault('accept', '.pdf,.docx')

    def clean_file(self):
        return validate_document_upload(self.cleaned_data.get('file'))


class EsitoIdoneitaForm(forms.ModelForm):
    class Meta:
        model = EsitoIdoneita
        fields = ['esito', 'mansione', 'data_visita', 'data_scadenza', 'note', 'certificato']
        widgets = {
            'data_visita': forms.DateInput(attrs={'type': 'date'}),
            'data_scadenza': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()
            if isinstance(field, forms.FileField):
                field.widget.attrs.setdefault('accept', '.pdf,.docx')

    def clean_certificato(self):
        return validate_document_upload(self.cleaned_data.get('certificato'))


class EsitoScadenzaForm(forms.ModelForm):
    class Meta:
        model = EsitoIdoneita
        fields = ['data_scadenza']
        widgets = {
            'data_scadenza': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()
