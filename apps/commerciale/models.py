import re
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Max
from django.utils import timezone

from apps.aziende.models import Azienda


ZERO = Decimal('0.00')


def current_year():
    return timezone.localdate().year


class Preventivo(models.Model):
    numero_preventivo = models.PositiveIntegerField(blank=True, null=True, unique=True)
    data_preventivo = models.DateField(default=timezone.localdate)
    azienda = models.ForeignKey(
        Azienda,
        on_delete=models.CASCADE,
        related_name='preventivi',
    )
    oggetto = models.CharField(max_length=255)
    descrizione_oggetto = models.TextField(blank=True)
    note = models.TextField(blank=True)
    riferimento_commerciale = models.CharField(max_length=255, blank=True)
    assistente_tecnico = models.CharField(max_length=255, blank=True)
    giorni_lavorativi = models.PositiveIntegerField(blank=True, null=True)
    durata_offerta = models.DateField(blank=True, null=True)
    condizioni_pagamento_riservate = models.TextField(blank=True)
    aliquota_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('22.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
    )
    data_creazione = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_preventivo', '-numero_preventivo']
        verbose_name = 'Preventivo'
        verbose_name_plural = 'Preventivi'

    def __str__(self):
        return f'Preventivo {self.numero_formattato} - {self.azienda}'

    def save(self, *args, **kwargs):
        if not self.numero_preventivo:
            massimo = type(self).objects.aggregate(max_numero=Max('numero_preventivo'))['max_numero'] or 0
            self.numero_preventivo = massimo + 1
        if not self.condizioni_pagamento_riservate and self.azienda_id:
            self.condizioni_pagamento_riservate = self.azienda.condizioni_pagamento_riservate
        super().save(*args, **kwargs)

    @property
    def numero_formattato(self):
        if not self.numero_preventivo:
            return 'Bozza'
        return f'{self.numero_preventivo:08d}'

    @property
    def totale_imponibile(self):
        if not self.pk:
            return ZERO
        return sum((voce.importo_totale for voce in self.voci.all()), ZERO)

    @property
    def totale_iva(self):
        imponibile = self.totale_imponibile
        return (imponibile * self.aliquota_iva / Decimal('100.00')).quantize(Decimal('0.01'))

    @property
    def totale_complessivo(self):
        return self.totale_imponibile + self.totale_iva


class PreventivoVoce(models.Model):
    preventivo = models.ForeignKey(
        Preventivo,
        on_delete=models.CASCADE,
        related_name='voci',
    )
    descrizione = models.TextField()
    quantita = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    sconto_percentuale = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
    )
    ordine = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordine', 'id']
        verbose_name = 'Voce preventivo'
        verbose_name_plural = 'Voci preventivo'

    def __str__(self):
        return self.descrizione

    @property
    def importo_lordo(self):
        return (self.quantita * self.costo_unitario).quantize(Decimal('0.01'))

    @property
    def importo_totale(self):
        sconto = (self.importo_lordo * self.sconto_percentuale / Decimal('100.00')).quantize(Decimal('0.01'))
        return self.importo_lordo - sconto


