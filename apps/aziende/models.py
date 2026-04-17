import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models

from apps.accounts.models import CustomUser

from .validators import (
    validate_company_document_upload,
    validate_company_logo_upload,
)


EMAIL_LIST_SPLIT_RE = re.compile(r'[\n\r,;]+')


def parse_company_notification_cc_emails(raw_value):
    emails = []
    seen = set()
    for chunk in EMAIL_LIST_SPLIT_RE.split(raw_value or ''):
        email = chunk.strip()
        if not email:
            continue
        try:
            validate_email(email)
        except ValidationError as exc:
            raise ValidationError(
                'Inserisci uno o più indirizzi email validi, separati da virgole o su righe distinte.'
            ) from exc
        email_key = email.lower()
        if email_key in seen:
            continue
        seen.add(email_key)
        emails.append(email)
    return emails


def normalize_company_notification_cc_emails(raw_value):
    return '\n'.join(parse_company_notification_cc_emails(raw_value))


def upload_documento_azienda(instance, filename):
    if hasattr(instance, 'user_id') and instance.user_id:
        user_id = instance.user_id
    elif hasattr(instance, 'azienda') and getattr(instance.azienda, 'user_id', None):
        user_id = instance.azienda.user_id
    else:
        user_id = 'senza_utente'
    return f'aziende/{user_id}/{filename}'


def upload_logo_azienda(instance, filename):
    user_id = instance.user_id or 'senza_utente'
    return f'aziende/{user_id}/logo/{filename}'


class Azienda(models.Model):
    INITIAL_DOCUMENT_FIELDS = (
        ('logo_azienda', 'Logo azienda'),
        ('protocollo_sanitario', 'Protocollo sanitario'),
        ('nomina_medico', 'Nomina del medico'),
        ('verbali_sopralluogo', 'Verbali sopralluogo ambiente di lavoro'),
        ('varie_documento', 'Altri documenti (per azienda)'),
    )

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE,
        limit_choices_to={'role': 'azienda'},
        null=True,
        blank=True,
    )
    ragione_sociale = models.CharField(max_length=255)
    codice_univoco = models.CharField(max_length=20, null=True, blank=True)
    logo_azienda = models.FileField(
        upload_to=upload_logo_azienda,
        blank=True,
        null=True,
        validators=[validate_company_logo_upload],
    )
    pec = models.EmailField(null=True, blank=True)
    referente_azienda = models.CharField(max_length=255, null=True, blank=True)
    codice_fiscale = models.CharField(max_length=16, blank=True)
    partita_iva = models.CharField(max_length=11, blank=True)
    email_contatto = models.EmailField(blank=True)
    email_notifiche_cc = models.TextField(
        blank=True,
        default='',
        help_text=(
            "Indirizzi email che ricevono in cc le comunicazioni inviate all'account "
            'azienda principale. Inseriscine uno per riga oppure separali con una virgola.'
        ),
    )
    telefono = models.CharField(max_length=20, blank=True)
    condizioni_pagamento_riservate = models.TextField(blank=True)
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
        help_text='Se non saldato, l\'azienda vedrà un avviso e le funzionalità saranno limitate.',
    )
    data_registrazione = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Azienda'
        verbose_name_plural = 'Aziende'

    def __str__(self):
        return self.display_name

    @classmethod
    def resolve_for_user(cls, user):
        if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_azienda', False):
            return None, None

        azienda = cls.objects.filter(user=user).first()
        if azienda:
            return azienda, None

        access = AziendaReadOnlyAccess.objects.select_related('azienda').filter(user=user).first()
        if access:
            return access.azienda, access
        return None, None

    @property
    def display_name(self):
        if self.ragione_sociale:
            return self.ragione_sociale
        if self.pk:
            return f'Azienda #{self.pk}'
        return 'Azienda senza nome'

    @property
    def referente_display_name(self):
        referente = (self.referente_azienda or '').strip()
        parts = referente.split()
        if len(parts) == 2:
            return f'{parts[1]} {parts[0]}'
        return referente

    @property
    def notification_cc_list(self):
        return parse_company_notification_cc_emails(self.email_notifiche_cc)

    @property
    def formatted_notification_cc_emails(self):
        return normalize_company_notification_cc_emails(self.email_notifiche_cc)

    @property
    def primary_notification_email(self):
        if self.user_id and getattr(self.user, 'email', ''):
            return self.user.email
        return (self.email_contatto or '').strip()

    def clean(self):
        super().clean()
        try:
            self.email_notifiche_cc = normalize_company_notification_cc_emails(self.email_notifiche_cc)
        except ValidationError as exc:
            raise ValidationError({'email_notifiche_cc': exc.messages}) from exc

    def get_documenti_iniziali(self):
        documenti = []
        for field_name, label in self.INITIAL_DOCUMENT_FIELDS:
            documento = getattr(self, field_name)
            if not documento:
                continue
            documenti.append({
                'field_name': field_name,
                'titolo': label,
                'file': documento,
                'nome_file': Path(documento.name).name,
                'note': self.varie_note if field_name == 'varie_documento' else '',
                'data_caricamento': self.data_registrazione,
                'origine': 'admin',
                'origine_label': 'Admin',
            })
        return documenti


