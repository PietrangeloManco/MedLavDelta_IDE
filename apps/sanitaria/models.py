from django.db import models
from apps.aziende.models import Lavoratore


def upload_documento(instance, filename):
    # Salva i file in media/documenti/<id_lavoratore>/<filename>
    return f'documenti/{instance.cartella.lavoratore.id}/{filename}'


def upload_certificato_idoneita(instance, filename):
    return f'idoneita/{instance.lavoratore_id}/{filename}'


class CartellaClinica(models.Model):
    lavoratore = models.OneToOneField(
        Lavoratore, on_delete=models.CASCADE, related_name='cartella'
    )
    data_apertura = models.DateField(auto_now_add=True)
    note_medico = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Cartella Clinica'
        verbose_name_plural = 'Cartelle Cliniche'

    def __str__(self):
        return f'Cartella - {self.lavoratore}'


class DocumentoSanitario(models.Model):
    REFERTO = 'referto'
    VISITA = 'verbale_visita'
    ESAME = 'esame'
    ALTRO = 'altro'

    TIPO_CHOICES = [
        (REFERTO, 'Referto'),
        (VISITA, 'Verbale di visita'),
        (ESAME, 'Risultato esame'),
        (ALTRO, 'Altro'),
    ]

    cartella = models.ForeignKey(
        CartellaClinica, on_delete=models.CASCADE, related_name='documenti'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titolo = models.CharField(max_length=255)
    file = models.FileField(upload_to=upload_documento)
    data = models.DateField()
    note = models.TextField(blank=True)
    caricato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento Sanitario'
        verbose_name_plural = 'Documenti Sanitari'
        ordering = ['-data']

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.cartella.lavoratore} ({self.data})'


class EsitoIdoneita(models.Model):
    IDONEO = 'idoneo'
    IDONEO_LIMITAZIONI = 'idoneo_limitazioni'
    IDONEITA_PRESCRIZIONE = 'idoneita_prescrizione'
    IDONEO_PRESCRIZIONI_LIMITAZIONI = 'idoneo_prescrizioni_limitazioni'
    NON_IDONEO = 'non_idoneo'
    TEMPORANEO = 'non_idoneo_temporaneo'

    ESITO_CHOICES = [
        (IDONEO, 'Idoneità confermata'),
        (IDONEO_LIMITAZIONI, 'Idoneità con limitazioni'),
        (IDONEITA_PRESCRIZIONE, 'Idoneità con prescrizione'),
        (IDONEO_PRESCRIZIONI_LIMITAZIONI, 'Idoneità con prescrizioni e limitazioni'),
        (NON_IDONEO, 'Idoneità non confermata'),
        (TEMPORANEO, 'Idoneità non confermata (temporanea)'),
    ]

    lavoratore = models.ForeignKey(
        Lavoratore, on_delete=models.CASCADE, related_name='idoneita'
    )
    esito = models.CharField(max_length=35, choices=ESITO_CHOICES)
    mansione = models.CharField(max_length=255)
    data_visita = models.DateField()
    data_scadenza = models.DateField()
    note = models.TextField(blank=True)
    certificato = models.FileField(
        upload_to=upload_certificato_idoneita, blank=True, null=True
    )
    comunicato_azienda = models.BooleanField(default=False)
    data_comunicazione = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Esito idoneità'
        verbose_name_plural = 'Esiti idoneità'
        ordering = ['-data_visita']

    def __str__(self):
        return f'{self.lavoratore} - {self.get_esito_display()} ({self.data_visita})'

    @property
    def is_scaduto(self):
        from django.utils import timezone
        return self.data_scadenza < timezone.now().date()