class Fattura(models.Model):
    anno_fattura = models.PositiveSmallIntegerField(default=current_year)
    prefisso_numero = models.CharField(max_length=10, default='FPR')
    numero_progressivo = models.PositiveIntegerField(blank=True, null=True)
    data_fattura = models.DateField(default=timezone.localdate)
    data_accettazione_campione = models.DateField(blank=True, null=True)
    azienda = models.ForeignKey(
        Azienda,
        on_delete=models.CASCADE,
        related_name='fatture',
    )
    categoria_merceologica = models.CharField(max_length=255, blank=True)
    indirizzo_fatturazione = models.CharField(max_length=255, blank=True)
    cap_fatturazione = models.CharField(max_length=10, blank=True)
    comune_fatturazione = models.CharField(max_length=100, blank=True)
    provincia_fatturazione = models.CharField(max_length=2, blank=True)
    condizioni_pagamento_riservate = models.TextField(blank=True)
    modalita_pagamento = models.CharField(max_length=255, blank=True)
    aliquota_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('22.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
    )
    esente_iva = models.CharField(max_length=255, blank=True)
    esigibilita_iva = models.CharField(max_length=255, blank=True, default='IVA ad esigibilita immediata')
    gdd = models.CharField(max_length=255, blank=True)
    fine_mese = models.BooleanField(default=False)
    scadenza = models.DateField(blank=True, null=True)
    banca_appoggio = models.CharField(max_length=255, blank=True)
    causale = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    inviata_il = models.DateField(blank=True, null=True)
    data_incasso = models.DateField(blank=True, null=True)
    data_creazione = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_fattura', '-anno_fattura', '-numero_progressivo']
        verbose_name = 'Fattura'
        verbose_name_plural = 'Fatture'
        constraints = [
            models.UniqueConstraint(
                fields=['anno_fattura', 'prefisso_numero', 'numero_progressivo'],
                name='commerciale_fattura_numero_unico',
            )
        ]

    def __str__(self):
        return f'Fattura {self.numero_completo} - {self.azienda}'

    def save(self, *args, **kwargs):
        if not self.numero_progressivo:
            massimo = type(self).objects.filter(
                anno_fattura=self.anno_fattura,
                prefisso_numero=self.prefisso_numero,
            ).aggregate(max_numero=Max('numero_progressivo'))['max_numero'] or 0
            self.numero_progressivo = massimo + 1
        if not self.condizioni_pagamento_riservate and self.azienda_id:
            self.condizioni_pagamento_riservate = self.azienda.condizioni_pagamento_riservate
        super().save(*args, **kwargs)

    @property
    def numero_completo(self):
        if not self.numero_progressivo:
            return 'Bozza'
        return f'{self.prefisso_numero}/{self.numero_progressivo:04d}/{self.anno_fattura}'

    @property
    def numero_documento(self):
        if not self.numero_progressivo:
            return 'Bozza'
        return f'{self.prefisso_numero} {self.numero_progressivo}'

    @property
    def prima_voce(self):
        if not self.pk:
            return None
        return self.voci.order_by('ordine', 'id').first()

    @property
    def categoria_merceologica_display(self):
        if self.categoria_merceologica:
            return self.categoria_merceologica
        prima_voce = self.prima_voce
        if not prima_voce or not prima_voce.descrizione:
            return ''
        match = re.search(
            r'Categoria\s+Merceologica\s*:\s*(.+?)(?:\s*-\s*Prodotto\s+Dichiarato\s*:|$)',
            prima_voce.descrizione,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return ' '.join(match.group(1).split())
        return prima_voce.descrizione.strip()

    @property
    def totale_imponibile(self):
        if not self.pk:
            return ZERO
        return sum((voce.importo_totale for voce in self.voci.all()), ZERO)

    @property
    def totale_iva(self):
        imponibile = self.totale_imponibile
        return (imponibile * self.aliquota_iva / Decimal('100.00')).quantize(Decimal('0.01'))

    @property
    def totale_complessivo(self):
        return self.totale_imponibile + self.totale_iva


class FatturaVoce(models.Model):
    fattura = models.ForeignKey(
        Fattura,
        on_delete=models.CASCADE,
        related_name='voci',
    )
    descrizione = models.CharField(max_length=255)
    quantita = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    sconto_percentuale = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
    )
    ordine = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordine', 'id']
        verbose_name = 'Voce fattura'
        verbose_name_plural = 'Voci fattura'

    def __str__(self):
        return self.descrizione

    @property
    def importo_lordo(self):
        return (self.quantita * self.costo_unitario).quantize(Decimal('0.01'))

    @property
    def importo_totale(self):
        sconto = (self.importo_lordo * self.sconto_percentuale / Decimal('100.00')).quantize(Decimal('0.01'))
        return self.importo_lordo - sconto
