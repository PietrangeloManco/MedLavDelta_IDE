from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from apps.sanitaria.models import EsitoIdoneita
from datetime import timedelta


class Command(BaseCommand):
    help = 'Invia notifiche email per le visite in scadenza nei prossimi 30 giorni'

    def handle(self, *args, **kwargs):
        oggi = timezone.now().date()
        soglia = oggi + timedelta(days=30)

        # Trova tutti gli esiti che scadono entro 30 giorni e non sono già scaduti
        esiti = EsitoIdoneita.objects.filter(
            data_scadenza__gte=oggi,
            data_scadenza__lte=soglia,
        ).select_related('lavoratore__azienda')

        if not esiti.exists():
            self.stdout.write('Nessuna scadenza nei prossimi 30 giorni.')
            return

        # Raggruppa per azienda per mandare una sola email per azienda
        aziende_map = {}
        for esito in esiti:
            azienda = esito.lavoratore.azienda
            if azienda not in aziende_map:
                aziende_map[azienda] = []
            aziende_map[azienda].append(esito)

        inviate = 0
        errori = 0

        for azienda, esiti_azienda in aziende_map.items():
            # Costruisci il corpo dell'email
            righe = []
            for esito in esiti_azienda:
                giorni_mancanti = (esito.data_scadenza - oggi).days
                righe.append(
                    f"  - {esito.lavoratore.nome_completo} | "
                    f"Mansione: {esito.mansione} | "
                    f"Scadenza: {esito.data_scadenza.strftime('%d/%m/%Y')} "
                    f"(tra {giorni_mancanti} giorni)"
                )

            corpo = f"""Gentile {azienda.ragione_sociale},

le segnaliamo che i seguenti lavoratori hanno una visita medica in scadenza nei prossimi 30 giorni:

{chr(10).join(righe)}

La invitiamo a contattare Centro Delta per pianificare le visite.

Cordiali saluti,
Centro Delta Srl — Medicina del Lavoro
"""

            try:
                send_mail(
                    subject='⚠️ Scadenza visite mediche — Centro Delta',
                    message=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[azienda.email_contatto],
                    fail_silently=False,
                )
                inviate += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Email inviata a {azienda.ragione_sociale} ({azienda.email_contatto})')
                )
            except Exception as e:
                errori += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Errore per {azienda.ragione_sociale}: {e}')
                )

        self.stdout.write(f'\nCompletato: {inviate} email inviate, {errori} errori.')