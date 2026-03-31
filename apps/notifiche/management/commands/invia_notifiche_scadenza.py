from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from apps.sanitaria.models import EsitoIdoneita
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Invia notifiche email per le visite in scadenza nei prossimi 30 giorni'

    def handle(self, *args, **kwargs):
        oggi = timezone.now().date()
        soglia = oggi + timedelta(days=30)

        # Trova tutti gli esiti che scadono entro 30 giorni e non sono già scaduti.
        esiti = EsitoIdoneita.objects.filter(
            data_scadenza__gte=oggi,
            data_scadenza__lte=soglia,
        ).select_related('lavoratore__azienda')

        if not esiti.exists():
            self.stdout.write('Nessuna scadenza nei prossimi 30 giorni.')
            return

        # Raggruppa per azienda e data scadenza (una email per data)
        gruppi = {}
        for esito in esiti:
            azienda = esito.lavoratore.azienda
            chiave = (azienda, esito.data_scadenza)
            if chiave not in gruppi:
                gruppi[chiave] = []
            gruppi[chiave].append(esito)

        inviate = 0
        errori = 0

        for (azienda, data_scadenza), esiti_azienda in gruppi.items():
            nomi = []
            for esito in esiti_azienda:
                nomi.append(f"- {esito.lavoratore.nome_completo}")

            corpo = (
                "Gentile,\n"
                "Le segnaliamo che i seguenti dipendenti hanno il giudizio di idoneità alla mansione in scadenza in data "
                f"{data_scadenza.strftime('%d/%m/%Y')}:\n"
                f"{chr(10).join(nomi)}\n"
                "Siamo a disposizione per pianificare insieme le visite di rinnovo nel momento più comodo per la sua organizzazione.\n"
                "\n"
                "Accedi a MedLavDelta: https://medlavdelta.it/\n"
                "\n"
                "Per qualsiasi informazione, rimaniamo a sua disposizione.\n"
                "Cordiali saluti,\n"
                "Centro Delta"
            )

            destinatari = []
            if getattr(azienda, 'user', None) and azienda.user.email:
                destinatari.append(azienda.user.email)
            elif azienda.email_contatto:
                destinatari.append(azienda.email_contatto)
            centro_email = getattr(settings, 'CENTRO_MEDICO_EMAIL', None)
            if centro_email:
                destinatari.append(centro_email)
            destinatari = list(dict.fromkeys(destinatari))

            if not destinatari:
                errori += 1
                self.stdout.write(
                    self.style.ERROR(f'Nessun destinatario per {azienda.ragione_sociale}.')
                )
                continue

            try:
                send_mail(
                    subject='Promemoria | Scadenze idoneità su MedLavDelta',
                    message=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=destinatari,
                    fail_silently=False,
                )
                inviate += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Email inviata a {azienda.ragione_sociale} ({", ".join(destinatari)})'
                    )
                )
            except Exception as e:
                errori += 1
                logger.exception(
                    "Errore invio email scadenza. Host=%s Port=%s From=%s To=%s",
                    settings.EMAIL_HOST,
                    settings.EMAIL_PORT,
                    settings.DEFAULT_FROM_EMAIL,
                    ", ".join(destinatari),
                )
                self.stdout.write(
                    self.style.ERROR(f'Errore per {azienda.ragione_sociale}: {e}')
                )

        self.stdout.write(f'\nCompletato: {inviate} email inviate, {errori} errori.')