class AziendaReadOnlyAccess(models.Model):
    azienda = models.ForeignKey(
        Azienda,
        on_delete=models.CASCADE,
        related_name='read_only_accesses',
    )
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='read_only_company_access',
        limit_choices_to={'role': 'azienda'},
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_company_read_only_accesses',
    )
    data_creazione = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Accesso azienda in sola lettura'
        verbose_name_plural = 'Accessi azienda in sola lettura'
        ordering = ['user__email', 'pk']

    def __str__(self):
        return f'{self.azienda} - {self.user.email}'


class DocumentoAziendale(models.Model):
    ORIGINE_ADMIN = 'admin'
    ORIGINE_AZIENDA = 'azienda'

    ORIGINE_CHOICES = [
        (ORIGINE_ADMIN, 'Admin'),
        (ORIGINE_AZIENDA, 'Azienda'),
    ]

    azienda = models.ForeignKey(
        Azienda,
        on_delete=models.CASCADE,
        related_name='documenti_generici',
    )
    titolo = models.CharField(max_length=255)
    file = models.FileField(
        upload_to=upload_documento_azienda,
        validators=[validate_company_document_upload],
    )
    note = models.TextField(blank=True)
    origine = models.CharField(
        max_length=20,
        choices=ORIGINE_CHOICES,
        default=ORIGINE_AZIENDA,
    )
    caricato_da = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documenti_aziendali_caricati',
    )
    data_caricamento = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento aziendale'
        verbose_name_plural = 'Documenti aziendali'
        ordering = ['-data_caricamento', '-id']

    def __str__(self):
        return f'{self.azienda} - {self.titolo}'

    @property
    def nome_file(self):
        return Path(self.file.name).name


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
        return f'{self.azienda} - {self.nome} ({self.citta})'


class Lavoratore(models.Model):
    SESSO_MASCHILE = 'M'
    SESSO_FEMMINILE = 'F'
    SESSO_CHOICES = [
        (SESSO_MASCHILE, 'Maschile'),
        (SESSO_FEMMINILE, 'Femminile'),
    ]

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
    sesso = models.CharField(max_length=1, choices=SESSO_CHOICES, blank=True, default='')
    codice_fiscale = models.CharField(max_length=16, unique=True)
    telefono = models.CharField('Numero di telefono', max_length=20, blank=True, default='')
    mansione = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    attivo = models.BooleanField(default=True)
    data_inserimento = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lavoratore'
        verbose_name_plural = 'Lavoratori'
        ordering = ['cognome', 'nome']

    def __str__(self):
        return f'{self.cognome} {self.nome} - {self.azienda}'

    @property
    def nome_completo(self):
        return f'{self.cognome} {self.nome}'.strip()
