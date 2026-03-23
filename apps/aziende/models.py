from django.db import models
from apps.accounts.models import CustomUser
from .validators import (
    validate_company_document_upload,
    validate_company_logo_upload,
)


def upload_documento_azienda(instance, filename):
    user_id = instance.user_id or 'senza_utente'
    return f'aziende/{user_id}/{filename}'


def upload_logo_azienda(instance, filename):
    user_id = instance.user_id or 'senza_utente'
    return f'aziende/{user_id}/logo/{filename}'


class Azienda(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE,
        limit_choices_to={'role': 'azienda'}
    )
    ragione_sociale = models.CharField(max_length=255)
    codice_univoco = models.CharField(max_length=20, null=True)
    logo_azienda = models.FileField(
        upload_to=upload_logo_azienda,
        null=True,
        validators=[validate_company_logo_upload],
    )
    pec = models.EmailField(null=True)
    referente_azienda = models.CharField(max_length=255, null=True)
    codice_fiscale = models.CharField(max_length=16, blank=True)
    partita_iva = models.CharField(max_length=11, blank=True)
    email_contatto = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    protocollo_sanitario = models.FileField(
        upload_to=upload_documento_azienda,
        blank=True,
        null=True,
        validators=[validate_company_document_upload],
    )
    nomina_medico = models.FileField(
        upload_to=upload_documento_azienda,
        blank=True,
        null=True,
        validators=[validate_company_document_upload],
    )
    verbali_sopralluogo = models.FileField(
        upload_to=upload_documento_azienda,
        blank=True,
        null=True,
        validators=[validate_company_document_upload],
    )
    varie_documento = models.FileField(
        upload_to=upload_documento_azienda,
        blank=True,
        null=True,
        validators=[validate_company_document_upload],
    )
    varie_note = models.TextField(blank=True)
    contratto_saldato = models.BooleanField(
        default=True,
        help_text='Se non saldato, l\'azienda vedra un avviso e le funzionalita saranno limitate.',
    )
    data_registrazione = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Azienda'
        verbose_name_plural = 'Aziende'

    def __str__(self):
        return self.ragione_sociale


class Sede(models.Model):
    azienda = models.ForeignKey(
        Azienda, on_delete=models.CASCADE, related_name='sedi'
    )
    nome = models.CharField(max_length=255)
    indirizzo = models.CharField(max_length=255)
    citta = models.CharField(max_length=100)
    cap = models.CharField(max_length=10, blank=True)
    provincia = models.CharField(max_length=2, blank=True)

    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedi'

    def __str__(self):
        return f'{self.azienda} — {self.nome} ({self.citta})'


class Lavoratore(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'role': 'operatore'}
    )
    azienda = models.ForeignKey(
        Azienda, on_delete=models.CASCADE, related_name='lavoratori'
    )
    sede = models.ForeignKey(
        Sede, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lavoratori'
    )
    nome = models.CharField(max_length=100)
    cognome = models.CharField(max_length=100)
    data_nascita = models.DateField()
    codice_fiscale = models.CharField(max_length=16, unique=True)
    mansione = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    attivo = models.BooleanField(default=True)
    data_inserimento = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lavoratore'
        verbose_name_plural = 'Lavoratori'
        ordering = ['cognome', 'nome']

    def __str__(self):
        return f'{self.cognome} {self.nome} — {self.azienda}'

    @property
    def nome_completo(self):
        return f'{self.nome} {self.cognome}'    
